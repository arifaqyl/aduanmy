from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger("trafficmy.scheduler")
_lock = threading.Lock()
_running = False
_last_gtfs_at: str | None = None
_last_full_at: str | None = None
_last_error: str | None = None
_last_backup_at: str | None = None
_last_backup_error: str | None = None
_scheduler_thread: threading.Thread | None = None
_scheduler_lock_owner = False
_scheduler_lock_fd: int | None = None


def _scheduler_lock_path() -> Path:
    return Path(settings.data_dir) / ".scheduler.lock"


def _try_acquire_scheduler_lock() -> bool:
    """Advisory single-worker guard for production multi-worker deploys.

    Returns True if this process should run the scheduler. In dev/test it
    always returns True (single worker). In production we hold an fcntl flock
    on the lockfile for the process lifetime so a container restart releases
    it immediately (volume file alone must not block the next boot).
    """
    if settings.env != "production":
        return True
    global _scheduler_lock_owner, _scheduler_lock_fd
    if _scheduler_lock_fd is not None:
        return True
    lock_path = _scheduler_lock_path()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return True  # cannot create dir -> assume single worker
    try:
        import fcntl
    except ImportError:
        # Windows/dev without fcntl — exclusive create + short age steal.
        return _try_acquire_scheduler_lock_fallback(lock_path)

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    except OSError:
        return True
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    except OSError:
        os.close(fd)
        return True
    try:
        os.ftruncate(fd, 0)
        os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode())
    except OSError:
        pass
    _scheduler_lock_fd = fd  # keep open — flock dies with process/container
    _scheduler_lock_owner = True
    return True


def _try_acquire_scheduler_lock_fallback(lock_path: Path) -> bool:
    """O_EXCL fallback when fcntl is unavailable (Windows)."""
    global _scheduler_lock_owner
    try:
        age = time.time() - lock_path.stat().st_mtime
        if age > 120:
            try:
                lock_path.unlink()
            except OSError:
                pass
    except FileNotFoundError:
        pass
    except OSError:
        pass
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, f"{os.getpid()}\n{time.time()}\n".encode())
    finally:
        os.close(fd)
    _scheduler_lock_owner = True
    return True


def _touch_scheduler_lock() -> None:
    """Refresh the lockfile mtime (fallback/age diagnostics)."""
    if not _scheduler_lock_owner:
        return
    try:
        _scheduler_lock_path().touch()
    except OSError:
        pass


def scheduler_state() -> dict:
    return {
        "enabled": settings.auto_refresh_enabled,
        "gtfs_anomaly_enabled": settings.gtfs_anomaly_enabled,
        "gtfs_interval_seconds": settings.gtfs_refresh_interval_seconds,
        "full_interval_seconds": settings.full_refresh_interval_seconds,
        "running": _running,
        "last_gtfs_at": _last_gtfs_at,
        "last_full_at": _last_full_at,
        "last_error": _last_error,
        "thread_alive": bool(_scheduler_thread and _scheduler_thread.is_alive()),
        "last_backup_at": _last_backup_at,
        "last_backup_error": _last_backup_error,
    }


def _run_gtfs() -> None:
    global _last_gtfs_at, _last_error
    if not settings.gtfs_anomaly_enabled:
        return
    from app.services.ingest_service import run_gtfs_ingest

    if not _lock.acquire(blocking=False):
        return
    try:
        _last_error = None
        report = run_gtfs_ingest()
        _last_gtfs_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logger.info("gtfs ingest complete: %s rows", report.get("written", 0))
    except Exception as exc:  # pragma: no cover
        _last_error = str(exc)
        logger.exception("gtfs ingest failed")
    finally:
        _lock.release()

def is_ingest_running() -> bool:
    return _lock.locked()


def trigger_full_ingest_async() -> bool:
    if _lock.locked():
        return False
    t = threading.Thread(target=run_full_now, name="trafficmy-manual-refresh", daemon=True)
    t.start()
    return True


def run_full_now(*, respect_cadence: bool = True) -> dict | None:
    global _last_full_at, _last_error, _running
    from app.services.ingest_service import run_ingest

    if not _lock.acquire(blocking=False):
        return None
    try:
        _running = True
        _last_error = None
        report = run_ingest(respect_cadence=respect_cadence)
        _last_full_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        logger.info("full ingest complete: %s rows", report.get("written", 0))
        try:
            from app.services.telegram_alerts import check_and_notify

            check_and_notify()
        except Exception:  # pragma: no cover - alerts must never break ingest
            logger.exception("telegram check_and_notify failed after ingest")
        try:
            from app.services.telegram_alerts import check_source_health_and_alert

            check_source_health_and_alert()
        except Exception:  # pragma: no cover - alerts must never break ingest
            logger.exception("source health alert failed after ingest")
        try:
            # Keeps frequencies.txt warm so board renders never touch the
            # network. download_static() is a no-op while the cache is <24h,
            # so this costs one HTTP call a day, not one per ingest.
            from app.services.headway_service import warm_headways

            warm_headways()
        except Exception:  # pragma: no cover - a cold headway cache degrades to None, never breaks ingest
            logger.exception("headway warm-up failed after ingest")
        return report
    except Exception as exc:  # pragma: no cover
        _last_error = str(exc)
        logger.exception("full ingest failed")
    finally:
        _running = False
        _lock.release()


def _run_full() -> None:
    run_full_now()


def _run_backup() -> None:
    global _last_backup_at, _last_backup_error
    if not settings.backup_enabled:
        return
    from app.db.maintenance import backup_database

    try:
        backup_database()
        _last_backup_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _last_backup_error = None
    except Exception as exc:  # pragma: no cover - production filesystem failure
        _last_backup_error = str(exc)
        logger.exception("database backup failed")


def _loop() -> None:
    gtfs_every = max(120, int(settings.gtfs_refresh_interval_seconds))
    full_every = max(gtfs_every, int(settings.full_refresh_interval_seconds))
    backup_every = max(full_every, int(settings.backup_interval_seconds))
    next_gtfs = time.time()
    next_full = time.time() + (full_every if settings.refresh_on_startup else 30)
    next_backup = time.time() + min(backup_every, 300)
    while True:
        try:
            time.sleep(30)
            _touch_scheduler_lock()
            now = time.time()
            if now >= next_backup:
                _run_backup()
                next_backup = now + backup_every
            if now >= next_full:
                _run_full()
                next_full = time.time() + full_every
                next_gtfs = time.time() + gtfs_every
                continue
            if settings.gtfs_anomaly_enabled and now >= next_gtfs:
                _run_gtfs()
                next_gtfs = time.time() + gtfs_every
        except Exception:  # pragma: no cover - keep the scheduler alive
            logger.exception("scheduler tick failed")
            time.sleep(5)


def start_scheduler() -> None:
    global _scheduler_thread
    if not settings.auto_refresh_enabled:
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    if not _try_acquire_scheduler_lock():
        logger.info("scheduler: deferring to another worker (lock held)")
        return
    _scheduler_thread = threading.Thread(target=_loop, name="trafficmy-scheduler", daemon=True)
    _scheduler_thread.start()
    logger.info(
        "scheduler: gtfs anomaly=%s, full every %ss",
        settings.gtfs_anomaly_enabled,
        settings.full_refresh_interval_seconds,
    )


def maybe_refresh_on_startup() -> None:
    if not settings.refresh_on_startup:
        return
    starter = threading.Thread(target=_run_full, name="trafficmy-startup-refresh", daemon=True)
    starter.start()
