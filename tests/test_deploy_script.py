from pathlib import Path

from scripts.deploy_do import should_skip


def test_dockerfile_uses_production_collection_defaults():
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "ADUANMY_FULL_REFRESH_INTERVAL_SECONDS=900" in dockerfile
    assert "ADUANMY_GTFS_ANOMALY_ENABLED=false" in dockerfile
    assert "ADUANMY_RETENTION_DAYS=90" in dockerfile
    assert "ADUANMY_THREADS_SESSION_PATH=/data/private/threads-session.json" in dockerfile
    assert "pip install --no-cache-dir -r requirements.production.txt" in dockerfile


def test_deploy_archive_excludes_transient_and_nested_dependency_directories():
    assert should_skip(Path(".deepsec/node_modules/package/index.js"))
    assert should_skip(Path("tools/node_modules/package/index.js"))
    assert should_skip(Path(".pytest_review/test_cache/file"))
    assert should_skip(Path("app/__pycache__/main.pyc"))
    assert should_skip(Path("data/aduanmy.db"))
    assert should_skip(Path("data/private/threads-session.json"))
    assert should_skip(Path("output/playwright/home.png"))
    assert should_skip(Path(".playwright-cli/session.json"))
    assert should_skip(Path(".pytest-codex-full-2/test.db"))


def test_deploy_archive_keeps_runtime_source():
    assert not should_skip(Path("app/main.py"))
    assert not should_skip(Path("static/index.html"))
