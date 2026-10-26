# CLAUDE.md

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
