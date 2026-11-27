"""``python -m server``: run the UI on 127.0.0.1 and open the browser."""

from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser

HOST = "127.0.0.1"  # never bind to other interfaces: the API can modify files
DEFAULT_PORT = 8765
STARTUP_TIMEOUT_S = 15.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m server", description="mytool UI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    return parser.parse_args()


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    return True


def _open_when_ready(url: str, port: int) -> None:
    """Open the browser only once the server actually accepts connections."""
    deadline = time.monotonic() + STARTUP_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        return
    if not webbrowser.open(url):
        print(f"Tarayıcı otomatik açılamadı. Bu adresi elle açın: {url}")


def main() -> None:
    args = _parse_args()
    try:
        import uvicorn

        from server.app import DEFAULT_DIST, create_app
    except ImportError as err:
        sys.exit(
            f"Eksik bağımlılık: {err.name}. Kurulum: pip install fastapi uvicorn 'pydantic>=2.7'"
        )

    if not _port_is_free(args.port):
        sys.exit(
            f"Port {args.port} kullanımda. Başka bir port deneyin: python -m server --port 8766"
        )

    url = f"http://{HOST}:{args.port}/"
    if not (DEFAULT_DIST / "index.html").is_file():
        print("Uyarı: web/dist bulunamadı. Önce `cd web && npm ci && npm run build` çalıştırın.")
    print(f"mytool UI: {url}  (durdurmak için Ctrl+C)")
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url, args.port), daemon=True).start()
    uvicorn.run(create_app(), host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
