"""Builds the Windows programs with PyInstaller.

python build.py            release: two one-file exe in dist/ and DotaDraft-windows.zip
python build.py --debug    debug: a folder with the exe and its libraries, the window keeps a console for errors
"""

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def pyinstaller(script, name, *options):
    command = [sys.executable, "-m", "PyInstaller", str(ROOT / script), "--name", name, "--noconfirm", "--clean",
               "--distpath", str(DIST), "--workpath", str(BUILD), "--specpath", str(BUILD), *options]
    print(">", " ".join(command[2:]))
    subprocess.run(command, check=True)


def release():
    common = ["--onefile", "--optimize", "1", "--exclude-module", "pytest"]
    pyinstaller("main.py", "DotaDraft", "--windowed", *common)
    pyinstaller("main_console.py", "DotaDraft-console", "--console", "--exclude-module", "tkinter", *common)
    archive = DIST / "DotaDraft-windows.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in ("DotaDraft.exe", "DotaDraft-console.exe"):
            zip_file.write(DIST / name, name)
        zip_file.write(ROOT / "README.md", "README.md")
    print("ready:", archive)


def debug():
    pyinstaller("main.py", "DotaDraft-debug", "--onedir", "--console")
    print("ready:", DIST / "DotaDraft-debug")


def main(argv):
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing: python -m pip install pyinstaller")
        return 1
    if DIST.exists():
        shutil.rmtree(DIST)
    if "--debug" in argv:
        debug()
    else:
        release()
    shutil.rmtree(BUILD, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
