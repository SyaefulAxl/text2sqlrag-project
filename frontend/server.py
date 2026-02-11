#!/usr/bin/env python3
"""
Simple HTTP server for the frontend application.
Run this to serve the frontend on http://localhost:8080
"""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080
FRONTEND_DIR = Path(__file__).parent


class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        # Add CORS headers to allow requests to localhost:8000
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def run_server():
    os.chdir(FRONTEND_DIR)
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"🚀 Frontend server running at http://localhost:{PORT}")
        print(f"📁 Serving files from: {FRONTEND_DIR}")
        print(f"📡 Backend API expected at: http://localhost:8000")
        print(f"\nPress CTRL+C to stop the server")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✅ Server stopped")


if __name__ == "__main__":
    run_server()
