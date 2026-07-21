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

## How to Run 

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

## How to Build

To compile a standalone executable from source:

1. Install PyInstaller (pip install pyinstaller).
2. Run the provided build.bat file in the project directory to automatically compile the application.

## Avatar Setup


1. Download the newest Mayu Tail Shocker prefab from the releases page.
2. Ensure your project has VRCFury installed.
3. Import the Mayu Tail Shocker Unity package into your project.
4. Drag the prefab directly onto your avatar's root in the project hierarchy.

## Screenshots

![A screenshot of the program running](/resources/sreenshot.jpg)

## Third Party Resources

Program icon: https://www.flaticon.com/free-icon/flash_657908

## Contact Me

You can find my contact information here: http://vore.my