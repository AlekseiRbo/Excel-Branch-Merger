from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_INTERVAL_SECONDS = 0.5
WATCHED_EXTENSIONS = {".py", ".png", ".jpg", ".jpeg", ".json"}


def get_snapshot() -> dict[Path, int]:
    snapshot: dict[Path, int] = {}
    watched_locations = [ROOT / "gui.py", ROOT / "assets"]

    for location in watched_locations:
        if location.is_file():
            snapshot[location] = location.stat().st_mtime_ns
        elif location.is_dir():
            for path in location.rglob("*"):
                if path.is_file() and path.suffix.lower() in WATCHED_EXTENSIONS:
                    snapshot[path] = path.stat().st_mtime_ns

    return snapshot


def start_gui() -> subprocess.Popen[bytes]:
    print("Starting Excel Branch Merger GUI...")
    return subprocess.Popen([sys.executable, "gui.py"], cwd=ROOT)


def stop_gui(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> None:
    previous_snapshot = get_snapshot()
    process = start_gui()
    print("Development mode is active.")
    print("Save gui.py or an image in assets to restart the window.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            current_snapshot = get_snapshot()

            if current_snapshot != previous_snapshot:
                print("Change detected. Restarting GUI...")
                stop_gui(process)
                process = start_gui()
                previous_snapshot = current_snapshot

            if process.poll() is not None:
                print("GUI closed. Development runner stopped.")
                break
    except KeyboardInterrupt:
        print("Stopping development mode...")
        stop_gui(process)


if __name__ == "__main__":
    main()
