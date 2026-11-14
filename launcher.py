"""Launch the local application, without connecting to equipment automatically."""
import argparse
import os
from pathlib import Path
import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn
from backend.api import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    # Bind once and hand the socket to uvicorn, avoiding a port-check race.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", args.port))
    except OSError:
        sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    data_dir = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "FM_GPTPRO"
    data_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(persistence_path=data_dir / "simulation.json")

    def open_browser():
        for _ in range(100):
            try:
                with urllib.request.urlopen(url + "/api/meta", timeout=0.5):
                    webbrowser.open(url)
                    return
            except OSError:
                time.sleep(0.1)

    if not args.no_browser:
        threading.Thread(target=open_browser, daemon=True).start()
    print(f"FM_GPTPRO: {url} (offline until explicitly connected)", flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info"))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
