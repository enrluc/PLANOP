"""Entry point for the PyInstaller-bundled backend (desktop mode).

Starts uvicorn against server.app, honoring HOST/PORT env vars set by Electron.
"""
import os
import sys
import uvicorn


def main() -> int:
    # Ensure our own directory is on sys.path (PyInstaller onedir layout).
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    if here not in sys.path:
        sys.path.insert(0, here)

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8001"))

    # Force LOCAL_MODE if the launcher is used, unless explicitly disabled.
    os.environ.setdefault("LOCAL_MODE", "true")

    # Import late so env vars are set first.
    from server import app  # type: ignore

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
