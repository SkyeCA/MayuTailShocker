# Mayu Tail Shocker

![The program icon](/resources/icon.png)

## Overview
This is a Python based application created to send random shock commands to OpenShock shockers when the tail
of a Mayu* is pulled.

__This project is not currently PiShock compatible!__

\* This will work on any avatar with a PhysBone that can be grabbed and pulled, but additional setup might be
required for your avatar and to this program's configuration.

## Releases

You can find the latest pre-built versions of this program and a Unity prefab for in game control on the [releases page](https://github.com/SkyeCA/MayuTailShocker/releases).

## Requirements

### 1. Software Dependencies
*   **Python 3.x** installed on your system.
*   The following Python packages:
    *   `python-osc`
    *   `requests`

### 2. OpenShock Requirements
*   An **OpenShock API Token**.
*   The **Shocker IDs** for the shockers you intend to control.

### 3. VRChat Requirements
*   OSC enabled in the VRChat radial menu (Options -> OSC -> Enabled).
*   An avatar configured with a PhysBone on the tail, set up with `_IsGrabbed` and `_Stretch` parameters and the ability to be grabbed and stretched.

### Physbone Parameter Setup

![Physbone Setup](/resources/physbone_setup.jpg)

## Desktop App

### How to Run 

To run the program from source:
1. Open your terminal or command prompt.
2. Install the required dependencies:
   ```bash
   pip install requests python-osc
   ```
3. Run the script:
   ```bash
   python tail_shocker.py
   ```

### How to Build

To compile a standalone executable from source:

1. Install PyInstaller (pip install pyinstaller).
2. Run the provided build.bat file in the project directory to automatically compile the application.

## Screenshots

![A screenshot of the program running](/resources/sreenshot.jpg)

## Avatar Control Prefab

### Avatar Setup

1. Download the newest Mayu Tail Shocker prefab from the releases page.
2. Ensure your project has VRCFury installed.
3. Import the Mayu Tail Shocker Unity package into your project.
4. Drag the prefab directly onto your avatar's root in the project hierarchy.

### How to Use

![A screenshot of the in game control](/resources/menu.jpg)

The prefab for this project adds a set of options to the VRC radial menu for controlling application settings. These options are placed in a submenu called "Mayu Tail Shocker" by default.

Options:

- __Enable:__ Enables or disables the application. When disabled no shocks will occur.
- __Vibrate Only:__ Enables or disables vibration only mode. When enabled the shocker will vibrate, but not shock the user.
- __Dynamic Mode:__ Enables or disables the shock intensity and duration based on the stretch amount of the tail/physbone.
- __Max Intensity:__ The maximum intensity the user can be shocked from 0% to 100%.
- __Max Duration:__ The maximum length of time a single shock can shock the user. Does not apply in dynamic mode. Range is 0 to 10 seconds, with each 1% being 100ms (10% is 1 second).
- __Cooldown:__ The time after a shock before another shock can occur. Does not apply in dynamic mode. Range is 0 to 10 seconds, with each 1% being 100ms (10% is 1 second).

## Third Party Resources

- Program icon: https://www.flaticon.com/free-icon/flash_657908
- Enable icon: https://www.flaticon.com/free-icon/power-switch_4139573
- Vibrate icon: https://www.flaticon.com/free-icon/ring_14533511
- Dynamic icon: https://www.flaticon.com/free-icon/line-graph_920199
- Intensity icon: https://www.flaticon.com/free-icon/thermostat_4117629
- Duration icon: https://www.flaticon.com/free-icon/hourglass_786017
- Cooldown icon: https://www.flaticon.com/free-icon/yield_678594

## AI Disclaimer

AI was used to create some parts of this project however I have personally tested everything and addressed edge cases where required.

If you have an issue with this please do no not contact me.

## Contact Me

You can find my contact information here: http://vore.my