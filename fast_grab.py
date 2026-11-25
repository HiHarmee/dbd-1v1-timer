# -*- coding: utf-8 -*-
"""
快速螢幕區域擷取 (Win32 GDI BitBlt)
- 比 PIL.ImageGrab 快很多 (約 54ms -> 數 ms)
- 回傳 numpy uint8 陣列 (H, W, 3) RGB
- 程序啟動時設定 Per-Monitor DPI 感知，確保座標與實體像素一致
- 任何錯誤都會拋出例外，呼叫端可退回 ImageGrab
"""

import ctypes
import numpy as np
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0
CAPTUREBLT = 0x40000000

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
gdi32.BitBlt.restype = wintypes.BOOL
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def set_dpi_aware():
    """設定 Per-Monitor DPI 感知，讓 GetSystemMetrics 與擷取座標使用實體像素"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class FastGrabber:
    """重複使用 DC 與 bitmap，避免每幀重新配置資源"""

    def __init__(self, bbox):
        self.set_bbox(bbox)

    def set_bbox(self, bbox):
        x1, y1, x2, y2 = (int(v) for v in bbox)
        self.x, self.y = x1, y1
        self.w, self.h = max(1, x2 - x1), max(1, y2 - y1)
        self._release()
        self.screen_dc = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        self.bmp = gdi32.CreateCompatibleBitmap(self.screen_dc, self.w, self.h)
        self.old = gdi32.SelectObject(self.mem_dc, self.bmp)

        self.bmi = BITMAPINFOHEADER()
        self.bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bmi.biWidth = self.w
        self.bmi.biHeight = -self.h  # 負值 = 由上到下
        self.bmi.biPlanes = 1
        self.bmi.biBitCount = 32
        self.bmi.biCompression = BI_RGB
        self.buf = (ctypes.c_ubyte * (self.w * self.h * 4))()

    def grab(self):
        """擷取目前 bbox 的畫面，回傳 (H, W, 3) uint8 RGB"""
        ok = gdi32.BitBlt(self.mem_dc, 0, 0, self.w, self.h,
                          self.screen_dc, self.x, self.y, SRCCOPY | CAPTUREBLT)
        if not ok:
            raise OSError("BitBlt failed")
        lines = gdi32.GetDIBits(self.mem_dc, self.bmp, 0, self.h,
                                ctypes.byref(self.buf), ctypes.byref(self.bmi), DIB_RGB_COLORS)
        if lines != self.h:
            raise OSError("GetDIBits failed")
        bgra = np.frombuffer(self.buf, dtype=np.uint8).reshape(self.h, self.w, 4)
        return bgra[:, :, [2, 1, 0]].copy()  # BGRA -> RGB

    def _release(self):
        if getattr(self, "mem_dc", None):
            gdi32.SelectObject(self.mem_dc, self.old)
            gdi32.DeleteObject(self.bmp)
            gdi32.DeleteDC(self.mem_dc)
            user32.ReleaseDC(None, self.screen_dc)
            self.mem_dc = None

    def close(self):
        self._release()
