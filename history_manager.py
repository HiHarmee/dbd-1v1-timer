# -*- coding: utf-8 -*-
"""
DBD 1v1 Timer - History 讀寫
- 將 self.history 儲存為 history.json，並提供讀取、格式化功能
- 路徑與 config.json 同資料夾
"""

import json
import os
import sys


def _app_dir():
    """程式所在目錄：打包成 exe 時用 exe 位置，開發時用專案目錄 (紀錄才會保存)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _app_dir()
HISTORY_PATH = os.path.join(BASE_DIR, "history.json")


def load_history():
    """讀取 history.json，回傳 list；檔案不存在或格式錯誤時回傳空 list"""
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("history"), list):
            return data["history"]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_history(history):
    """將 history list 寫入 history.json"""
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump({"history": history}, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def fmt_time(seconds):
    """將秒數格式化成 mm:ss.xx；None 回傳 --:--.--"""
    if seconds is None:
        return "--:--.--"
    m = int(seconds // 60)
    s = int(seconds % 60)
    ms = int((seconds * 100) % 100)
    return "{:02d}:{:02d}.{:02d}".format(m, s, ms)


def render_text(history):
    """把 history list 轉成易讀的文字行（含換行）"""
    from i18n import tr
    if not history:
        return tr("history.empty")
    lines = []
    for item in history:
        round_no = item.get("round", "-")
        hit_t = fmt_time(item.get("hit"))
        down_t = fmt_time(item.get("down"))
        hit_diff = ""
        if item.get("hit") is not None and item.get("down") is not None:
            hit_diff = "  (+{:.1f}s)".format(item["down"] - item["hit"])
        lines.append(tr("history.render").format(round_no, hit_t, down_t, hit_diff))
    return "\n".join(lines)