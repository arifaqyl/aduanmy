from __future__ import annotations

import logging
import threading
import time

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
