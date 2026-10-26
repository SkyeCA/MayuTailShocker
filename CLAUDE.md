# CLAUDE.md

## Safety rules (don't change without an explicit request)

- Shock settings (intensity, duration, cooldown, Vibrate/Shock, Random/Stretch) deliberately
  reset to the defaults in `ShockSettings` (30%, Vibrate) on every launch, and the app pushes
  them to the avatar menu on start and on avatar change. Don't persist them, and don't adopt
  the avatar's saved values at startup.
- A Stop always goes to every configured shocker, never a random one
  (`OpenShockClient._target_ids`).
- Disabling and closing the app both send a Stop. OpenShock requests go out one at a time
  (`ShockEngine._send_lock`), so a Stop can't be overtaken by a shock already on its way, and
  a shock still waiting when the system is disabled is dropped.
- Cooldown runs from when a shock is estimated to *end* (send time + duration), not from when
  it starts.

## Known issues (not fixed yet)

From a code review in October 2026. These were deliberately left for later.

### Stretch mode needs a transport rework (do this later)

Stretch mode sends a 400 ms command every 200 ms, each as a blocking `requests.post` on a
fresh HTTPS connection (`dynamic_shock_loop`, `OpenShockClient.send`). Consequences:

- Each iteration takes 0.2 s plus the request time, so above roughly 200 ms latency there are
  gaps between pulses.
- The "one shock per second held" count assumes exactly 0.2 s per iteration, so it undercounts.
- In "One at random" mode every pulse picks a new shocker, so one pull hops between them.

Look at WebSockets for this when reworking. OpenShock has a realtime "live control" WebSocket
and a SignalR hub for user events; its C# SDK wraps them as `OpenShock.SDK.CSharp.Live` and
`OpenShock.SDK.CSharp.Hub` (https://github.com/OpenShock/SDK.CSharp). Check the API docs for
the protocol and whether it's usable from Python before committing to it. A
`requests.Session` (connection reuse) would be a cheaper partial fix.

### Possible hang on close (unconfirmed)

`EngineListener` callbacks call `root.after()` from the OSC thread, and `_tkinter` makes that
thread wait until the Tk thread runs the call. `ShockEngine.shutdown` ends with `osc.stop()`,
which blocks the Tk thread until the OSC thread's serve loop exits. If an OSC handler is in a
listener call at that moment, each waits for the other and the window never closes. It needs
a UI-touching message (triggered shock, menu change, avatar change) within ~0.5 s of closing,
so it's rare. It was found by reading CPython's `_tkinter`, not observed. The Stop and the
shock stats happen before `osc.stop()`, so even then the shockers are stopped. Fix if it's
ever seen: have listeners push onto a `queue.Queue` that the Tk thread drains from its 100 ms
`_poll_tail` loop, so no other thread calls into Tk.

### Lower priority

- Shock count: the Stretch loop counts shocks even with no API token configured (only
  `trigger_shock` checks `client.is_configured`); `is_real_shock` is fixed when the loop
  starts, so switching Vibrate/Shock mid-pull miscounts; both modes count attempts, not
  successful sends.
- `load_config` only guards JSON syntax. A hand-edited file with wrong types (e.g.
  `"shocker_ids": "abc"`) or a top-level list crashes at startup, as can the legacy-migration
  `save()` there.
- `config.json` is written non-atomically, unlike `session_state.json`.
- Data file paths come from `sys.argv[0]`, but `resource_path` uses the current directory, so
  they disagree when launched from elsewhere; `sys.executable` is the reliable choice when
  frozen. Writing next to the exe also fails if it's installed in Program Files (consider
  `%APPDATA%`).
- The OSC ports (9001 listen / 9000 send) are hardcoded, with no setting and no OSCQuery.
- On Python 3.9 (allowed by `requires-python`), uv/pip resolve python-osc 1.8.3, whose
  `SimpleUDPClient` isn't a context manager, so the `with SimpleUDPClient(...)` tests in
  `tests/test_osc_bridge.py` error there. They pass on 3.10+.
- `build.bat` adds a self-signed code-signing certificate to the CurrentUser Trusted Root
  store. That gives end users no trust, but anything signed with that key is trusted on the
  build machine. It also has no `errorlevel` checks: it signs after a failed PyInstaller run,
  and the version is bumped even when the build fails.

## Design notes

- `OpenShockClient` reads the token, shocker IDs and mode straight from the live `AppConfig`.
  `ShockEngine.update_config` saves a copy first and only then applies the changes, so the
  client never sees values that failed to save. The engine talks to the client only through
  `send()` and `is_configured`. If another backend is ever added (PiShock support was
  planned once, but is dropped for the foreseeable future), keep it behind that interface.

## Under consideration (do not implement unless asked)

### SteamVR dashboard overlay

We're considering an optional "Show in SteamVR dashboard" setting that adds the app as a
SteamVR dashboard overlay, so it can be controlled from the SteamVR dashboard without
viewing the whole desktop. **This is not approved - don't start on it without an explicit
request.**

Notes from the initial assessment:

- Use the OpenVR overlay API via `pyopenvr` (`CreateDashboardOverlay`, overlay mouse
  events for laser-pointer input, a `.vrmanifest` for auto-launch with SteamVR). It should
  fail gracefully when SteamVR isn't running.
- Preferred approach: a second, VR-only front end implementing `EngineListener` against
  the same `ShockEngine` (see `mts/engine.py`), drawn with Pillow like the dials in
  `mts/controls.py`, with its own hit-testing. Scope: power switch, Output/Mode toggles,
  the three dials and status - Settings/Logs/About stay desktop-only.
- Rejected alternative: mirroring the Tk window into the overlay (screen capture plus
  synthetic input) - quicker but fragile and laggy.
- Rough estimate: 3-5 days, and it needs testing in a headset.
- Engine changes this would need: `ShockEngine` accepts a single listener, and
  `update_settings` deliberately doesn't notify about changes made from a UI (only from
  OSC), while `set_active` always notifies. With two front ends, the engine needs a list of
  listeners and must notify every change, or the desktop and VR UIs will drift apart.
