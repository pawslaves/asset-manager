import threading

import uvicorn
import webview
from backend.api import app


class Bridge:
    def __init__(self):
        self._window = None

    def set_window(self, w):
        self._window = w

    def pick(self):
        if not self._window:
            return None
        result = self._window.create_file_dialog(webview.FileDialog.OPEN)
        return result[0] if result else None


def run_server():
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=5000,
        log_level="critical",
        access_log=False,
        log_config=None,
    )


def main():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    api = Bridge()
    window = webview.create_window(
        "paw asset manager",
        "http://127.0.0.1:5000",
        width=840,
        height=620,
        background_color="#201d1d",
        js_api=api,
    )
    api.set_window(window)

    webview.start()


if __name__ == "__main__":
    main()
