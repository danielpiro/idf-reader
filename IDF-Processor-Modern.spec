# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['modern_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('settings.json', '.'), ('data', 'data'), ('parsers', 'parsers'), ('generators', 'generators'), ('utils', 'utils')],
    hiddenimports=['flet', 'asyncio', 'eppy', 'reportlab', 'parsers', 'generators', 'utils', 'utils.path_utils', 'utils.logging_config', 'utils.data_loader', 'processing_manager', 'idf_code_cleaner'],
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
    name='IDF-Processor-Modern',
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
    uac_admin=True,
)
