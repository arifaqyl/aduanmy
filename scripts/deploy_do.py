"""Deploy TrafficMY to DigitalOcean via paramiko (never PowerShell SSH)."""
from __future__ import annotations

import io
import re
import secrets
import sys
import tarfile
from pathlib import Path

import paramiko

HOST = "68.183.181.237"
USER = "root"
REMOTE = "/root/trafficmy"
REPO = Path(__file__).resolve().parents[1]
SECRETS = Path(r"D:\MyVault\SECRETS.md")
THREADS_SESSION = REPO / "data" / "private" / "threads-session.json"
SKIP_DIRS = {
    ".cursor",
    ".deepsec",
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "data",
    "node_modules",
    "output",
}
SKIP_FILES = {".env", ".env.production", ".env.local"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_DIR_PREFIXES = (".pytest_", ".pytest-", ".tmp-pytest")


def load_password() -> str:
    text = SECRETS.read_text(encoding="utf-8")
    match = re.search(r"^-\s*Password:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit("DigitalOcean password not found in vault secrets file")
    return match.group(1).strip()


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS or part.startswith(SKIP_DIR_PREFIXES) for part in path.parts):
        return True
    return path.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES


def run(ssh: paramiko.SSHClient, cmd: str, *, secret: bool = False) -> str:
    label = "(secret command)" if secret else cmd
    print(f"$ {label}")
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip() and not secret:
        safe = out.rstrip().encode("ascii", errors="replace").decode("ascii")
        print(safe)
    if err.strip() and not secret:
        safe = err.rstrip().encode("ascii", errors="replace").decode("ascii")
        print(safe, file=sys.stderr)
    if exit_code != 0:
        raise SystemExit(f"Command failed ({exit_code})")
    return out


def build_tarball() -> io.BytesIO:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for path in REPO.rglob("*"):
            rel = path.relative_to(REPO)
            if should_skip(rel):
                continue
            if path.is_dir():
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"))
    buffer.seek(0)
    return buffer


def docker_deploy(ssh: paramiko.SSHClient) -> None:
    run(ssh, f"cd {REMOTE} && docker build -t trafficmy:latest .")
    run(ssh, "docker volume create trafficmy_data >/dev/null 2>&1 || true")
    run(ssh, "docker stop trafficmy >/dev/null 2>&1 || true")
    run(ssh, "docker rm trafficmy >/dev/null 2>&1 || true")
    run(
        ssh,
        "docker run -d --name trafficmy --restart unless-stopped "
        "--init --stop-timeout 60 --log-opt max-size=10m --log-opt max-file=3 "
        "-p 8002:8000 --env-file /root/trafficmy/.env.production "
        "-v trafficmy_data:/data trafficmy:latest",
    )


def install_threads_session(ssh: paramiko.SSHClient, sftp: paramiko.SFTPClient) -> None:
    if not THREADS_SESSION.is_file():
        print("Threads session not found locally; production will use the public-search fallback.")
        return
    remote_session = f"{REMOTE}/.threads-session.json"
    sftp.put(str(THREADS_SESSION), remote_session)
    sftp.chmod(remote_session, 0o600)
    run(ssh, "docker volume create trafficmy_data >/dev/null 2>&1 || true")
    run(
        ssh,
        "install -d -m 700 /var/lib/docker/volumes/trafficmy_data/_data/private && "
        f"install -m 600 {remote_session} "
        "/var/lib/docker/volumes/trafficmy_data/_data/private/threads-session.json && "
        f"rm -f {remote_session}",
        secret=True,
    )


def ensure_nginx(ssh: paramiko.SSHClient) -> None:
    snippet = """
    location /traffic/ {
        proxy_pass http://127.0.0.1:8002/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
"""
    run(
        ssh,
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        "paths = list(Path('/etc/nginx/sites-enabled').glob('*'))\n"
        "if not paths:\n"
        "    raise SystemExit('nginx site config not found')\n"
        f"snippet = {snippet!r}\n"
        "for path in paths:\n"
        "    text = path.read_text(encoding='utf-8')\n"
        "    if 'location /traffic/' in text:\n"
        "        print(f'nginx already configured: {path}')\n"
        "        break\n"
        "    if 'location /' not in text:\n"
        "        continue\n"
        "    text = text.replace('location /', snippet + '\\n    location /', 1)\n"
        "    path.write_text(text, encoding='utf-8')\n"
        "    print(f'patched nginx config: {path}')\n"
        "    break\n"
        "else:\n"
        "    raise SystemExit('could not patch nginx config')\n"
        "PY",
    )
    run(ssh, "nginx -t && systemctl reload nginx")


def ensure_watchdog(ssh: paramiko.SSHClient) -> None:
    service = """[Unit]
Description=TrafficMY container watchdog
After=docker.service network-online.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c '/usr/bin/curl -fsS --max-time 15 http://127.0.0.1:8002/api/health/live >/dev/null || /usr/bin/docker restart trafficmy'
"""
    timer = """[Unit]
Description=Check TrafficMY every two minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
Persistent=true

[Install]
WantedBy=timers.target
"""
    run(
        ssh,
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        f"Path('/etc/systemd/system/trafficmy-watchdog.service').write_text({service!r}, encoding='utf-8')\n"
        f"Path('/etc/systemd/system/trafficmy-watchdog.timer').write_text({timer!r}, encoding='utf-8')\n"
        "PY",
    )
    run(ssh, "systemctl daemon-reload && systemctl enable --now trafficmy-watchdog.timer")


def write_remote_env(sftp: paramiko.SFTPClient, refresh_key: str) -> None:
    env_lines = "\n".join(
        [
            "ADUANMY_ENV=production",
            "ADUANMY_DB_PATH=/data/aduanmy.db",
            "ADUANMY_DATA_DIR=/data",
            "ADUANMY_AUTO_REFRESH_ENABLED=true",
            "ADUANMY_GTFS_ANOMALY_ENABLED=false",
            "ADUANMY_GTFS_REFRESH_INTERVAL_SECONDS=300",
            "ADUANMY_FULL_REFRESH_INTERVAL_SECONDS=900",
            "ADUANMY_DASHBOARD_POLL_INTERVAL_SECONDS=300",
            "ADUANMY_REFRESH_ON_STARTUP=true",
            "ADUANMY_DISCOVERY_DEPTH=full",
            "ADUANMY_STALE_AFTER_MINUTES=120",
            "ADUANMY_RETENTION_DAYS=90",
            "ADUANMY_CORS_ORIGINS=https://arifaqyl.me",
            "ADUANMY_ALLOW_DASHBOARD_REFRESH=false",
            "ADUANMY_EXPOSE_RAW_SOURCES=false",
            "ADUANMY_X_AUTO_COLLECT_ENABLED=false",
            "ADUANMY_THREADS_SESSION_PATH=/data/private/threads-session.json",
            "ADUANMY_REDDIT_MIN_INTERVAL_SECONDS=7200",
            "ADUANMY_X_MIN_INTERVAL_SECONDS=21600",
            "ADUANMY_BACKUP_ENABLED=true",
            "ADUANMY_BACKUP_INTERVAL_SECONDS=21600",
            "ADUANMY_BACKUP_RETENTION_COUNT=14",
            f"ADUANMY_REFRESH_API_KEY={refresh_key}",
            "",
        ]
    )
    with sftp.file(f"{REMOTE}/.env.production", "w") as handle:
        handle.write(env_lines)
    sftp.chmod(f"{REMOTE}/.env.production", 0o600)


def main() -> None:
    password = load_password()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=password, timeout=45)
    ssh.get_transport().set_keepalive(15)
    sftp = ssh.open_sftp()

    run(ssh, f"mkdir -p {REMOTE}")
    tarball = build_tarball()
    sftp.putfo(tarball, f"{REMOTE}/deploy.tar.gz")
    run(ssh, f"cd {REMOTE} && tar xzf deploy.tar.gz && rm deploy.tar.gz")

    refresh_key = secrets.token_urlsafe(24)
    write_remote_env(sftp, refresh_key)
    install_threads_session(ssh, sftp)

    docker_deploy(ssh)
    ensure_nginx(ssh)
    ensure_watchdog(ssh)
    run(
        ssh,
        "for i in $(seq 1 45); do "
        "curl -sf http://127.0.0.1:8002/api/health/live && exit 0; "
        "sleep 2; done; docker logs --tail 50 trafficmy; exit 1",
    )
    run(ssh, "curl -sf -o /dev/null -w '%{http_code}\\n' http://127.0.0.1/traffic/")
    sftp.close()
    ssh.close()
    print("TrafficMY deploy complete.")


if __name__ == "__main__":
    main()
