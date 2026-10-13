"""Two independent native windows, sharing one local server and controller."""
from threading import RLock
import webview
from config import VERSION


class DesktopWindows:
    def __init__(self, url, hidden=False):
        self._url=url
        self._hidden=hidden
        self._lock=RLock()
        self._debug=None
        self._closing=False
        self._main=webview.create_window(f"SDITADC · v{VERSION} · 仓库运行",url,
                                      js_api=self,width=1460,height=940,min_size=(1080,720),
                                      hidden=hidden,maximized=not hidden,background_color="#101820")
        self._main.events.closed += self._main_closed

    def open_debug(self):
        with self._lock:
            if self._closing:
                return {"ok":False}
            if self._debug is not None and self._debug in webview.windows:
                window=self._debug
            else:
                window=webview.create_window(f"SDITADC · v{VERSION} · 运行调试",self._url+"debug.html",
                                            js_api=self,width=900,height=800,min_size=(680,600),
                                            hidden=self._hidden,background_color="#101820")
                self._debug=window
                window.events.closed += lambda: self._debug_closed(window)
        if not self._hidden:
            window.show()
        return {"ok":True}

    def focus_main(self):
        if not self._hidden and not self._closing:
            self._main.show()
        return {"ok":not self._closing}

    def _debug_closed(self, window):
        with self._lock:
            if self._debug is window:
                self._debug=None

    def _main_closed(self):
        with self._lock:
            self._closing=True
            window=self._debug
            self._debug=None
        if window is not None and window in webview.windows:
            window.destroy()

