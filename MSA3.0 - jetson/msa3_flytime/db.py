from __future__ import annotations

import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config


class DbError(RuntimeError):
    pass


@dataclass(frozen=True)
class Drone:
    drone_sn: str
    drone_type: str | None
    drone_version: str | None


@dataclass(frozen=True)
class FlyTimeDay:
    drone_sn: str
    fly_date_time: dt.datetime
    revised_start_time: int
    today_start_total_flight_time: int
    total_flight_time: int
    today_flight_time: int


def _dt_to_text(value: dt.datetime) -> str:
    # Match yyyy-MM-dd HH:mm:ss
    v = value.replace(microsecond=0)
    return v.strftime("%Y-%m-%d %H:%M:%S")


def _text_to_dt(value: str) -> dt.datetime:
    # Accept both "YYYY-MM-DD HH:MM:SS" and ISO-ish
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


class SqliteStore:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._path = str(Path(cfg.sqlite_path))
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def init_schema(self) -> None:
        migrations_path = Path(__file__).resolve().parent / "migrations.sql"
        sql = migrations_path.read_text(encoding="utf-8")
        conn = self._conn()
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()

    def ping(self) -> None:
        conn = self._conn()
        try:
            conn.execute("SELECT 1").fetchall()
            conn.commit()
        finally:
            conn.close()

    def ensure_drone(
        self,
        drone_sn: str,
        drone_type: str | None = None,
        version: str | None = None,
    ) -> None:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO t_drone (drone_sn, drone_type, drone_version, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(drone_sn) DO UPDATE SET
                  drone_type = COALESCE(excluded.drone_type, t_drone.drone_type),
                  drone_version = COALESCE(excluded.drone_version, t_drone.drone_version),
                  updated_at = CURRENT_TIMESTAMP
                """.strip(),
                (drone_sn, drone_type, version),
            )
            conn.commit()
        finally:
            conn.close()

    def list_drones(self) -> list[Drone]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT drone_sn, drone_type, drone_version FROM t_drone ORDER BY drone_sn"
            ).fetchall()
            conn.commit()
            return [
                Drone(
                    drone_sn=r["drone_sn"],
                    drone_type=r["drone_type"],
                    drone_version=r["drone_version"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_latest_total(self, drone_sn: str) -> int | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT total_flight_time
                FROM t_fly_time
                WHERE drone_sn = ?
                ORDER BY fly_date_time DESC
                LIMIT 1
                """.strip(),
                (drone_sn,),
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else None
        finally:
            conn.close()

    def ensure_today_row(self, drone_sn: str, now: dt.datetime, initial_total: int) -> FlyTimeDay:
        today = now.date().isoformat()
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT drone_sn, fly_date_time, revised_start_time,
                       today_start_total_flight_time, total_flight_time, today_flight_time
                FROM t_fly_time
                WHERE drone_sn = ? AND date(fly_date_time) = ?
                LIMIT 1
                """.strip(),
                (drone_sn, today),
            ).fetchone()
            if row:
                conn.commit()
                return FlyTimeDay(
                    drone_sn=row[0],
                    fly_date_time=_text_to_dt(row[1]),
                    revised_start_time=int(row[2]),
                    today_start_total_flight_time=int(row[3]),
                    total_flight_time=int(row[4]),
                    today_flight_time=int(row[5]),
                )

            now_text = _dt_to_text(now)
            conn.execute(
                """
                INSERT INTO t_fly_time (
                    drone_sn, fly_date_time, revised_start_time,
                    today_start_total_flight_time, total_flight_time, today_flight_time,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """.strip(),
                (drone_sn, now_text, 0, int(initial_total), int(initial_total), 0),
            )
            conn.commit()
            return FlyTimeDay(
                drone_sn=drone_sn,
                fly_date_time=now.replace(microsecond=0),
                revised_start_time=0,
                today_start_total_flight_time=int(initial_total),
                total_flight_time=int(initial_total),
                today_flight_time=0,
            )
        finally:
            conn.close()

    def update_today_total(self, drone_sn: str, now: dt.datetime, new_total: int) -> None:
        today = now.date().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE t_fly_time
                SET
                  fly_date_time = ?,
                  total_flight_time = ?,
                  today_flight_time = MAX(0, ? - today_start_total_flight_time),
                  updated_at = CURRENT_TIMESTAMP
                WHERE drone_sn = ? AND date(fly_date_time) = ?
                """.strip(),
                (
                    _dt_to_text(now),
                    int(new_total),
                    int(new_total),
                    drone_sn,
                    today,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def revise_start_on_first_osd(self, drone_sn: str, now: dt.datetime, new_total: int) -> None:
        today = now.date().isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """
                UPDATE t_fly_time
                SET
                  fly_date_time = ?,
                  revised_start_time = 1,
                  today_start_total_flight_time = ?,
                  total_flight_time = ?,
                  today_flight_time = 0,
                  updated_at = CURRENT_TIMESTAMP
                WHERE drone_sn = ?
                  AND date(fly_date_time) = ?
                  AND revised_start_time = 0
                """.strip(),
                (_dt_to_text(now), int(new_total), int(new_total), drone_sn, today),
            )
            conn.commit()
        finally:
            conn.close()

    def get_day_row(self, drone_sn: str, day: dt.date) -> FlyTimeDay | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT drone_sn, fly_date_time, revised_start_time,
                       today_start_total_flight_time, total_flight_time, today_flight_time
                FROM t_fly_time
                WHERE drone_sn = ? AND date(fly_date_time) = ?
                LIMIT 1
                """.strip(),
                (drone_sn, day.isoformat()),
            ).fetchone()
            conn.commit()
            if not row:
                return None
            return FlyTimeDay(
                drone_sn=row[0],
                fly_date_time=_text_to_dt(row[1]),
                revised_start_time=int(row[2]),
                today_start_total_flight_time=int(row[3]),
                total_flight_time=int(row[4]),
                today_flight_time=int(row[5]),
            )
        finally:
            conn.close()

    def init_today_for_all_drones(self, now: dt.datetime) -> int:
        drones = self.list_drones()
        inserted = 0
        for d in drones:
            latest = self.get_latest_total(d.drone_sn)
            if latest is None:
                latest = 0
            day_row = self.get_day_row(d.drone_sn, now.date())
            if day_row is None:
                self.ensure_today_row(d.drone_sn, now, latest)
                inserted += 1
        return inserted

    def summary_by_range(self, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT d.drone_sn, d.drone_type, d.drone_version,
                       COALESCE(SUM(f.today_flight_time), 0) AS total_seconds
                FROM t_drone d
                LEFT JOIN t_fly_time f
                  ON f.drone_sn = d.drone_sn
                 AND date(f.fly_date_time) BETWEEN ? AND ?
                GROUP BY d.drone_sn, d.drone_type, d.drone_version
                ORDER BY d.drone_sn
                """.strip(),
                (start.isoformat(), end.isoformat()),
            ).fetchall()
            conn.commit()
            result: list[dict[str, Any]] = []
            for r in rows:
                result.append(
                    {
                        "drone_sn": r["drone_sn"],
                        "drone_type": r["drone_type"],
                        "drone_version": r["drone_version"],
                        "total_seconds": int(r["total_seconds"] or 0),
                    }
                )
            return result
        finally:
            conn.close()

    def drone_daily_breakdown(self, drone_sn: str, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT date(fly_date_time) AS fly_date, today_flight_time AS seconds
                FROM t_fly_time
                WHERE drone_sn = ? AND date(fly_date_time) BETWEEN ? AND ?
                ORDER BY date(fly_date_time)
                """.strip(),
                (drone_sn, start.isoformat(), end.isoformat()),
            ).fetchall()
            conn.commit()
            return [
                {"fly_date": r["fly_date"], "seconds": int(r["seconds"] or 0)}
                for r in rows
            ]
        finally:
            conn.close()

    def get_revised_flag(self, drone_sn: str, day: dt.date) -> int | None:
        conn = self._conn()
        try:
            row = conn.execute(
                """
                SELECT revised_start_time
                FROM t_fly_time
                WHERE drone_sn = ? AND date(fly_date_time) = ?
                LIMIT 1
                """.strip(),
                (drone_sn, day.isoformat()),
            ).fetchone()
            conn.commit()
            return int(row[0]) if row else None
        finally:
            conn.close()
