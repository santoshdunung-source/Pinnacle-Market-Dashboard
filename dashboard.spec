# PyInstaller spec — bundles Python + every dependency into one standalone
# executable, so running the dashboard needs nothing pre-installed at all.
#
# Build (run on the target OS — PyInstaller does not cross-compile):
#   pip install pyinstaller
#   pyinstaller dashboard.spec
#
# Output: dist/Pinnacle Dashboard(.exe on Windows) — a single file, copy it
# anywhere and double-click it. No Python, no pip, nothing else needed.

import sys

block_cipher = None

a = Analysis(
    ["run_dashboard.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("static", "static"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "yfinance",
        "bs4",
        "market_data",
        "app",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Pinnacle Dashboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
