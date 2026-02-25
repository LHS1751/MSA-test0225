-- SQLite schema for drone flight time tracking

CREATE TABLE IF NOT EXISTS t_drone (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  drone_sn TEXT NOT NULL UNIQUE,
  drone_type TEXT NULL,
  drone_version TEXT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE TABLE IF NOT EXISTS t_fly_time (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  drone_sn TEXT NOT NULL,
  fly_date_time TEXT NOT NULL,
  revised_start_time INTEGER NOT NULL DEFAULT 0,
  today_start_total_flight_time INTEGER NOT NULL,
  total_flight_time INTEGER NOT NULL,
  today_flight_time INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);

CREATE INDEX IF NOT EXISTS idx_t_fly_time_drone ON t_fly_time (drone_sn);
CREATE INDEX IF NOT EXISTS idx_t_fly_time_time ON t_fly_time (fly_date_time);

-- 每台無人機每天僅一筆（SQLite 支援 expression index）
CREATE UNIQUE INDEX IF NOT EXISTS uk_t_fly_time_drone_day
ON t_fly_time (drone_sn, date(fly_date_time));

