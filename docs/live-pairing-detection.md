# Live pairing detection: research notes

This documents how `source/dongle_watcher.py` knows, in near real time, which
wireless controller/tracker is connected to which dongle - and the dead ends
that led there. Written up so the reasoning survives past the commit that
introduced it.

## The question

`lighthouse_console`'s own commands tell you which USB dongles exist, but not
which *wireless* device is currently bonded to a given dongle, nor its type
(controller vs. tracker) or battery. The app needed this to show live
per-row pairing status without polling a multi-second CLI command in a loop.

## `lighthouse_console` CLI: what works and what doesn't

`lighthouse_console.exe` (from `SteamVR/tools/lighthouse/bin/win64/`) is
Valve's own diagnostic tool. Relevant behavior, found by direct
experimentation:

- **One-shot CLI-argument mode** (`lighthouse_console.exe dongleinfo`) runs a
  single command against the *default* receiver and exits cleanly. It's what
  the app already used for `dongleinfo`/`serial` list queries.
- **Interactive stdin mode** (`serial <dongle>\n<command>\n...\nquit\n` piped
  to stdin) is required to target a *specific* dongle. Selecting a dongle via
  `serial <x>` blocks until the connection attempt finishes - no artificial
  `sleep` between commands is needed.
- **`deviceinfo` is unreliable for anything but the default receiver.** Its
  `DEVICEINFO serial=... device_class=...` output only ever reflects the
  first-opened default receiver (the wired HMD, e.g. `LHR-E34FAE56`), even
  when a different dongle was just selected and successfully read its
  config. This isn't a timing issue - retried with an explicit `sleep` and a
  `downloadconfig` completing first, still stuck on the default device. Don't
  rely on it for anything except the default receiver.
- **`battery`'s reply text has no leading newline.** The CLI prints its `lh>`
  prompt, then a synchronous command's reply right after it on the *same*
  line: `lh> battery (not charging): 96`. A regex anchored to the start of
  the line (`^battery`) will never match. Async status lines (like the
  `<serial>: Connected to receiver <dongle>` line) don't have this problem -
  they're always emitted with their own leading newline.
- **`battery` is sticky across `serial` switches in the same session.** If
  you select dongle A (connected), read its battery, then switch to dongle B
  (nothing connected), the `battery` command keeps reporting dongle A's last
  value instead of resetting. Only trust a `battery` reply that's paired
  with a fresh `<serial>: Connected to receiver <dongle>` line for the dongle
  you actually care about, or avoid the problem entirely by using one fresh
  subprocess per dongle (see below).
- **`downloadconfig <path>` writes the device's full config as JSON**, and
  it's the only reliable way found to get `device_class` for a non-default
  device. Top-level fields include `device_class` (`"controller"`,
  `"generic_tracker"`, `"hmd"`, ...), `device_serial_number`, `device_pid`,
  `device_vid`. This is what `dongle_watcher.query_paired_device()` parses.

### Timing: sequential vs. batched vs. parallel

Querying `serial <dongle>\nbattery\nquit\n` per dongle, measured over 3
trials each against 3 real dongles:

| Approach | Avg total time (3 dongles) |
|---|---|
| Separate process per dongle, run sequentially | 7.52s |
| One process, dongles queried sequentially via stdin | 4.98s |
| **One process per dongle, launched concurrently** | **2.72s** |

Fixed per-invocation startup cost (opening the default HMD receiver) is
~1.3s; each additional `serial` selection adds ~1.1s of real RF round-trip
time. Running one process per dongle *in parallel* collapses the total to
roughly the cost of the single slowest dongle, instead of the sum - this is
what `dongle_watcher.query_paired_device()` relies on implicitly by being
called once per dongle from independent watcher threads.

Bypassing `lighthouse_console` entirely and reimplementing the wireless
protocol from scratch (see below) was considered and rejected for the
*identity/battery/class* lookup specifically: the ~1.1s/dongle floor is real
RF handshake time with the physical device, not tool overhead, so a
reimplementation would hit the same wall while requiring a full
reverse-engineering of Valve's proprietary compressed config format (prior
art: [libsurvive](https://github.com/collabora/libsurvive),
[LighthouseRedox](https://github.com/nairol/LighthouseRedox) - neither is a
small effort).

## Direct HID access: what it's good for

While full identity/battery/class lookup isn't worth reimplementing,
*detecting that something just connected or disconnected* is - and turned
out to be nearly free.

- The `hidapi` Python package (`pip install hidapi`, imported as `hid`) talks
  to HID devices via the **native Windows HID API**, not `libusb`/`WinUSB`.
  This matters: `libusb`-based access (as used elsewhere in this repo, in
  `usb_util.py`) requires rebinding a device's driver to `WinUSB`, which
  would break `lighthouse_console`'s and SteamVR's own (native-HID-driver)
  access to the same device. `hidapi` needs no such rebind.
- **Confirmed safe to use alongside SteamVR/`lighthouse_console`.** Windows'
  HID class driver supports concurrent shared-read access; this is also the
  Valve-documented workflow (community guidance: open `lighthouse_console`,
  run `dongleinfo`, *then* start SteamVR while it's still open). Verified
  directly: with a background `hidapi` reader continuously open on a dongle,
  a concurrent `lighthouse_console` session against the *same* dongle still
  got a correct battery reading, with no errors on either side.
- **A connected wireless device streams HID input reports continuously**
  (report IDs `0x23`/`0x24`, matching what `libsurvive`'s `driver_vive.c`
  documents as `VIVE_REPORT_RF_WATCHMAN(x2)` telemetry packets) at roughly
  100-190Hz. An unconnected dongle is completely silent. Presence/absence of
  this stream is a reliable, essentially-instant connect/disconnect signal
  that needs zero protocol decoding.
- Live-tested end to end: turning a tracker off was detected after ~1s
  (the deliberate silence buffer, to absorb natural gaps in the stream
  without misreading them as a power-off); turning it back on was detected
  effectively instantly (first packet in = connected).

### Which VID/PID to watch

Two USB PIDs both represent legitimate wireless-pairing-capable dongles
under Valve's vendor ID (`0x28DE`):

- `0x2101` - standalone "Watchman Dongle" units.
- `0x2102` - an HMD's *built-in* radios (e.g. a Valve Index has two onboard
  radios, serials ending in `LYM`/`RYB`). These exist specifically to pair
  the Index's own controllers, wirelessly, in addition to whatever
  standalone dongles are plugged in - they are not merely "the headset's
  connection" and must not be excluded from live watching. (This app
  separately categorizes `LYM`/`RYB`-suffixed serials as `"hmd"` for
  *display* purposes - i.e. which icon/name to show - but that categorization
  is unrelated to whether the dongle can host a live controller pairing, and
  the watcher intentionally ignores it.)

Both PIDs were confirmed to emit the same `0x23`/`0x24` report stream.
`DongleWatcher._run()` tries `0x2101` then `0x2102` when opening a given
dongle serial.

## Resulting architecture

`DongleWatcher` (one per dongle, background daemon thread):

1. Open the dongle non-exclusively via `hidapi`.
2. Poll `read()` in a tight non-blocking loop. Reports arriving = connected;
   more than `DISCONNECT_SILENCE_SECONDS` (1.0s) of silence after having been
   connected = disconnected.
3. On a transition to connected (a rare event, not the steady state), make
   one `query_paired_device()` call - a single `lighthouse_console`
   subprocess running `serial <dongle>\ndownloadconfig <tmpfile>\nbattery\nquit\n`
   - to resolve the paired device's own serial, battery %, and device class,
   then read+delete the temp JSON config file.
4. Report state changes back to the UI thread via `App.after(0, ...)`, since
   Tk widgets aren't safe to touch directly from a background thread.

Net effect: sub-second change detection with near-zero idle overhead
(a tight non-blocking read loop, no process spawning while idle), only
paying the ~1-3s `lighthouse_console` cost on an actual connect event.
