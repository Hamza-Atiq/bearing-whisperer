"""Local stand-in for Vercel's server functions: same code, port 8787. The key is read in-process, never printed."""
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bearing import assistant  # noqa: E402

os.environ.setdefault("AMD_KEY", assistant.load_key() or "")
sys.path.insert(0, str(Path(__file__).resolve().parent / "api"))
from _common import serve  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    def _route(self):
        serve(self, self.path.split("?")[0].rstrip("/").split("/")[-1])

    do_GET = do_POST = _route


if __name__ == "__main__":
    print("dev api on http://127.0.0.1:8787, assistant key loaded:", bool(os.environ.get("AMD_KEY")))
    ThreadingHTTPServer(("127.0.0.1", 8787), Handler).serve_forever()
