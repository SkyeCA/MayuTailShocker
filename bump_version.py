"""Bumps the patch version in mts/version.py and mirrors it into version_info.txt.

Run before building (see build.bat). Prints the new version to stdout.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "mts" / "version.py"
VERSION_INFO_FILE = ROOT / "version_info.txt"

VERSION_RE = re.compile(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"')


def read_version():
    match = VERSION_RE.search(VERSION_FILE.read_text())
    if not match:
        raise SystemExit(f"Could not find __version__ in {VERSION_FILE}")
    return tuple(int(part) for part in match.groups())


def write_version(major, minor, patch):
    version_str = f"{major}.{minor}.{patch}"
    tuple_str = f"({major}, {minor}, {patch}, 0)"

    VERSION_FILE.write_text(VERSION_RE.sub(f'__version__ = "{version_str}"', VERSION_FILE.read_text()))

    info_text = VERSION_INFO_FILE.read_text()
    info_text = re.sub(r"filevers=\(\d+, \d+, \d+, \d+\)", f"filevers={tuple_str}", info_text)
    info_text = re.sub(r"prodvers=\(\d+, \d+, \d+, \d+\)", f"prodvers={tuple_str}", info_text)
    info_text = re.sub(r"StringStruct\('FileVersion', '[^']*'\)", f"StringStruct('FileVersion', '{version_str}')", info_text)
    info_text = re.sub(r"StringStruct\('ProductVersion', '[^']*'\)", f"StringStruct('ProductVersion', '{version_str}')", info_text)
    VERSION_INFO_FILE.write_text(info_text)


def main():
    major, minor, patch = read_version()
    patch += 1
    write_version(major, minor, patch)
    print(f"{major}.{minor}.{patch}")


if __name__ == "__main__":
    main()
