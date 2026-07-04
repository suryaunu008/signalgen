# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Get the project directory
project_dir = os.path.abspath(SPECPATH)

# Collect all data files
datas = [
    (os.path.join(project_dir, 'app', 'ui', 'templates'), 'app/ui/templates'),
    (os.path.join(project_dir, 'app', 'ui', 'static'), 'app/ui/static'),
    (os.path.join(project_dir, 'static', 'favicon.ico'), 'static'),
]

binaries = []

# Hidden imports for packages that are dynamically imported
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'engineio.async_drivers.aiohttp',
    'socketio',
    'aiohttp',
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'pythonnet',
    'clr_loader',
    'ta',
    'talib',
    'talib.stream',
    'pandas',
    'numpy',
    'yfinance',
    'ib_insync',
    'sqlite3',
    'multiprocessing',
    'multiprocessing.pool',
]

# PyWebView on Windows can load pythonnet/clr_loader dynamically. Collecting
# these packages explicitly keeps Python.Runtime.dll and native CLR loader files
# in the frozen app when moving it to another PC.
for package_name in ('webview', 'pythonnet', 'clr_loader'):
    try:
        package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports
    except Exception as exc:
        print(f"WARNING: Could not collect PyInstaller files for {package_name}: {exc}")

a = Analysis(
    [os.path.join(project_dir, 'app', 'main.py')],
    pathex=[project_dir],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SignalGen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No console window for desktop app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(project_dir, 'static', 'favicon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SignalGen',
)
