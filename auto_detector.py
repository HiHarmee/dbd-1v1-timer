# -*- coding: utf-8 -*-
"""
DBD 1v1 Timer - 倒地圖標偵測器 (NCC 模板比對)
- 使用 icon_detector.DownedIconMatcher 判斷 ROI 是否與倒地參考圖相似
- 觸發：連續多幀倒地 -> on_down_callback；連續多幀非倒地 -> on_undowned_callback
- check_interval 單位為「毫秒」(與 config.json 一致)
"""

import time
import threading
import ctypes

try:
    from PIL import ImageGrab  # noqa: F401  (備援截圖)
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import numpy as np
from icon_detector import DownedIconMatcher
from fast_grab import FastGrabber

user32 = ctypes.windll.user32


class DownedIconDetector:
    """
    倒地圖標偵測器

    參數:
        on_down_callback: 偵測到倒地時呼叫 (自動暫停)
        on_undowned_callback: 偵測到救起時呼叫 (自動續算)
        custom_bbox: (x1, y1, x2, y2) 螢幕絕對座標，None 則依解析度計算
        threshold: NCC 門檻
    """

    def __init__(self, on_down_callback=None, on_undowned_callback=None,
                 custom_bbox=None, threshold=0.5):
        self.on_down = on_down_callback
        self.on_undowned = on_undowned_callback
        self.running = False
        self.thread = None

        self.current_state = "UP"  # "UP" / "DOWNED"
        self.consecutive_down = 0
        self.consecutive_up = 0
        self.required_consecutive = 2  # 連續 2 幀確認

        self.check_interval_ms = 150   # 毫秒
        self.threshold = threshold
        self.use_icon_detection = True

        self.matcher = DownedIconMatcher(threshold=threshold, pad=2)
        self.last_result = (False, {})  # 背景迴圈最新結果 (UI 讀取，不重複截圖)
        self._grabber = None       # GDI 快速擷取器 (懶建立)
        self._grabber_bbox = None

        self.screen_w = user32.GetSystemMetrics(0)
        self.screen_h = user32.GetSystemMetrics(1)
        self.custom_bbox = custom_bbox
        self._calculate_bbox()

    def _calculate_bbox(self):
        """未指定 bbox 時，依 16:9 比例計算左下角第 1 個頭像區域"""
        if self.custom_bbox and len(self.custom_bbox) == 4:
            self.bbox = tuple(int(v) for v in self.custom_bbox)
        else:
            x1 = int(self.screen_w * 0.028)
            x2 = int(self.screen_w * 0.065)
            y1 = int(self.screen_h * 0.744)
            y2 = int(self.screen_h * 0.796)
            self.bbox = (x1, y1, x2, y2)

    def set_bbox(self, bbox):
        self.custom_bbox = bbox
        self.bbox = tuple(int(v) for v in bbox)

    def get_bbox(self):
        return self.bbox

    def update_thresholds(self, threshold=None, check_interval_ms=None,
                          use_icon_detection=None):
        """熱更新參數 (check_interval_ms 為毫秒)"""
        if threshold is not None:
            self.threshold = threshold
            self.matcher.threshold = threshold
        if check_interval_ms is not None:
            self.check_interval_ms = check_interval_ms
        if use_icon_detection is not None:
            self.use_icon_detection = use_icon_detection

    def start(self):
        if not PIL_AVAILABLE or self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def reset_state(self):
        self.current_state = "UP"
        self.consecutive_down = 0
        self.consecutive_up = 0

    def _grab_region(self):
        """優先使用 GDI 快速擷取 (約 11ms)，失敗時退回 ImageGrab (約 54ms)"""
        if self._grabber_bbox != self.bbox:
            if self._grabber is not None:
                self._grabber.close()
            self._grabber = None
            self._grabber_bbox = self.bbox
            try:
                self._grabber = FastGrabber(self.bbox)
            except Exception:
                self._grabber = None
        if self._grabber is not None:
            try:
                return self._grabber.grab()
            except Exception:
                self._grabber.close()
                self._grabber = None
        img = ImageGrab.grab(bbox=self.bbox)
        return np.asarray(img.convert("RGB"))

    def analyze_frame(self):
        """
        擷取 bbox 畫面並比對，回傳 (is_downed, stats)
        stats 包含 score (NCC)、threshold、bbox 與 region (ROI numpy 陣列，供除錯預覽)
        """
        if not PIL_AVAILABLE:
            return False, {"error": "PIL not available"}
        try:
            region = self._grab_region()
            if region.size == 0:
                return False, {"error": "empty region"}

            if not self.use_icon_detection:
                return False, {"score": 0.0, "threshold": self.threshold,
                               "bbox": self.bbox, "region": region, "error": None}

            is_downed, score = self.matcher.is_downed(region)
            return is_downed, {
                "score": score,
                "threshold": self.threshold,
                "bbox": self.bbox,
                "region": region,
                "error": None,
            }
        except Exception as e:
            return False, {"error": str(e)}


    def _loop(self):
        """背景監聽迴圈 (防抖：連續 required_consecutive 幀才切換狀態)"""
        while self.running:
            try:
                is_downed, _stats = self.analyze_frame()
                # 保存最新結果供 UI 讀取，UI 不再自行截圖
                self.last_result = (is_downed, _stats)

                if is_downed:
                    self.consecutive_down += 1
                    self.consecutive_up = 0
                    if (self.consecutive_down >= self.required_consecutive
                            and self.current_state == "UP"):
                        self.current_state = "DOWNED"
                        if self.on_down:
                            self.on_down()
                else:
                    self.consecutive_up += 1
                    self.consecutive_down = 0
                    if (self.consecutive_up >= self.required_consecutive
                            and self.current_state == "DOWNED"):
                        self.current_state = "UP"
                        if self.on_undowned:
                            self.on_undowned()
            except Exception:
                pass

            time.sleep(max(0.02, self.check_interval_ms / 1000.0))


# 向後相容：保留舊介面名稱
ScreenAutoDetector = DownedIconDetector
