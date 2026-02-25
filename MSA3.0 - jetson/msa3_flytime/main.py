from __future__ import annotations

import logging
import threading
from pathlib import Path
from logging.handlers import RotatingFileHandler

from .config import load_config
from .db import SqliteStore
from .http_server import serve
from .mqtt_client import MqttRunner
from .scheduler import InitDailyScheduler


def main() -> None:
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "msa3_flytime.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    fh = RotatingFileHandler(str(log_file), maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8")
    fh.setFormatter(fmt)

    root.handlers.clear()
    root.addHandler(sh)
    root.addHandler(fh)

    cfg = load_config()
    store = SqliteStore(cfg)
    store.ping()

    stop_event = threading.Event()

    # Scheduler thread
    scheduler = InitDailyScheduler(store, stop_event)
    t_scheduler = threading.Thread(target=scheduler.run_forever, name="scheduler", daemon=True)
    t_scheduler.start()

    # MQTT thread
    mqtt_runner = MqttRunner(cfg, store)
    t_mqtt = threading.Thread(target=mqtt_runner.run_forever, name="mqtt", daemon=True)
    t_mqtt.start()

    # HTTP server (main thread)
    static_dir = str(Path(__file__).resolve().parent / "static")
    server = serve(store, cfg.http_host, cfg.http_port, static_dir=static_dir)
    logging.getLogger(__name__).info("HTTP serving on http://%s:%s", cfg.http_host, cfg.http_port)

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()


if __name__ == "__main__":
    main()
