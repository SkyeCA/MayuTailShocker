import os
import sys

OSC_IP = "127.0.0.1"
OSC_PORT = 9001
OSC_SEND_PORT = 9000

# Legacy avatar parameters (physbone grab/stretch)
DEFAULT_PARAM_GRABBED = "/avatar/parameters/Tail/_IsGrabbed"
DEFAULT_PARAM_STRETCH = "/avatar/parameters/Tail/_Stretch"

# In-game control parameters (MTS_* menu)
MTS_ENABLE = "/avatar/parameters/MTS_Enable"
MTS_VIBRATE = "/avatar/parameters/MTS_VibrateMode"
MTS_DYNAMIC = "/avatar/parameters/MTS_DynamicMode"
MTS_INTENSITY = "/avatar/parameters/MTS_MaxIntensity"
MTS_DURATION = "/avatar/parameters/MTS_MaxDuration"
MTS_COOLDOWN = "/avatar/parameters/MTS_Cooldown"

CONFIG_FILE = os.path.join(os.path.dirname(sys.argv[0]), "config.json")
SHOCK_LOG_FILE = os.path.join(os.path.dirname(sys.argv[0]), "shock_log.txt")
USER_AGENT = "MayuTailShocker/1.0 (skye@vore.my)"

GITHUB_URL = "https://github.com/SkyeCA/MayuTailShocker"
ABOUT_URL = "https://vore.my"


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
