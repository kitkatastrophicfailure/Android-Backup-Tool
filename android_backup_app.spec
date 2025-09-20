# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['android_backup_app.pyw'],
    pathex=[],
    binaries=[],
    datas=[
        ('adb.exe', '.'),
        ('AdbWinApi.dll', '.'),
        ('AdbWinUsbApi.dll', '.')
    ],
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
    name='android_backup_app',
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
    # --- Minor correction for consistency ---
    icon='android.png',
    manifest='admin.manifest',
)