# -*- mode: python ; coding: utf-8 -*-
import os
import sys

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('src', 'src')],
    hiddenimports=[
        'scipy.special._ufuncs',
        'scipy.special._specfun',
        'scipy.special._comb',
        'scipy.stats._distn_infrastructure',
        'skimage',
        'skimage.metrics',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['nltk', 'scipy.stats.distributions'],
    noarchive=False,
)

# faster-whisper runtime files
from PyInstaller.utils.hooks import collect_all
fw_datas, fw_binaries, fw_hiddenimports = collect_all('faster_whisper')
a.datas += fw_datas
a.binaries += fw_binaries
a.hiddenimports += fw_hiddenimports

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

# macOS: 生成 .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Video-Distiller.app',
        icon=None,
        bundle_identifier='com.videodistiller.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '2.0.0',
        },
    )
