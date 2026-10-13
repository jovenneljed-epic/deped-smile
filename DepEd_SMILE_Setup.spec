# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['installer_wizard.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/Client/.gemini/antigravity/scratch/project_smile/dist/DepEd_SMILE.exe', 'dist'), ('C:/Users/Client/.gemini/antigravity/scratch/project_smile/favicon.ico', '.'), ('C:/Users/Client/.gemini/antigravity/scratch/project_smile/desktop_config.json', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DepEd_SMILE_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='C:/Users/Client/.gemini/antigravity/scratch/project_smile/version_info.txt',
    icon=['C:/Users/Client/.gemini/antigravity/scratch/project_smile/favicon.ico'],
)
