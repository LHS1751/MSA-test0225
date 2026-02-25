from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    sqlite_path: str

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None

    http_host: str
    http_port: int


def _getenv_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def load_config() -> Config:
    sqlite_path = os.getenv("SQLITE_PATH", os.path.join("data", "msa3_flytime.sqlite3"))

    mqtt_host = os.getenv("MQTT_HOST", "127.0.0.1")
    mqtt_port = _getenv_int("MQTT_PORT", 1883)
    mqtt_username = os.getenv("MQTT_USERNAME") or None
    mqtt_password = os.getenv("MQTT_PASSWORD") or None

    http_host = os.getenv("HTTP_HOST", "0.0.0.0")
    http_port = _getenv_int("HTTP_PORT", 8000)

    return Config(
        sqlite_path=sqlite_path,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        http_host=http_host,
        http_port=http_port,
    )
