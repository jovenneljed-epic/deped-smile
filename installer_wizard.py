"""
DepEd Project S.M.I.L.E. - Native Windows Setup Installer Wizard
================================================================
A native Windows installation wizard for DepEd Project S.M.I.L.E.
Installs DepEd_SMILE.exe, configures shortcuts (Desktop & Start Menu),
and registers the app in Windows "Installed Apps / Add or Remove Programs".
"""

import os
import sys
import shutil
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Resolve payload directory (source vs PyInstaller bundle)
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_INSTALL_NAME = "DepEd SMILE"
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
DEFAULT_INSTALL_DIR = os.path.join(LOCAL_APP_DATA, "Programs", DEFAULT_INSTALL_NAME)
APP_TITLE = "DepEd Project S.M.I.L.E. Setup"


def create_windows_shortcut(target_path, shortcut_path, icon_path=None, description=""):
    """Creates a native Windows .lnk shortcut using PowerShell WScript.Shell."""
    try:
        ps_script = f"""
        $WshShell = New-Object -ComObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "{target_path}"
        $Shortcut.WorkingDirectory = "{os.path.dirname(target_path)}"
        $Shortcut.Description = "{description}"
        """
        if icon_path and os.path.exists(icon_path):
            ps_script += f'\n$Shortcut.IconLocation = "{icon_path},0"'
        ps_script += '\n$Shortcut.Save()'

        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return True
    except Exception as e:
        print(f"[!] Shortcut error: {e}")
        return False


def register_uninstall_in_registry(install_dir, exe_path, icon_path):
    """Registers the application into Windows Add/Remove Programs (HKCU)."""
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DepEd_SMILE"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "DepEd Project S.M.I.L.E.")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "2.0.0")
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "Department of Education")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, install_dir)
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, icon_path)
            uninst_cmd = f'cmd.exe /c "{os.path.join(install_dir, "uninstall.bat")}"'
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninst_cmd)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 25000)
    except Exception as e:
        print(f"[!] Registry registration note: {e}")


def write_uninstaller_script(install_dir):
    """Generates an uninstaller batch script that cleans up files, shortcuts, and registry."""
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    start_menu = os.path.join(os.environ.get("APPDATA", ""), "Microsoft\\Windows\\Start Menu\\Programs\\DepEd Project SMILE")
    desktop_shortcut = os.path.join(desktop, "DepEd S.M.I.L.E..lnk")

    uninst_content = f"""@echo off
title DepEd Project S.M.I.L.E. Uninstaller
echo ======================================================================
echo    UNINSTALLING DEPED PROJECT S.M.I.L.E.
echo ======================================================================
echo.
echo Removing Desktop shortcut...
if exist "{desktop_shortcut}" del /f /q "{desktop_shortcut}"

echo Removing Start Menu folder...
if exist "{start_menu}" rmdir /s /q "{start_menu}"

echo Cleaning Registry records...
reg delete "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\DepEd_SMILE" /f >nul 2>&1

echo Removing application directory...
cd /d "%TEMP%"
rmdir /s /q "{install_dir}" >nul 2>&1

echo.
echo [OK] DepEd Project S.M.I.L.E. has been successfully uninstalled.
timeout /t 3 >nul
exit
"""
    uninst_path = os.path.join(install_dir, "uninstall.bat")
    try:
        with open(uninst_path, "w", encoding="utf-8") as f:
            f.write(uninst_content)
    except Exception:
        pass


class SetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("640x480")
        self.resizable(False, False)
        self.configure(bg="#F8FAFC")

        self.install_dir_var = tk.StringVar(value=DEFAULT_INSTALL_DIR)
        self.cb_desktop_var = tk.BooleanVar(value=True)
        self.cb_startmenu_var = tk.BooleanVar(value=True)
        self.cb_launch_var = tk.BooleanVar(value=True)

        self.current_step = 1

        self._setup_ui()
        self._show_step(1)

    def _setup_ui(self):
        # Header Banner (Navy & Gold)
        self.header = tk.Frame(self, bg="#050B14", height=80)
        self.header.pack(fill=tk.X, side=tk.TOP)
        self.header.pack_propagate(False)

        self.lbl_head_title = tk.Label(
            self.header, text="DepEd Project S.M.I.L.E. Setup",
            font=("Segoe UI", 14, "bold"), fg="#FCD116", bg="#050B14"
        )
        self.lbl_head_title.pack(anchor="w", padx=24, pady=(16, 2))

        self.lbl_head_sub = tk.Label(
            self.header, text="Smart Monitoring & Intelligent Learner Engagement",
            font=("Segoe UI", 9), fg="#94A3B8", bg="#050B14"
        )
        self.lbl_head_sub.pack(anchor="w", padx=24)

        # Content Area
        self.content_frame = tk.Frame(self, bg="#F8FAFC")
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=28, pady=20)

        # Footer Bottom Bar with Buttons
        self.footer = tk.Frame(self, bg="#E2E8F0", height=60)
        self.footer.pack(fill=tk.X, side=tk.BOTTOM)
        self.footer.pack_propagate(False)

        self.btn_cancel = tk.Button(
            self.footer, text="Cancel", font=("Segoe UI", 9),
            bg="#FFFFFF", fg="#334155", bd=1, relief=tk.SOLID, padx=16, pady=4,
            command=self.destroy
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(6, 24), pady=14)

        self.btn_next = tk.Button(
            self.footer, text="Next >", font=("Segoe UI", 9, "bold"),
            bg="#0038A8", fg="#FFFFFF", bd=0, padx=20, pady=5,
            cursor="hand2", command=self._on_next
        )
        self.btn_next.pack(side=tk.RIGHT, pady=14)

        self.btn_back = tk.Button(
            self.footer, text="< Back", font=("Segoe UI", 9),
            bg="#FFFFFF", fg="#334155", bd=1, relief=tk.SOLID, padx=16, pady=4,
            command=self._on_back
        )
        self.btn_back.pack(side=tk.RIGHT, padx=6, pady=14)

    def _clear_content(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _show_step(self, step):
        self.current_step = step
        self._clear_content()

        if step == 1:
            self.btn_back.config(state=tk.DISABLED)
            self.btn_next.config(text="Next >", state=tk.NORMAL)
            self.btn_cancel.config(text="Cancel")

            tk.Label(
                self.content_frame, text="Welcome to DepEd Project S.M.I.L.E. Setup",
                font=("Segoe UI", 12, "bold"), fg="#0F172A", bg="#F8FAFC"
            ).pack(anchor="w", pady=(10, 8))

            msg = (
                "This setup wizard will install DepEd Project S.M.I.L.E. Standalone Desktop Client "
                "on your Windows computer.\n\n"
                "Key Features Included:\n"
                " • Real-time two-way cloud sync with https://deped-smile.vercel.app\n"
                " • Hardware-accelerated Microsoft Edge WebView2 display\n"
                " • RFID Gate scanner auto-capture, AI facial verification & hotkeys\n"
                " • Dedicated desktop icon and Start Menu access without browser bars\n\n"
                "Click Next to continue with the installation."
            )
            tk.Label(
                self.content_frame, text=msg, font=("Segoe UI", 9),
                fg="#334155", bg="#F8FAFC", justify=tk.LEFT, wraplength=570
            ).pack(anchor="w", pady=4)

        elif step == 2:
            self.btn_back.config(state=tk.NORMAL)
            self.btn_next.config(text="Next >")

            tk.Label(
                self.content_frame, text="Select Destination Location",
                font=("Segoe UI", 12, "bold"), fg="#0F172A", bg="#F8FAFC"
            ).pack(anchor="w", pady=(6, 4))

            tk.Label(
                self.content_frame, text="Where should DepEd Project S.M.I.L.E. be installed?",
                font=("Segoe UI", 9), fg="#64748B", bg="#F8FAFC"
            ).pack(anchor="w", pady=(0, 14))

            box = tk.Frame(self.content_frame, bg="#F8FAFC")
            box.pack(fill=tk.X, pady=6)

            entry = tk.Entry(
                box, textvariable=self.install_dir_var, font=("Segoe UI", 9),
                bg="#FFFFFF", fg="#0F172A", bd=1, relief=tk.SOLID
            )
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

            def _browse():
                d = filedialog.askdirectory(initialdir=self.install_dir_var.get())
                if d:
                    self.install_dir_var.set(os.path.join(d, DEFAULT_INSTALL_NAME))

            tk.Button(
                box, text="Browse...", font=("Segoe UI", 9),
                bg="#E2E8F0", fg="#0F172A", bd=1, relief=tk.SOLID, padx=12, pady=3,
                command=_browse
            ).pack(side=tk.RIGHT)

            tk.Label(
                self.content_frame, text="At least 25 MB of available disk space is required.",
                font=("Segoe UI", 8, "italic"), fg="#64748B", bg="#F8FAFC"
            ).pack(anchor="w", pady=(10, 0))

        elif step == 3:
            self.btn_back.config(state=tk.NORMAL)
            self.btn_next.config(text="Install")

            tk.Label(
                self.content_frame, text="Select Additional Tasks",
                font=("Segoe UI", 12, "bold"), fg="#0F172A", bg="#F8FAFC"
            ).pack(anchor="w", pady=(6, 4))

            tk.Label(
                self.content_frame, text="Select the additional shortcuts you would like Setup to create:",
                font=("Segoe UI", 9), fg="#64748B", bg="#F8FAFC"
            ).pack(anchor="w", pady=(0, 16))

            task_box = tk.LabelFrame(
                self.content_frame, text=" Additional Shortcuts ",
                font=("Segoe UI", 9, "bold"), fg="#0038A8", bg="#FFFFFF", padx=16, pady=12
            )
            task_box.pack(fill=tk.X, pady=4)

            tk.Checkbutton(
                task_box, text="Create a Desktop shortcut (DepEd S.M.I.L.E.)",
                variable=self.cb_desktop_var, font=("Segoe UI", 9), bg="#FFFFFF"
            ).pack(anchor="w", pady=4)

            tk.Checkbutton(
                task_box, text="Create a Start Menu program shortcut",
                variable=self.cb_startmenu_var, font=("Segoe UI", 9), bg="#FFFFFF"
            ).pack(anchor="w", pady=4)

        elif step == 4:
            # Installation Progress
            self.btn_back.config(state=tk.DISABLED)
            self.btn_next.config(state=tk.DISABLED)
            self.btn_cancel.config(state=tk.DISABLED)

            tk.Label(
                self.content_frame, text="Installing DepEd Project S.M.I.L.E...",
                font=("Segoe UI", 12, "bold"), fg="#0F172A", bg="#F8FAFC"
            ).pack(anchor="w", pady=(10, 6))

            self.lbl_status = tk.Label(
                self.content_frame, text="Preparing installation...",
                font=("Segoe UI", 9), fg="#64748B", bg="#F8FAFC"
            )
            self.lbl_status.pack(anchor="w", pady=(0, 10))

            self.progress = ttk.Progressbar(self.content_frame, mode="determinate", length=560)
            self.progress.pack(fill=tk.X, pady=10)

            self.after(200, self._perform_installation)

        elif step == 5:
            # Finish Screen
            self.btn_back.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_next.config(text="Finish", state=tk.NORMAL, command=self._on_finish)

            tk.Label(
                self.content_frame, text="Installation Complete!",
                font=("Segoe UI", 14, "bold"), fg="#10B981", bg="#F8FAFC"
            ).pack(anchor="w", pady=(16, 6))

            tk.Label(
                self.content_frame,
                text="DepEd Project S.M.I.L.E. has been successfully installed on your computer.\n\n"
                     "You can now access the standalone application from your Desktop or Start Menu.",
                font=("Segoe UI", 9), fg="#334155", bg="#F8FAFC", justify=tk.LEFT
            ).pack(anchor="w", pady=6)

            tk.Checkbutton(
                self.content_frame, text="Launch DepEd Project S.M.I.L.E. now",
                variable=self.cb_launch_var, font=("Segoe UI", 10, "bold"), fg="#0038A8", bg="#F8FAFC"
            ).pack(anchor="w", pady=(24, 0))

    def _perform_installation(self):
        target_dir = os.path.abspath(self.install_dir_var.get())
        try:
            os.makedirs(target_dir, exist_ok=True)
            self.progress["value"] = 20
            self.lbl_status.config(text=f"Copying application binaries to {target_dir}...")
            self.update_idletasks()

            # Locate payload files
            source_candidates = [
                os.path.join(BUNDLE_DIR, "dist", "DepEd_SMILE.exe"),
                os.path.join(BUNDLE_DIR, "DepEd_SMILE.exe"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "DepEd_SMILE.exe"),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "DepEd_SMILE.exe")
            ]
            src_exe = None
            for cand in source_candidates:
                if os.path.exists(cand):
                    src_exe = cand
                    break

            if not src_exe:
                raise FileNotFoundError("DepEd_SMILE.exe payload not found. Please compile the executable first.")

            # Copy Exe
            dest_exe = os.path.join(target_dir, "DepEd_SMILE.exe")
            shutil.copy2(src_exe, dest_exe)

            # Copy Icon & Config
            src_icon = os.path.join(BUNDLE_DIR, "favicon.ico")
            if not os.path.exists(src_icon):
                src_icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")
            dest_icon = os.path.join(target_dir, "favicon.ico")
            if os.path.exists(src_icon):
                shutil.copy2(src_icon, dest_icon)

            src_cfg = os.path.join(BUNDLE_DIR, "desktop_config.json")
            if not os.path.exists(src_cfg):
                src_cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_config.json")
            dest_cfg = os.path.join(target_dir, "desktop_config.json")
            if os.path.exists(src_cfg):
                shutil.copy2(src_cfg, dest_cfg)

            self.progress["value"] = 60
            self.lbl_status.config(text="Creating Desktop and Start Menu shortcuts...")
            self.update_idletasks()

            # Desktop Shortcut
            if self.cb_desktop_var.get():
                desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
                shortcut_dest = os.path.join(desktop, "DepEd S.M.I.L.E..lnk")
                create_windows_shortcut(
                    dest_exe, shortcut_dest, icon_path=dest_icon,
                    description="DepEd Project S.M.I.L.E. Desktop Client"
                )

            # Start Menu Shortcut
            if self.cb_startmenu_var.get():
                start_dir = os.path.join(
                    os.environ.get("APPDATA", ""),
                    "Microsoft\\Windows\\Start Menu\\Programs\\DepEd Project SMILE"
                )
                os.makedirs(start_dir, exist_ok=True)
                start_shortcut = os.path.join(start_dir, "DepEd Project S.M.I.L.E..lnk")
                create_windows_shortcut(
                    dest_exe, start_shortcut, icon_path=dest_icon,
                    description="DepEd Project S.M.I.L.E. Desktop Client"
                )

            self.progress["value"] = 85
            self.lbl_status.config(text="Writing uninstaller and Windows registry records...")
            self.update_idletasks()

            # Uninstaller & Registry
            write_uninstaller_script(target_dir)
            register_uninstall_in_registry(target_dir, dest_exe, dest_icon)

            self.progress["value"] = 100
            self.after(400, lambda: self._show_step(5))

        except Exception as e:
            messagebox.showerror("Installation Error", f"Failed to complete installation:\n{e}")
            self.destroy()

    def _on_next(self):
        if self.current_step < 3:
            self._show_step(self.current_step + 1)
        elif self.current_step == 3:
            self._show_step(4)

    def _on_back(self):
        if self.current_step > 1:
            self._show_step(self.current_step - 1)

    def _on_finish(self):
        if self.cb_launch_var.get():
            target_exe = os.path.join(os.path.abspath(self.install_dir_var.get()), "DepEd_SMILE.exe")
            if os.path.exists(target_exe):
                try:
                    subprocess.Popen([target_exe], cwd=os.path.dirname(target_exe))
                except Exception as e:
                    print(f"[!] Launch notice: {e}")
        self.destroy()


def main():
    app = SetupWizard()
    app.mainloop()


if __name__ == "__main__":
    main()
