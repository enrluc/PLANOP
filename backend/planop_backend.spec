# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — builds a standalone planop-backend(.exe) that starts uvicorn
# and exposes the FastAPI app defined in server.py.
#
# Build with:
#   pyinstaller planop_backend.spec --noconfirm --clean
#
# Output goes to backend/dist/planop-backend/  (extraResources of electron-builder).

from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = []

# Packages whose data files / metadata must be bundled
_bundled = [
    'emergentintegrations',
    'uvicorn',
    'fastapi',
    'starlette',
    'anyio',
    'sniffio',
    'httpx',
    'openpyxl',
    'reportlab',
    'motor',
    'pymongo',
    'bcrypt',
    'passlib',
    'pypdf',
    'pandas',
    'numpy',
]
for pkg in _bundled:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# uvicorn workers / loops / http parsers are picked lazily -> declare them explicitly
hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'email_validator',
]

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
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
    name='planop-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='planop-backend',
)
