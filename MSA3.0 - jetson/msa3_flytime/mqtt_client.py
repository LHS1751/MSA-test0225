from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from typing import Any

from .config import Config
from .db import SqliteStore

logger = logging.getLogger(__name__)


def _extract_drone_sn_from_topic(topic: str) -> str | None:
    # thing/product/{device_sn}/osd
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == "thing" and parts[1] == "product":
        return parts[2]
    return None


def _find_total_flight_time(payload: Any) -> float | None:
    """Best-effort extraction of total_flight_time (seconds) from unknown JSON shapes."""
    if payload is None:
        return None

    if isinstance(payload, (int, float)):
        return float(payload)

    if isinstance(payload, dict):
        # direct
        if "total_flight_time" in payload and isinstance(payload["total_flight_time"], (int, float)):
            return float(payload["total_flight_time"])

        # common wrappers
        for key in ("data", "osd", "state", "payload"):
            if key in payload:
                v = _find_total_flight_time(payload.get(key))
                if v is not None:
                    return v

        # deep scan (bounded)
        for _, v in list(payload.items())[:50]:
            vv = _find_total_flight_time(v)
            if vv is not None:
                return vv

    if isinstance(payload, list):
        for item in payload[:50]:
            v = _find_total_flight_time(item)
            if v is not None:
                return v

    return None


@dataclass
class MqttRunner:
    cfg: Config
    store: SqliteStore

    def run_forever(self) -> None:
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "paho-mqtt not installed. Install requirements.txt first."
            ) from e

        client = mqtt.Client()
        if self.cfg.mqtt_username:
            client.username_pw_set(self.cfg.mqtt_username, self.cfg.mqtt_password or "")

        def on_connect(_client, _userdata, _flags, rc, *_args):
            if rc == 0:
                logger.info("MQTT connected")
                _client.subscribe("thing/product/+/osd")
            else:
                logger.error("MQTT connect failed rc=%s", rc)

        def on_message(_client, _userdata, msg):
            topic = msg.topic
            drone_sn = _extract_drone_sn_from_topic(topic)
            if not drone_sn:
                return

            try:
                raw = msg.payload.decode("utf-8", errors="ignore")
                payload = json.loads(raw) if raw else None
            except Exception:
                payload = None

            total = _find_total_flight_time(payload)
            if total is None:
                return

            total_int = int(round(float(total)))
            now = dt.datetime.now()

            try:
                self.store.ensure_drone(drone_sn)
                self.store.ensure_today_row(drone_sn, now, total_int)

                # Spec: if revised_start_time == 0, revise today's start exactly once
                # using the first OSD total_flight_time received today.
                self.store.revise_start_on_first_osd(drone_sn, now, total_int)

                # Always update today's total & computed today_flight_time.
                self.store.update_today_total(drone_sn, now, total_int)
            except Exception:
                logger.exception("Failed to process OSD for %s", drone_sn)

        client.on_connect = on_connect
        client.on_message = on_message

        logger.info("Connecting MQTT %s:%s", self.cfg.mqtt_host, self.cfg.mqtt_port)
        client.connect(self.cfg.mqtt_host, self.cfg.mqtt_port, keepalive=60)
        client.loop_forever()
