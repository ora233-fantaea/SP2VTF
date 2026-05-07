# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\dev\\sp_to_vtf_v1.0.4.py'],
    pathex=[],
    binaries=[],
    datas=[('tape-x64.png', '.')],
    hiddenimports=['PySide6'],
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
    name='SP2VTF_v1.0.4',
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
)
