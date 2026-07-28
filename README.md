# Mayu Tail Shocker

A Python desktop app that sends random shock commands to your OpenShock shockers when your Mayu's* tail is grabbed and pulled.

> [!WARNING]
> This project is **not** currently PiShock compatible.

\* Works with any avatar that has a PhysBone which can be grabbed and stretched — some extra setup on your avatar and in this program's config may be required.

## Contents

- [Releases](#releases)
- [Requirements](#requirements)
- [Desktop App](#desktop-app)
- [Avatar Control Prefab](#avatar-control-prefab)
- [Third Party Resources](#third-party-resources)
- [Screenshots](#screenshots)

## Releases

Pre-built versions of the desktop app and the Unity prefab for in-game control are on the [releases page](https://github.com/SkyeCA/MayuTailShocker/releases).

## Requirements

### Software Dependencies
- **Python 3.x**
- Python packages: `python-osc`, `requests`

### OpenShock
- An **OpenShock API Token**
- The **Shocker IDs** for the shockers you want to control

### VRChat
- OSC enabled (Options → OSC → Enabled)
- An avatar with a tail PhysBone that can be grabbed and stretched, exposing `_IsGrabbed` and `_Stretch` parameters

### Physbone Parameter Setup

![Physbone Setup](/resources/physbone_setup.jpg)

## Desktop App

### Running from Source

With [uv](https://github.com/astral-sh/uv) (handles the virtual environment for you):
```bash
uv run python tail_shocker.py
```

With pip:
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   python tail_shocker.py
   ```

> [!TIP]
> If using pip, a virtual environment (`venv`) is recommended when running from source.

### Building

Run `build.bat` in the project directory to compile a standalone executable.

### Running Tests

The `tests/` folder contains a unit test suite covering config loading/saving, the OpenShock API client, session/shock-log persistence, and the OSC bridge. It only uses the standard library, so no extra install is needed:

```bash
python -m unittest discover -v
# or, with uv:
uv run python -m unittest discover -v
```

## Avatar Control Prefab

### Setup

1. Download the latest Mayu Tail Shocker prefab from the [releases page](https://github.com/SkyeCA/MayuTailShocker/releases).
2. Make sure your project has VRCFury installed.
3. Import the Mayu Tail Shocker Unity package.
4. Drag the prefab onto your avatar's root in the hierarchy.

### Usage

![A screenshot of the in game control](/resources/menu.jpg)

The prefab adds a submenu to the VRC radial menu (named "Mayu Tail Shocker" by default) with these options:

| Option | Description |
|---|---|
| **Enable** | Turns the application on or off. No shocks occur while disabled. |
| **Vibrate Only** | When enabled, the shocker vibrates instead of shocking. |
| **Dynamic Mode** | Sets shock intensity and duration automatically from the tail's grab state and stretch amount. |
| **Max Intensity** | Maximum shock intensity, 0–100%. |
| **Max Duration** | Maximum length of a single shock. Not used in Dynamic Mode. Range is 0–10s, where each 1% = 100ms (10% = 1s). OpenShock's minimum shock duration is 300ms, so 1–3% all trigger a 300ms shock. |
| **Cooldown** | Time after a shock before another can occur. Not used in Dynamic Mode. Same 1% = 100ms scale as Max Duration. |

## Third Party Resources

- [Program icon](https://www.flaticon.com/free-icon/flash_657908)
- [Enable icon](https://www.flaticon.com/free-icon/power-switch_4139573)
- [Vibrate icon](https://www.flaticon.com/free-icon/ring_14533511)
- [Dynamic icon](https://www.flaticon.com/free-icon/line-graph_920199)
- [Intensity icon](https://www.flaticon.com/free-icon/thermostat_4117629)
- [Duration icon](https://www.flaticon.com/free-icon/hourglass_786017)
- [Cooldown icon](https://www.flaticon.com/free-icon/yield_678594)

## Screenshots

![A screenshot of the program running](/resources/screenshot.jpg)

## AI Disclaimer

AI was used to create *some* parts of this project; everything has been personally tested and edge cases have been addressed. Please don't contact me about this.

## Contact Me

[vore.my](http://vore.my)
