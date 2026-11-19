# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['tdms2mat/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('procesar_matlab.m', '.'),
        ('config.json', '.'),
        ('icon.ico', '.'),
        ('icon.png', '.'),
        ('tdms2mat/gui', 'tdms2mat/gui'),
    ],
    hiddenimports=[
        'tdms2mat',
        'tdms2mat.gui.app',
        'tdms2mat.pipeline.orchestrator',
        'tdms2mat.config.schema',
        'tdms2mat.config.config_utils',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'ttkbootstrap',
    ],
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
    name='TDMS2MAT',
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
    icon='icon.ico',
)
