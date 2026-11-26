"""Serve the app on this computer (http://localhost:8765) – installable from Chrome/Edge."""
import functools
import http.server
import threading
import webbrowser


class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".webmanifest": "application/manifest+json", ".js": "text/javascript",
                      ".json": "application/json", ".svg": "image/svg+xml"}

    def end_headers(self):
        if "/data/" in self.path or self.path.split("?")[0].endswith(("sw.js", ".html", "/")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args):  # keep the console clean
        pass


def serve(app_dir, port=8765, open_browser=True):
    handler = functools.partial(_Handler, directory=app_dir)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://localhost:{port}/"
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if open_browser:
        webbrowser.open(url)
    return httpd, url
