import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


SERVICE_NAME = "checkout-api"
SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")
DEGRADED = os.getenv("DEGRADED", "false").lower() == "true"


class CheckoutHandler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(
                200,
                {
                    "service": SERVICE_NAME,
                    "status": "degraded" if DEGRADED else "healthy",
                    "version": SERVICE_VERSION,
                },
            )
            return

        if self.path == "/checkout":
            if DEGRADED:
                time.sleep(0.8)
            else:
                time.sleep(0.08)

            self.send_json(
                200,
                {
                    "service": SERVICE_NAME,
                    "version": SERVICE_VERSION,
                    "checkout": "completed",
                    "mode": "degraded" if DEGRADED else "normal",
                },
            )
            return

        self.send_json(
            404,
            {
                "error": "not_found",
            },
        )

    def log_message(self, format: str, *args) -> None:
        print(f"[checkout-api] {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), CheckoutHandler)

    print(
        f"Checkout API running on port 8000 "
        f"(version={SERVICE_VERSION}, degraded={DEGRADED})"
    )

    server.serve_forever()