"""``python -m server``: run the UI on 127.0.0.1 and open the browser."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"  # never bind to other interfaces: the API can modify files
DEFAULT_PORT = 8765
STARTUP_TIMEOUT_S = 15.0
GRACEFUL_SHUTDOWN_S = 2


ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env_file(path: Path = ENV_FILE) -> list[str]:
    """Read KEY=value lines from the repo's .env (git-ignored) into os.environ.

    Values already set in the terminal win. Returns the names that were loaded,
    never the values, so secrets are not printed.
    """
    loaded: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return loaded
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m server", description="Verifix web arayüzü")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="sunucu portu")
    parser.add_argument("--no-browser", action="store_true", help="tarayıcıyı açma")
    parser.add_argument(
        "--model", help="öneriler için LLM modeli (ör. claude-haiku-5-5); MYTOOL_MODEL yerine"
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        help="analiz başına harcama sınırı, USD (varsayılan 0.50); MYTOOL_MAX_COST yerine",
    )
    args = parser.parse_args()
    # The core adapter reads its settings from the environment (load_config).
    if args.model:
        os.environ["MYTOOL_MODEL"] = args.model
    if args.max_cost is not None:
        if args.max_cost < 0:
            parser.error("--max-cost negatif olamaz")
        os.environ["MYTOOL_MAX_COST"] = str(args.max_cost)
    return args


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


def _print_settings() -> None:
    if os.environ.get("MYTOOL_UI_ADAPTER", "core").strip().lower() == "mock":
        print("Adaptör: mock (sahte veri, API çağrısı yapılmaz)")
        return
    from mytool.core.config import has_api_key, load_config

    try:
        cfg = load_config()
    except ValueError as exc:
        sys.exit(str(exc))
    key = "tanımlı" if has_api_key() else "TANIMLI DEĞİL"
    print(
        f"Model: {cfg.model} · harcama sınırı: ${cfg.max_cost_usd:.2f}/analiz · "
        f"ANTHROPIC_API_KEY: {key}"
    )
    from server.notify import TelegramNotifier

    telegram = (
        "açık" if TelegramNotifier().configured else "kapalı (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)"
    )
    print(f"Telegram bildirimi: {telegram}")


def main() -> None:
    loaded = load_env_file()
    if loaded:
        print(f".env okundu: {', '.join(loaded)}")
    args = _parse_args()
    try:
        import uvicorn

        from server.app import DEFAULT_DIST, create_app
    except ImportError as err:
        sys.exit(f"Eksik bağımlılık: {err.name}. Depo kökünde kurulum: uv sync --group ui")

    if not _port_is_free(args.port):
        sys.exit(
            f"Port {args.port} kullanımda. Başka bir port deneyin: python -m server --port 8766"
        )

    url = f"http://{HOST}:{args.port}/"
    if not (DEFAULT_DIST / "index.html").is_file():
        print("Uyarı: web/dist bulunamadı. Önce `cd web && npm ci && npm run build` çalıştırın.")
    print(f"Verifix: {url}")
    _print_settings()
    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url, args.port), daemon=True).start()
    print("Durdurmak için Ctrl+C (en geç birkaç saniyede kapanır).")
    # Live progress streams (SSE) stay open; without a timeout Ctrl+C waits for them forever.
    uvicorn.run(
        create_app(),
        host=HOST,
        port=args.port,
        log_level="warning",
        timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_S,
    )


if __name__ == "__main__":
    main()
