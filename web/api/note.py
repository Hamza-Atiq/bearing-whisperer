from http.server import BaseHTTPRequestHandler
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import serve  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        serve(self, "note")

    def do_GET(self):
        serve(self, "note")
