from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import Config, load_config
from .triage import route_file

log = logging.getLogger("liveframe.watcher")


class StableInboxHandler(FileSystemEventHandler):
    """Wait until Samba finishes writing, then triage."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._poll_loop, name="liveframe-stable", daemon=True)

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._stop.set()
        self._worker.join(timeout=5)

    def _mark(self, path: Path) -> None:
        if not self._is_inbox_file(path):
            return
        with self._lock:
            self._pending[str(path.resolve())] = time.monotonic()

    def _is_inbox_file(self, path: Path) -> bool:
        try:
            resolved = path.resolve()
        except OSError:
            return False
        if not resolved.is_file():
            return False
        try:
            resolved.relative_to(self.config.inbox.resolve())
        except ValueError:
            return False
        if resolved.name.startswith(".") or resolved.name.startswith("._"):
            return False
        if resolved.name.endswith(".tmp") or resolved.name.endswith(".partial"):
            return False
        return True

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._mark(Path(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._mark(Path(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._mark(Path(event.dest_path))

    def scan_existing(self) -> None:
        for path in sorted(self.config.inbox.rglob("*")):
            if path.is_file():
                self._mark(path)

    def _poll_loop(self) -> None:
        stable_for = self.config.triage.stable_seconds
        while not self._stop.is_set():
            time.sleep(0.4)
            now = time.monotonic()
            ready: list[str] = []
            with self._lock:
                for key, last_touch in list(self._pending.items()):
                    path = Path(key)
                    if not path.is_file():
                        self._pending.pop(key, None)
                        continue
                    try:
                        size_a = path.stat().st_size
                    except OSError:
                        self._pending.pop(key, None)
                        continue
                    # Require quiet period after last event
                    if now - last_touch < stable_for:
                        continue
                    time.sleep(0.15)
                    try:
                        size_b = path.stat().st_size
                    except OSError:
                        self._pending.pop(key, None)
                        continue
                    if size_a == size_b and size_a > 0:
                        ready.append(key)
                        self._pending.pop(key, None)

            for key in ready:
                path = Path(key)
                try:
                    route_file(path, self.config)
                except Exception:
                    log.exception("Triage failed for %s", path)


def run_watcher(config: Config) -> None:
    config.ensure_dirs()
    handler = StableInboxHandler(config)
    handler.scan_existing()
    handler.start()

    observer = Observer()
    observer.schedule(handler, str(config.inbox), recursive=True)
    observer.start()
    log.info(
        "Watching inbox=%s approved=%s hold=%s (stable=%.1fs)",
        config.inbox,
        config.approved,
        config.hold,
        config.triage.stable_seconds,
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher")
    finally:
        observer.stop()
        observer.join(timeout=5)
        handler.stop()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LiveFrame inbox watcher")
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config.yaml (default: LIVEFRAME_CONFIG or ./config.yaml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    run_watcher(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
