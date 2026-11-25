# -*- coding: utf-8 -*-
"""
DBD 1v1 Timer - Configuration Manager
"""

import json
import os
import sys

DEFAULT_CONFIG = {
    "hotkeys": {
        "start_pause": "T",
        "split_hit_down": "F2",
        "reset": "Del",
        "toggle_lock": "F4",
        "toggle_sound": "F8"
    },
    "startup": {
        "mode": "unlocked",
        "position": "top_center",
        "remember_x": 800,
        "remember_y": 25,
        "play_sound": True
    },
    "timing": {
        "mode": "dbd_1v1",
        "countdown_seconds": 60,
        "auto_next_round": True
    },
    "appearance": {
        "bg_mode": "transparent",
        "font_size": "huge",
        "theme": "neon_green",
        "opacity": 0.95,
        "language": "en"
    },
    "sound": {
        "enabled": True,
        "volume": 0.20,
        "style": "lofi"
    },
    "auto_detect": {
        "enabled": False,
        "check_interval": 150,
        "match_threshold": 0.5,
        "use_icon_detection": True,
        "debug": False
    }
}

THEMES = {
    "neon_green": {
        "name": "螢光電競綠",
        "text_time": "#ffffff",
        "text_running": "#00ff66",
        "text_paused": "#ffcc00",
        "text_hit": "#00ffcc",
        "text_down": "#ff3344",
        "text_sub": "#aaaaaa"
    },
    "blood": {
        "name": "黎明血紅",
        "text_time": "#ffffff",
        "text_running": "#ff3344",
        "text_paused": "#ffaa00",
        "text_hit": "#33ff88",
        "text_down": "#ff2233",
        "text_sub": "#999999"
    },
    "cyber": {
        "name": "賽博青藍",
        "text_time": "#ffffff",
        "text_running": "#00ffee",
        "text_paused": "#ffbb00",
        "text_hit": "#00ffee",
        "text_down": "#ff0055",
        "text_sub": "#8899aa"
    },
    "pure_white": {
        "name": "高對比極簡白",
        "text_time": "#ffffff",
        "text_running": "#ffffff",
        "text_paused": "#e0e0e0",
        "text_hit": "#ffdd44",
        "text_down": "#ff4444",
        "text_sub": "#888888"
    }
}

KEY_VK_MAP = {
    "R": 0x52,
    "Del": 0x2E,
    "Delete": 0x2E,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74, "F6": 0x75,
    "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79, "F11": 0x7A, "F12": 0x7B,
    "Num 0": 0x60, "Num 1": 0x61, "Num 2": 0x62, "Num 3": 0x63, "Num 4": 0x64,
    "Num 5": 0x65, "Num 6": 0x66, "Num 7": 0x67, "Num 8": 0x68, "Num 9": 0x69,
    "Space": 0x20, "Tab": 0x09, "Insert": 0x2D, "Shift": 0x10,
    "`": 0xC0, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE
}
for c in range(ord('A'), ord('Z') + 1):
    KEY_VK_MAP[chr(c)] = c
for c in range(ord('0'), ord('9') + 1):
    KEY_VK_MAP[chr(c)] = c


def _app_dir():
    """程式所在目錄：打包成 exe 時用 exe 位置，開發時用專案目錄 (設定才會保存)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


class ConfigManager:
    def __init__(self, filepath=None):
        if filepath is None:
            self.filepath = os.path.join(_app_dir(), "config.json")
        else:
            self.filepath = filepath
        self.config = self.load()

    def load(self):
        if not os.path.exists(self.filepath):
            self.save(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = self._deep_merge(DEFAULT_CONFIG, data)
            # 遷移：舊版 start_pause 若殘留為 R，自動改為 T，避免「按 R 仍出聲」
            hk = merged.get("hotkeys", {})
            if hk.get("start_pause") == "R":
                hk["start_pause"] = "T"
                self.save(merged)
            return merged
        except Exception:
            return dict(DEFAULT_CONFIG)

    def save(self, data=None):
        if data is not None:
            self.config = data
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _deep_merge(self, default, custom):
        res = dict(default)
        for k, v in custom.items():
            if k in res and isinstance(res[k], dict) and isinstance(v, dict):
                res[k] = self._deep_merge(res[k], v)
            else:
                res[k] = v
        return res
