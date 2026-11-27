"""``python -m server``: run the UI on 127.0.0.1 and open the browser."""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from server.app import DEFAULT_DIST, create_app

HOST = "127.0.0.1"  # never bind to other interfaces: the API can modify files
DEFAULT_PORT = 8765


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m server", description="mytool UI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    url = f"http://{HOST}:{args.port}/"
    has_frontend = (DEFAULT_DIST / "index.html").is_file()
    if not has_frontend:
        print("web/dist bulunamadı: yalnızca API çalışıyor. Arayüz için `npm run dev` (web/).")
    elif not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print(f"mytool UI: {url}")
    uvicorn.run(create_app(), host=HOST, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
