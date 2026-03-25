#!/usr/bin/env python3
import http.server
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
port = int(os.environ.get("PORT", 8000))

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/station-finder.html"
        return super().do_GET()

with http.server.HTTPServer(("", port), Handler) as httpd:
    print(f"Serving at http://localhost:{port}")
    httpd.serve_forever()
