# Mayu Tail Shocker

![The program icon](/resources/icon.png)

## Overview
This is a Python based application created to send random shock commands to an OpenShock shocker when the tail
of a Mayu* is pulled.

__This project is not currently PiShock compatible!__

* This will work on any avatar with a PhysBone that can be grabbed and pulled, but additional setup might be
required on your avatar and to this program's configuration.

## Requirements

### 1. Software Dependencies
*   **Python 3.x** installed on your system.
*   The following Python packages:
    *   `python-osc`
    *   `requests`

### 2. OpenShock Requirements
*   An **OpenShock API Token**.
*   The **Shocker ID** for the specific shocker you intend to control.

### 3. VRChat Requirements
*   OSC enabled in the VRChat radial menu (Options -> OSC -> Enabled).
*   An avatar configured with a PhysBone on the tail, set up with `_IsGrabbed` and `_Stretch` parameters and the ability to be grabbed and stretched.

## Setup and Installation

1.  Clone this repo.
2.  **Install dependencies:** Open a terminal, change to the project directory, and run:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure API credentials:**
    *   Open `tail_shocker.py` in a text editor.
    *   Locate the `CONFIGURATION` section at the top of the file.
    *   Replace `"YOUR_API_KEY_HERE"` with your actual OpenShock API token.
    *   Replace `"YOUR_SHOCKER_ID_HERE"` with your specific OpenShock device ID.
    *   Save and close the file.

*(Optional)* If your VRChat avatar uses different parameter names, update the `PARAM_GRABBED` and `PARAM_STRETCH` variables in the configuration block to match your avatar's paths.

## Usage

1.  Start the application by running the script from your terminal:
    ```bash
    python tail_shocker.py
    ```
2.  Adjust the safety caps using the provided sliders:
    *   **Maximum Allowed Intensity:** Sets the upper percentage limit for the random intensity calculation.
    *   **Maximum Allowed Duration:** Sets the upper time limit (in seconds) for the random duration calculation.
    *   **Cooldown Between Events:** Sets a mandatory waiting period before another command can be sent.
3.  **Test Mode:** By default, the application starts with "Test Mode" enabled. This sends safe "Vibrate" commands to your device instead of shocks. Uncheck the box to enable live shocks.
4.  **Disable/Enable Button:** Click the red "Disable" button at any time to immediately send a halt command to the OpenShock API and disable further events. Click it again to re-enable the system.

## Screenshots

![A screenshot of the program running](/resources/sreenshot.jpg)

## Third Party Resources

Program icon: https://www.flaticon.com/free-icon/flash_657908

## Contact Me

You can find my contact information here: http://vore.my