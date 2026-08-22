import json
import os
import re
import subprocess
import tempfile
import threading
import time

import hid

VIVE_DONGLE_VID = 0x28DE
# Both standalone "Watchman Dongle" units (0x2101) and an HMD's built-in
# radios (0x2102, e.g. the Index's two onboard radios - they exist
# specifically to pair its controllers, not just to represent the headset
# itself) can host a live wireless controller/tracker connection.
VIVE_DONGLE_PIDS = (0x2101, 0x2102)

# How long the RF stream from a paired device must go quiet before we call it
# disconnected. The stream isn't perfectly continuous, so this absorbs small
# natural gaps without misreading them as a power-off.
DISCONNECT_SILENCE_SECONDS = 1.0
READ_POLL_INTERVAL_SECONDS = 0.01

_CONNECTED_LINE_RE = re.compile(r"^(\S+): Connected to receiver (\S+)$")
# NOTE: lighthouse_console prints its "lh> " prompt and then, for a command
# that replies synchronously (like "battery"), writes the reply right after
# it on the *same* line with no separating newline - e.g. "lh> battery (not
# charging): 96". So this must NOT be anchored to the start of the line
# (unlike _CONNECTED_LINE_RE, whose line is always a fresh async message).
_BATTERY_LINE_RE = re.compile(r"battery \([^)]*\): (\d+)")

# Maps the lighthouse_console/config "device_class" field to a short display label.
DEVICE_CLASS_LABELS = {
    "controller": "Controller",
    "generic_tracker": "Tracker",
    "hmd": "HMD",
}


def query_paired_device(dongle_serial, exe_path, timeout=6):
    """Runs one lighthouse_console session against a single dongle to find the
    serial, battery level, and device class (controller/tracker/...) of
    whatever's currently connected to it. Returns (paired_serial,
    battery_percent, device_class_label); any of these is None if not
    available (nothing connected, class unrecognized, or the tool couldn't
    be reached)."""
    config_fd, config_path = tempfile.mkstemp(suffix=".json")
    os.close(config_fd)
    os.remove(config_path)  # let lighthouse_console create it fresh

    try:
        process = subprocess.Popen(
            [exe_path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, universal_newlines=True,
        )
    except FileNotFoundError:
        return None, None, None

    process.stdin.write(f"serial {dongle_serial}\ndownloadconfig {config_path}\nbattery\nquit\n")
    process.stdin.close()
    try:
        out, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, _ = process.communicate()

    paired_serial = None
    battery = None
    for line in out.splitlines():
        match = _CONNECTED_LINE_RE.match(line.strip())
        if match and match.group(2) == dongle_serial:
            paired_serial = match.group(1)
            continue
        match = _BATTERY_LINE_RE.search(line)
        if match and paired_serial is not None:
            battery = int(match.group(1))

    device_class = None
    if os.path.exists(config_path):
        try:
            with open(config_path) as config_file:
                config = json.load(config_file)
            raw_class = config.get("device_class")
            device_class = DEVICE_CLASS_LABELS.get(raw_class, raw_class)
        except (OSError, ValueError):
            pass
        finally:
            os.remove(config_path)

    return paired_serial, battery, device_class


class DongleWatcher:
    """Watches one Watchman dongle's raw HID report stream to detect, in near
    real time, whether a wireless controller/tracker is currently connected
    to it - without polling lighthouse_console. A connected device streams
    RF telemetry reports continuously; silence means nothing's connected.

    This opens the dongle's HID interface non-exclusively (same access model
    lighthouse_console/SteamVR themselves use), so it's safe to run alongside
    either. On a transition to connected, it makes one lighthouse_console
    call to resolve the paired device's own serial and battery level.
    """

    def __init__(self, dongle_serial, exe_path, on_change):
        self.dongle_serial = dongle_serial
        self.exe_path = exe_path
        self.on_change = on_change  # callback(dongle_serial, connected, paired_serial, battery, device_class)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2)

    def _run(self):
        device = hid.device()
        for pid in VIVE_DONGLE_PIDS:
            try:
                device.open(VIVE_DONGLE_VID, pid, self.dongle_serial)
                break
            except OSError:
                continue
        else:
            return
        device.set_nonblocking(1)

        connected = False
        last_report_time = None
        try:
            while not self._stop_event.is_set():
                report = device.read(64)
                now = time.monotonic()
                if report:
                    last_report_time = now
                    if not connected:
                        connected = True
                        paired_serial, battery, device_class = query_paired_device(self.dongle_serial, self.exe_path)
                        self.on_change(self.dongle_serial, True, paired_serial, battery, device_class)
                elif connected and last_report_time is not None and (now - last_report_time) > DISCONNECT_SILENCE_SECONDS:
                    connected = False
                    self.on_change(self.dongle_serial, False, None, None, None)
                time.sleep(READ_POLL_INTERVAL_SECONDS)
        finally:
            device.close()
