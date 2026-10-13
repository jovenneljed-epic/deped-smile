"""
DepEd Project S.M.I.L.E. - Windows Setup Installer Builder
===========================================================
Compiles the installer wizard and embeds DepEd_SMILE.exe into
a single distribution setup installer: dist/DepEd_SMILE_Setup.exe
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
APP_EXE = os.path.join(DIST_DIR, "DepEd_SMILE.exe")
ICON_PATH = os.path.join(BASE_DIR, "favicon.ico")
CONFIG_PATH = os.path.join(BASE_DIR, "desktop_config.json")
VERSION_FILE = os.path.join(BASE_DIR, "version_info.txt")

def main():
    print("=" * 72)
    print("   DEPARTMENT OF EDUCATION - PROJECT S.M.I.L.E. SETUP BUILDER")
    print("=" * 72)

    if not os.path.exists(APP_EXE):
        print(f"[!] Error: {APP_EXE} not found.")
        print("    Please compile the desktop app first using: python build_desktop_exe.py")
        sys.exit(1)

    print(f" [*] Bundling application binary: {APP_EXE}")
    print(f" [*] Target Setup Executable:     dist/DepEd_SMILE_Setup.exe")
    print("-" * 72)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name=DepEd_SMILE_Setup",
        f"--icon={ICON_PATH}",
        f"--add-data={APP_EXE};dist",
        f"--add-data={ICON_PATH};.",
        f"--add-data={CONFIG_PATH};.",
    ]
    if os.path.exists(VERSION_FILE):
        cmd.append(f"--version-file={VERSION_FILE}")
    cmd.append("installer_wizard.py")

    print(f" [*] Running PyInstaller for Setup Installer...\n")
    ret = subprocess.run(cmd, cwd=BASE_DIR)

    if ret.returncode != 0:
        print(f"\n[!] Setup compilation failed with code {ret.returncode}")
        sys.exit(ret.returncode)

    setup_exe = os.path.join(DIST_DIR, "DepEd_SMILE_Setup.exe")
    if os.path.exists(setup_exe):
        size_mb = os.path.getsize(setup_exe) / (1024 * 1024)
        print("\n" + "=" * 72)
        print(" [SUCCESS] DepEd S.M.I.L.E. Windows Setup Installer Ready!")
        print(f"  - Setup Executable: {setup_exe}")
        print(f"  - Setup Size:       {size_mb:.2f} MB")
        print("  - Features:         GUI Setup Wizard, Desktop Icon, Start Menu, Add/Remove Programs")
        print("=" * 72)
    else:
        print(f"\n[!] Error: {setup_exe} not found in dist/")
        sys.exit(1)

if __name__ == "__main__":
    main()
