from __future__ import annotations

import datetime as dt
import logging
import threading
import time

from .db import SqliteStore

logger = logging.getLogger(__name__)


def _next_run_after(now: dt.datetime) -> dt.datetime:
    """Return next scheduled time at 00:00/06:00/12:00/18:00."""
    candidates = [0, 6, 12, 18]
    for h in candidates:
        t = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if t > now:
            return t
    # next day 00:00
    next_day = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return next_day


class InitDailyScheduler:
    def __init__(self, store: SqliteStore, stop_event: threading.Event):
        self._store = store
        self._stop = stop_event

    def run_forever(self) -> None:
        # Run once on startup.
        try:
            inserted = self._store.init_today_for_all_drones(dt.datetime.now())
            logger.info("Init daily rows on startup inserted=%s", inserted)
        except Exception:
            logger.exception("Init daily rows on startup failed")

        while not self._stop.is_set():
            now = dt.datetime.now()
            nxt = _next_run_after(now)
            sleep_seconds = (nxt - now).total_seconds()

            # Sleep in small chunks so stop_event is responsive.
            remaining = max(0.0, sleep_seconds)
            while remaining > 0 and not self._stop.is_set():
                chunk = min(remaining, 5.0)
                time.sleep(chunk)
                remaining -= chunk

            if self._stop.is_set():
                break

            try:
                inserted = self._store.init_today_for_all_drones(dt.datetime.now())
                logger.info("Init daily rows inserted=%s", inserted)
            except Exception:
                logger.exception("Init daily rows failed")
