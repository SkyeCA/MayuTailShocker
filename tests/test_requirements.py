import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class RequirementsTests(unittest.TestCase):
    def test_requirements_txt_matches_pyproject(self):
        # pip/build.bat install from requirements.txt and uv from pyproject.toml, so
        # the two lists must not drift apart.
        try:
            import tomllib
        except ImportError:
            self.skipTest("tomllib needs Python 3.11+")
        with open(ROOT / "pyproject.toml", "rb") as f:
            expected = tomllib.load(f)["project"]["dependencies"]
        lines = (line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines())
        actual = [line for line in lines if line and not line.startswith("#")]
        self.assertEqual(sorted(actual), sorted(expected))


if __name__ == "__main__":
    unittest.main()
