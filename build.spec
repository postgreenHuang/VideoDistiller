# -*- mode: python ; coding: utf-8 -*-
import os
import sys

# faster-whisper runtime files — 必须在 Analysis 之前收集
from PyInstaller.utils.hooks import collect_all
fw_datas, fw_binaries, fw_hiddenimports = collect_all('faster_whisper')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=fw_binaries,
    datas=[('src', 'src'), ('icon.ico', '.')] + fw_datas,
    hiddenimports=[
        'scipy.special._ufuncs',
        'scipy.special._specfun',
        'scipy.special._comb',
        'scipy.stats._distn_infrastructure',
        'skimage',
        'skimage.metrics',
    ] + fw_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['nltk', 'scipy.stats.distributions'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Video-Distiller',
    icon='icon.ico',
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
        icon='icon.ico',
        bundle_identifier='com.videodistiller.app',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '2.0.0',
        },
    )
