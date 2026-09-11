# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — builds a standalone planop-backend(.exe) that starts uvicorn
# and exposes the FastAPI app defined in server.py.
#
# Build with:
#   pyinstaller planop_backend.spec --noconfirm --clean
#
# Output goes to backend/dist/planop-backend/  (extraResources of electron-builder).

from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules

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
    'httpcore',
    'openpyxl',
    'reportlab',
    'motor',
    'pymongo',
    'bcrypt',
    'passlib',
    'pypdf',
    'anthropic',
    'dotenv',
    'pydantic',
    'pydantic_core',
    'email_validator',
    'dns',           # dnspython (pymongo SRV)
]
for pkg in _bundled:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:
        print(f"[spec] collect_all({pkg!r}) failed: {e}")
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass

# Motor / PyMongo: PyInstaller often misses async submodules -> declare them explicitly.
hiddenimports += collect_submodules('motor')
hiddenimports += collect_submodules('pymongo')
hiddenimports += collect_submodules('anthropic')
hiddenimports += collect_submodules('emergentintegrations')

# Explicit belts-and-braces list for the imports server.py performs at module level.
hiddenimports += [
    'motor',
    'motor.motor_asyncio',
    'motor.core',
    'pymongo',
    'pymongo.asynchronous',
    'pymongo.synchronous',
    'pymongo.auth',
    'pymongo.auth_aws',
    'pymongo.srv_resolver',
    'bson',
    'bson.objectid',
    'reportlab.lib.pagesizes',
    'reportlab.lib.colors',
    'reportlab.lib.units',
    'reportlab.pdfgen.canvas',
    'openpyxl',
    'openpyxl.styles',
    'pypdf',
    'httpx',
    'httpcore',
    'anthropic',
    'anthropic._client',
    'emergentintegrations.llm.chat',
    'email_validator',
    'dotenv',
]

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
]

# Deduplicate
hiddenimports = sorted(set(hiddenimports))

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
