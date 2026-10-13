"""
DepEd Project S.M.I.L.E. - Standalone Executable Builder
=========================================================
Builds a standalone, native Windows .exe (DepEd_SMILE.exe) using PyInstaller.
Embeds official metadata, icon, WebView2 dependencies, and config.
"""

import os
import sys
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")
ICON_PATH = os.path.join(BASE_DIR, "favicon.ico")
CONFIG_PATH = os.path.join(BASE_DIR, "desktop_config.json")
VERSION_FILE = os.path.join(BASE_DIR, "version_info.txt")

def main():
    print("=" * 72)
    print("   DEPARTMENT OF EDUCATION - PROJECT S.M.I.L.E. WINDOWS BUILDER")
    print("=" * 72)
    print(f" [*] Working Directory: {BASE_DIR}")
    print(f" [*] Target Executable: dist/DepEd_SMILE.exe")
    print(f" [*] App Icon:          {ICON_PATH}")
    print("-" * 72)

    if not os.path.exists(ICON_PATH):
        print(f"[!] Warning: {ICON_PATH} not found.")

    # Construct PyInstaller arguments
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",              # No black console window
        "--onefile",               # Single standalone executable
        f"--name=DepEd_SMILE",
        f"--icon={ICON_PATH}",
        f"--add-data={CONFIG_PATH};.",
        f"--add-data={ICON_PATH};.",
        "--hidden-import=webview",
        "--hidden-import=clr_loader",
        "--hidden-import=pythonnet",
    ]

    if os.path.exists(VERSION_FILE):
        cmd.append(f"--version-file={VERSION_FILE}")

    cmd.append("smile_desktop_app.py")

    print(f" [*] Running PyInstaller command:\n     {' '.join(cmd)}\n")
    ret = subprocess.run(cmd, cwd=BASE_DIR)

    if ret.returncode != 0:
        print(f"\n[!] Build failed with exit code {ret.returncode}")
        sys.exit(ret.returncode)

    target_exe = os.path.join(DIST_DIR, "DepEd_SMILE.exe")
    if os.path.exists(target_exe):
        size_mb = os.path.getsize(target_exe) / (1024 * 1024)
        print("\n" + "=" * 72)
        print(" [SUCCESS] Standalone Executable Created Successfully!")
        print(f"  - Output Location: {target_exe}")
        print(f"  - File Size:       {size_mb:.2f} MB")
        print("  - Features:        Windows 10/11 Native, Edge WebView2, Real-Time Cloud Sync")
        print("=" * 72)
    else:
        print(f"\n[!] Warning: Expected file {target_exe} not found in dist/")
        sys.exit(1)

if __name__ == "__main__":
    main()
