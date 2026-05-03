# -*- mode: python ; coding: utf-8 -*-
import os

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src')],
    hiddenimports=[
        'scipy.special._ufuncs',
        'scipy.special._specfun',
        'scipy.special._comb',
        'skimage',
        'skimage.metrics',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# faster-whisper runtime files
from PyInstaller.utils.hooks import collect_all
for item in collect_all('faster_whisper'):
    if isinstance(item, tuple) and len(item) == 3:
        typ = item[2]
        if typ == 'DATA':
            a.datas += [item]
        elif typ == 'BINARY':
            a.binaries += [item]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Video-Distiller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Video-Distiller',
)
