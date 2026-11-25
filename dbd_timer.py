# -*- coding: utf-8 -*-
"""
DBD 1v1 Duel Overlay Timer (原生電競 HUD 版 - 水平橫向一字展開)
- 修正：切換視窗防卡死 (DWM SWP_FRAMECHANGED 刷新機制)
- 修正：全螢幕遊戲按鍵穿透偵測 (GetAsyncKeyState 64-bit 強化)
- 優化：滑鼠穿透鎖定無縫切換，拖曳絕對座標邊界防脫軌
- 預設按鍵：T 鍵開始 / 倒地紀錄 / 下一局、F2 首刀、Del 鍵重設
"""

import os
import sys
import time
import threading
import tkinter as tk
import ctypes

from config_manager import ConfigManager, THEMES, KEY_VK_MAP
from sound_engine import LoFiSoundEngine
from settings_window import SettingsWindow
from auto_detector import DownedIconDetector
from history_manager import load_history, save_history
from i18n import tr, set_lang

# Win32 API 常數
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_APPWINDOW = 0x00040000
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

user32 = ctypes.windll.user32
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

CHROMA_KEY = "#010101"


class DBDDuelTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("DBD 1v1 Timer")

        self.cfg_mgr = ConfigManager()
        self.cfg = self.cfg_mgr.config
        set_lang(self.cfg.get("appearance", {}).get("language", "en"))
        snd_cfg = self.cfg["sound"]
        self.sound_engine = LoFiSoundEngine(
            volume=snd_cfg.get("volume", 0.20),
            sound_style=snd_cfg.get("style", "lofi"),
            enabled=snd_cfg.get("enabled", True)
        )

        # 水平橫向尺寸
        self.width = 560
        self.height = 50

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # 計時狀態
        self.is_running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.hit_time = None
        self.down_time = None
        self.round_num = 1
        self.history = load_history()
        self.laps = []
        self._last_cue_int = -1          # 已觸發的 30/60 秒整數秒
        self._clock_flash_after = None   # 數字閃動排程
        self._clock_flash_count = 0
        self._clock_flash_on = False
        self._clock_flash_base = None

        self.cd_target = self.cfg["timing"].get("countdown_seconds", 60)
        self.cd_remaining = float(self.cd_target)

        self.is_locked = False
        self._drag_offset_x = 0
        self._drag_offset_y = 0

        # 建立 UI
        self._build_ui()
        self._apply_appearance()

        self.root.update_idletasks()
        self.hwnd = int(self.root.frame(), 16) if hasattr(self.root, 'frame') else user32.FindWindowW(None, "DBD 1v1 Timer")
        self._enable_taskbar_icon()
        self._detach_ime(self.hwnd)

        self._apply_initial_position()

        # 置頂顯現，SWP_NOACTIVATE 避免切換時搶焦點卡頓
        self.root.lift()
        user32.SetWindowPos(
            self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED | SWP_SHOWWINDOW
        )

        if self.cfg["startup"].get("mode") == "locked":
            self.root.after(300, self.toggle_lock)

        if self.cfg["startup"].get("play_sound", True):
            self.sound_engine.play("startup")

        # 自動偵測器 - 只偵測倒地圖標 (自動暫停/續算)，參數全部來自 config.json
        ad = self.cfg.get("auto_detect", {})
        self.auto_detector = DownedIconDetector(
            on_down_callback=lambda: self.root.after(0, self._auto_pause_on_downed),
            on_undowned_callback=lambda: self.root.after(0, self._auto_resume_on_pickup),
            custom_bbox=self._bbox_from_cfg(ad),
            threshold=ad.get("match_threshold", 0.75),
        )
        self.auto_detector.update_thresholds(
            check_interval_ms=ad.get("check_interval", 150),
            use_icon_detection=ad.get("use_icon_detection", True),
        )
        if self.cfg.get("auto_detect", {}).get("enabled", False):
            self.auto_detector.start()

        # 除錯視窗 (顯示偵測 ROI 與即時統計)
        self.debug_window = None
        self.debug_enabled = False
        if self.cfg.get("auto_detect", {}).get("debug", False):
            self._open_debug_window()

        # 螢幕 ROI 覆蓋層 (框出偵測區域)
        self.roi_overlay = None
        self.roi_overlay_enabled = False
        if self.cfg.get("auto_detect", {}).get("debug", False):
            self._show_roi_overlay()

        # 快捷鍵監聽
        self.stop_key_listener = False
        self._update_vk_map()
        self.key_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        self.key_thread.start()

        self._update_clock()

    def _enable_taskbar_icon(self):
        try:
            style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style)
            user32.SetWindowPos(
                self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
        except Exception:
            pass

    def _detach_ime(self, hwnd):
        """卸載計時視窗的輸入法，避免按 T 等按鍵時跳出注音候選小視窗"""
        try:
            imm32 = ctypes.windll.imm32
            imm32.ImmAssociateContextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            imm32.ImmAssociateContextW.restype = ctypes.c_void_p
            imm32.ImmAssociateContextW(ctypes.c_void_p(hwnd), None)
        except Exception:
            pass

    def _apply_initial_position(self):
        pos_mode = self.cfg["startup"].get("position", "top_center")
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        if pos_mode == "top_center":
            x = max(10, (screen_w - self.width) // 2)
            y = 20
        elif pos_mode == "top_right":
            x = max(10, screen_w - self.width - 30)
            y = 20
        elif pos_mode == "remember":
            rx = self.cfg["startup"].get("remember_x", (screen_w - self.width) // 2)
            ry = self.cfg["startup"].get("remember_y", 20)
            x = max(0, min(screen_w - self.width, rx))
            y = max(0, min(screen_h - self.height, ry))
        else:
            x = max(10, (screen_w - self.width) // 2)
            y = 20

        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

    # ----------------- UI 建立 -----------------
    def _build_ui(self):
        self.bar = tk.Frame(self.root)
        self.bar.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        self.round_label = tk.Label(
            self.bar, text="{}{}".format(tr("hud.round"), self.round_num), font=("Impact", 13),
            anchor="w", cursor="fleur"
        )
        self.round_label.pack(side=tk.LEFT, padx=(0, 10))

        self.time_label = tk.Label(
            self.bar, text="00:00.00", font=("Consolas", 32, "bold"),
            cursor="fleur"
        )
        self.time_label.pack(side=tk.LEFT, padx=(0, 12))

        self.divider = tk.Label(self.bar, text="|", font=("Arial", 11), fg="#555555")
        self.divider.pack(side=tk.LEFT, padx=(0, 12))

        self.hit_label = tk.Label(
            self.bar, text=tr("hud.first_hit"), font=("Microsoft JhengHei", 10, "bold"),
            cursor="fleur"
        )
        self.hit_label.pack(side=tk.LEFT, padx=(0, 12))

        self.down_label = tk.Label(
            self.bar, text=tr("hud.downed"), font=("Microsoft JhengHei", 10, "bold"),
            cursor="fleur"
        )
        self.down_label.pack(side=tk.LEFT, padx=(0, 14))

        self.close_btn = tk.Label(
            self.bar, text=tr("hud.close"), font=("Arial", 9, "bold"), fg="#888888", padx=4, cursor="hand2"
        )
        self.close_btn.pack(side=tk.RIGHT)
        self.close_btn.bind("<Button-1>", lambda e: self.close())

        self.settings_btn = tk.Label(
            self.bar, text=tr("hud.settings"), font=("Arial", 9, "bold"), fg="#888888", padx=4, cursor="hand2"
        )
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 6))
        self.settings_btn.bind("<Button-1>", lambda e: self.open_settings())

        self.lock_badge = tk.Label(
            self.bar, text=tr("hud.lock_off"), font=("Arial", 10, "bold"), fg="#00ff66", cursor="hand2"
        )
        self.lock_badge.pack(side=tk.LEFT, padx=(8, 0))
        self.lock_badge.bind("<Button-1>", lambda e: self.toggle_lock())

        for widget in (self.bar, self.round_label, self.time_label, self.divider,
                       self.hit_label, self.down_label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, event):
        self._drag_offset_x = event.x_root - self.root.winfo_x()
        self._drag_offset_y = event.y_root - self.root.winfo_y()

    def _on_drag(self, event):
        if self.is_locked:
            return
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        new_x = max(0, min(screen_w - self.width, event.x_root - self._drag_offset_x))
        new_y = max(0, min(screen_h - self.height, event.y_root - self._drag_offset_y))
        self.root.geometry(f"+{new_x}+{new_y}")
        self.cfg["startup"]["remember_x"] = new_x
        self.cfg["startup"]["remember_y"] = new_y

    # ----------------- 視窗鎖定 (含 DWM 刷新) -----------------
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.sound_engine.play("toggle_lock")
        cur_style = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)

        if self.is_locked:
            new_style = cur_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            user32.SetWindowPos(
                self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
            self.lock_badge.config(text=tr("hud.lock_on"), fg="#ff3344")
        else:
            new_style = (cur_style & ~WS_EX_TRANSPARENT) | WS_EX_LAYERED
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, new_style)
            user32.SetWindowPos(
                self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED
            )
            self.lock_badge.config(text=tr("hud.lock_off"), fg="#00ff66")

    # ----------------- 外觀套用 -----------------
    def _apply_appearance(self):
        app_cfg = self.cfg["appearance"]
        th_key = app_cfg.get("theme", "neon_green")
        th = THEMES.get(th_key, THEMES["neon_green"])
        bg_mode = app_cfg.get("bg_mode", "transparent")
        font_sz = app_cfg.get("font_size", "huge")

        pt = 34 if font_sz == "huge" else (30 if font_sz == "large" else 26)
        self.time_label.configure(font=("Consolas", pt, "bold"))

        if bg_mode == "transparent":
            self.root.attributes("-transparentcolor", CHROMA_KEY)
            self.root.attributes("-alpha", 1.0)
            self.root.configure(bg=CHROMA_KEY)
            self.bar.configure(bg=CHROMA_KEY)
            bg_color = CHROMA_KEY
        else:
            self.root.attributes("-transparentcolor", "")
            self.root.attributes("-alpha", 0.78)
            dark_bg = "#0d0e14"
            self.root.configure(bg=dark_bg)
            self.bar.configure(bg=dark_bg)
            bg_color = dark_bg

        self.round_label.configure(fg=th["text_sub"], bg=bg_color)
        self.divider.configure(bg=bg_color)
        self.hit_label.configure(fg=th["text_hit"], bg=bg_color)
        self.down_label.configure(fg=th["text_down"], bg=bg_color)
        self.close_btn.configure(bg=bg_color)
        self.settings_btn.configure(bg=bg_color)

        badge_col = "#ff3344" if self.is_locked else "#00ff66"
        badge_txt = tr("hud.lock_on") if self.is_locked else tr("hud.lock_off")
        self.lock_badge.configure(text=badge_txt, fg=badge_col, bg=bg_color)

        if self.is_running:
            self.time_label.configure(fg=th["text_running"], bg=bg_color)
        elif self.elapsed_time > 0 or self.down_time is not None:
            self.time_label.configure(fg=th["text_paused"], bg=bg_color)
        else:
            self.time_label.configure(fg=th["text_time"], bg=bg_color)

    # ----------------- 計時控制 -----------------
    def toggle_start(self):
        th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
        mode = self.cfg["timing"].get("mode", "dbd_1v1")

        # dbd_1v1：T 鍵語意
        #   未開始 -> 開始新局；計時中 -> 紀錄倒地並結束本局；本局已倒地 -> 開新局
        if mode == "dbd_1v1":
            if self.down_time is not None:
                self._start_new_round()
            elif self.is_running:
                self._record_down()
            else:
                self._start_new_round()
            return

        if not self.is_running:
            if mode == "countdown":
                if self.cd_remaining <= 0.05:
                    self.cd_remaining = float(self.cfg["timing"].get("countdown_seconds", 60))
                self.start_time = time.time()
            else:
                self.start_time = time.time() - self.elapsed_time
            self.is_running = True
            self.time_label.config(fg=th["text_running"])
            self.sound_engine.play("start")
        else:
            if mode == "countdown":
                self.cd_remaining = max(0.0, self.cd_remaining - (time.time() - self.start_time))
            else:
                self.elapsed_time = time.time() - self.start_time
            self.is_running = False
            self._stop_clock_flash(restore=False)
            self.time_label.config(fg=th["text_paused"])
            self.sound_engine.play("pause")

    def pause_timer(self):
        if self.is_running:
            self.elapsed_time = time.time() - self.start_time
            self.is_running = False
            self._stop_clock_flash(restore=False)
            self.time_label.config(fg="#ffcc00")
            self.sound_engine.play("pause")

    def trigger_split(self):
        th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
        mode = self.cfg["timing"].get("mode", "dbd_1v1")

        if mode == "dbd_1v1":
            if not self.is_running and self.elapsed_time == 0:
                return
            cur = time.time() - self.start_time if self.is_running else self.elapsed_time
            # F2 只負責首刀；倒地由 T 鍵或倒地偵測紀錄
            if self.hit_time is None:
                self.hit_time = cur
                self.hit_label.config(text=tr("hud.first_hit_fmt").format(self._format_time(self.hit_time)), fg=th["text_hit"])
                self.sound_engine.play("hit")

        elif mode == "stopwatch":
            if not self.is_running and self.elapsed_time == 0:
                return
            cur = time.time() - self.start_time if self.is_running else self.elapsed_time
            self.laps.append(cur)
            self.hit_label.config(text=f"圈數 #{len(self.laps)}: {self._format_time(cur)}")
            self.sound_engine.play("lap")

        elif mode == "countdown":
            self.cd_remaining = float(self.cfg["timing"].get("countdown_seconds", 60))
            self.time_label.config(text=self._format_time(self.cd_remaining))
            self.sound_engine.play("reset")

    def _auto_pause_on_downed(self):
        """偵測到倒地圖標 -> 直接紀錄倒地時間並結束本局 (dbd_1v1)；其他模式維持自動暫停"""
        if self.cfg["timing"].get("mode", "dbd_1v1") != "dbd_1v1":
            if self.is_running:
                self.pause_timer()
                self.sound_engine.play("down")
            return
        if self.down_time is not None:
            return  # 本局已紀錄過倒地
        if not self.is_running and self.elapsed_time == 0:
            return  # 尚未開始計時，忽略
        self._record_down()

    def _auto_resume_on_pickup(self):
        """倒地圖標消失 -> 前一局已保留，自動開始新的一局 (dbd_1v1)；其他模式維持自動續算"""
        if self.cfg["timing"].get("mode", "dbd_1v1") != "dbd_1v1":
            if not self.is_running and self.elapsed_time > 0:
                self.toggle_start()
                self.sound_engine.play("hit")
            return
        if self.down_time is None:
            return  # 本局尚未紀錄倒地，不切局
        self._start_new_round()

    def _record_down(self):
        """紀錄本局倒地時間並結束本局；前一局資料保存在 self.history"""
        th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
        cur = time.time() - self.start_time if self.is_running else self.elapsed_time
        self.down_time = cur
        diff_txt = tr("hud.down_diff").format(self.down_time - self.hit_time) if self.hit_time is not None else ""
        self.down_label.config(text=tr("hud.downed_fmt").format(self._format_time(self.down_time)) + diff_txt, fg=th["text_down"])
        self.is_running = False
        self.elapsed_time = self.down_time
        self._stop_clock_flash(restore=False)
        self.time_label.config(text=self._format_time(self.down_time), fg=th["text_down"])
        self.sound_engine.play("down")
        self.history.append({
            "round": self.round_num,
            "hit": self.hit_time,
            "down": self.down_time,
        })
        save_history(self.history)

    def _start_new_round(self):
        """開始新的一局：局數 +1、計時從 0 開始，前一局紀錄保留"""
        th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
        # 只有前一局確實有紀錄時才 +1；首次開始維持第 1 局
        if self.history or self.elapsed_time > 0 or self.down_time is not None:
            self.round_num += 1
        self.is_running = True
        self.start_time = time.time()
        self.elapsed_time = 0.0
        self.hit_time = None
        self.down_time = None
        self.laps = []
        self._last_cue_int = -1
        self._stop_clock_flash(restore=False)
        self.round_label.config(text="{}{}".format(tr("hud.round"), self.round_num))
        self.hit_label.config(text=tr("hud.first_hit"))
        self.down_label.config(text=tr("hud.downed"))
        self._last_clock_ticks = None
        self.time_label.config(text="00:00.00", fg=th["text_running"])
        self.sound_engine.play("start")

    def reset_timer(self):
        self.sound_engine.play("reset")
        if self.cfg["timing"].get("auto_next_round", True) and (self.elapsed_time > 0 or self.down_time is not None):
            self.round_num += 1

        self.is_running = False
        self.start_time = 0.0
        self.elapsed_time = 0.0
        self.hit_time = None
        self.down_time = None
        self.laps = []
        self._last_cue_int = -1
        self._stop_clock_flash(restore=False)
        if hasattr(self, 'auto_detector'):
            self.auto_detector.reset_state()
        self.round_label.config(text="{}{}".format(tr("hud.round"), self.round_num))
        self._last_clock_ticks = None
        self.time_label.config(text="00:00.00")
        self.hit_label.config(text=tr("hud.first_hit"))
        self.down_label.config(text=tr("hud.downed"))
        self.time_label.config(fg="#ffffff")

    # ----------------- 時鐘更新 -----------------
    def _format_time(self, seconds):
        m = int(seconds // 60)
        s = int(seconds % 60)
        ms = int((seconds * 100) % 100)
        return f"{m:02d}:{s:02d}.{ms:02d}"

    def _update_clock(self):
        if self.is_running:
            mode = self.cfg["timing"].get("mode", "dbd_1v1")
            if mode == "countdown":
                rem = max(0.0, self.cd_remaining - (time.time() - self.start_time))
                if rem <= 0.001:
                    self.is_running = False
                    self.cd_remaining = 0.0
                    th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
                    self.time_label.config(text="00:00.00", fg=th["text_down"])
                    self.sound_engine.play("alarm")
                else:
                    self._set_clock_text(rem)
            else:
                elapsed = time.time() - self.start_time
                self._check_interval_cue(elapsed)
                self._set_clock_text(elapsed)
        self.root.after(20, self._update_clock)

    def _check_interval_cue(self, elapsed):
        """30 秒與每 60 秒 -> 數字閃動提示 (無提示音、無邊框)"""
        sec = int(elapsed)
        if sec == self._last_cue_int:
            return
        self._last_cue_int = sec
        if sec <= 0:
            return
        if sec % 60 == 30:
            self._start_clock_flash(0.8)   # 30 秒：短閃
        elif sec % 60 == 0:
            self._start_clock_flash(1.6)   # 60 秒：長閃

    # ---------- 數字閃動提示 ----------
    def _start_clock_flash(self, duration):
        """讓計時數字在主題色與白色之間閃動，duration 單位為秒"""
        self._stop_clock_flash(restore=False)
        th = THEMES.get(self.cfg["appearance"].get("theme", "neon_green"), THEMES["neon_green"])
        self._clock_flash_base = th["text_running"]
        self._clock_flash_count = max(1, int(duration * 1000 / 120))
        self._clock_flash_on = False
        self._clock_flash_after = self.root.after(120, self._clock_flash_tick)

    def _clock_flash_tick(self):
        if self._clock_flash_count <= 0:
            self._stop_clock_flash(restore=True)
            return
        self._clock_flash_on = not self._clock_flash_on
        color = "#ffffff" if self._clock_flash_on else self._clock_flash_base
        self.time_label.config(fg=color)
        self._clock_flash_count -= 1
        self._clock_flash_after = self.root.after(120, self._clock_flash_tick)

    def _stop_clock_flash(self, restore=True):
        """停止數字閃動；restore=True 時恢復原本計時顏色"""
        if self._clock_flash_after is not None:
            try:
                self.root.after_cancel(self._clock_flash_after)
            except Exception:
                pass
            self._clock_flash_after = None
        if restore and self._clock_flash_base is not None and hasattr(self, "time_label"):
            self.time_label.config(fg=self._clock_flash_base)
        self._clock_flash_count = 0
        self._clock_flash_on = False
        self._clock_flash_base = None


    def _set_clock_text(self, seconds):
        """只在顯示的百分之一秒變化時才更新 Label，避免每 20ms 重繪造成卡頓"""
        ticks = int(seconds * 100)
        if ticks == getattr(self, "_last_clock_ticks", None):
            return
        self._last_clock_ticks = ticks
        self.time_label.config(text=self._format_time(seconds))

    # ----------------- 全域快捷鍵監聽 -----------------
    def _update_vk_map(self):
        hk = self.cfg["hotkeys"]
        self.active_vks = {}
        for action, k in hk.items():
            vk = KEY_VK_MAP.get(k) or KEY_VK_MAP.get(k.capitalize())
            if vk:
                self.active_vks[action] = vk

    def _hotkey_loop(self):
        last_state = {}
        while not self.stop_key_listener:
            vks = dict(self.active_vks)
            for action, vk_code in vks.items():
                is_down = (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0
                was_down = last_state.get(action, False)

                if is_down and not was_down:
                    self._dispatch_action(action)

                last_state[action] = is_down

            time.sleep(0.015)

    def _dispatch_action(self, action):
        if action == "start_pause":
            self.root.after(0, self.toggle_start)
        elif action == "split_hit_down":
            self.root.after(0, self.trigger_split)
        elif action == "reset":
            self.root.after(0, self.reset_timer)
        elif action == "toggle_lock":
            self.root.after(0, self.toggle_lock)
        elif action == "toggle_sound":
            self.root.after(0, self._toggle_sound_mute)

    def _toggle_sound_mute(self):
        cur = self.cfg["sound"].get("enabled", True)
        self.cfg["sound"]["enabled"] = not cur
        self.sound_engine.set_config(enabled=not cur)

    def _bbox_from_cfg(self, ad):
        """將 config 的比例座標換算為螢幕絕對座標；未設定時回傳 None (偵測器使用預設值)"""
        keys = ["bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"]
        if not all(k in ad for k in keys):
            return None
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        return (
            int(screen_w * ad["bbox_x1"]),
            int(screen_h * ad["bbox_y1"]),
            int(screen_w * ad["bbox_x2"]),
            int(screen_h * ad["bbox_y2"]),
        )

    def open_settings(self):
        if self.is_locked:
            self.toggle_lock()
        SettingsWindow(self.root, self.cfg_mgr, self.sound_engine, self.on_settings_applied)

    def on_settings_applied(self, new_cfg):
        self.cfg = new_cfg
        set_lang(self.cfg.get("appearance", {}).get("language", "en"))
        snd = self.cfg["sound"]
        self.sound_engine.set_config(volume=snd.get("volume", 0.20), sound_style=snd.get("style", "lofi"), enabled=snd.get("enabled", True))
        self._update_vk_map()
        self._apply_appearance()

        # 更新自動偵測器參數
        ad = self.cfg.get("auto_detect", {})
        if hasattr(self, 'auto_detector'):
            self.auto_detector.update_thresholds(
                threshold=ad.get("match_threshold"),
                check_interval_ms=ad.get("check_interval"),
                use_icon_detection=ad.get("use_icon_detection")
            )
            # 更新 BBox (如果有設定)
            bbox_keys = ["bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2"]
            if all(k in ad for k in bbox_keys):
                screen_w = user32.GetSystemMetrics(0)
                screen_h = user32.GetSystemMetrics(1)
                bbox = (
                    int(screen_w * ad["bbox_x1"]),
                    int(screen_h * ad["bbox_y1"]),
                    int(screen_w * ad["bbox_x2"]),
                    int(screen_h * ad["bbox_y2"])
                )
                self.auto_detector.set_bbox(bbox)

        if ad.get("enabled", False):
            self.auto_detector.start()
        else:
            self.auto_detector.stop()

        # 除錯視窗與 ROI 覆蓋層：依設定即時開關，不需重啟
        if ad.get("debug", False):
            if self.debug_window is None:
                self._open_debug_window()
            if self.roi_overlay is None:
                self._show_roi_overlay()
        else:
            self._close_debug_window()
            self._hide_roi_overlay()
        self.reset_timer()

    # ----------------- 除錯視窗 -----------------
    def _open_debug_window(self):
        """開啟除錯視窗：顯示 NCC 相似度、判斷區域與放大預覽"""
        if self.debug_window is not None:
            return
        self.debug_enabled = True
        dbg = tk.Toplevel(self.root)
        dbg.title(tr("debug.title"))
        dbg.configure(bg="#181a20")
        dbg.attributes("-topmost", True)
        dbg.resizable(False, False)
        dbg.protocol("WM_DELETE_WINDOW", self._close_debug_window)

        tk.Label(dbg, text="倒地圖標偵測 (即時)", font=("Microsoft JhengHei", 10, "bold"),
                 fg="#00ff88", bg="#181a20").pack(pady=6)

        self.debug_labels = {}
        for key, label in [
            ("score", tr("debug.score")),
            ("threshold", tr("debug.threshold")),
            ("result", tr("debug.result")),
            ("bbox", tr("debug.bbox")),
        ]:
            row = tk.Frame(dbg, bg="#1a1c23")
            row.pack(fill=tk.X, padx=10, pady=2)
            tk.Label(row, text=label + ":", font=("Microsoft JhengHei", 9),
                     fg="#a0a6b5", bg="#1a1c23", width=20, anchor="w").pack(side=tk.LEFT)
            val = tk.Label(row, text="-", font=("Microsoft JhengHei", 9, "bold"),
                           fg="#00ff88", bg="#1a1c23", anchor="e")
            val.pack(side=tk.RIGHT)
            self.debug_labels[key] = val

        # 判斷區域放大預覽 (即模板比對實際使用的畫面)
        self.debug_preview_lbl = tk.Label(dbg, text=tr("debug.preview"), bg="#0d0e12", fg="#666666",
                                          width=40, height=6)
        self.debug_preview_lbl.pack(padx=10, pady=8)

        tk.Button(dbg, text=tr("debug.close"), font=("Microsoft JhengHei", 9),
                  bg="#2a2d36", fg="#d0d4dc", relief=tk.FLAT, padx=10, pady=2,
                  command=self._close_debug_window).pack(pady=(0, 8))

        self.debug_window = dbg
        self.debug_photo = None
        self._start_debug_loop()

    def _close_debug_window(self):
        """關閉除錯視窗 (不影響計時器與偵測)"""
        self.debug_enabled = False
        if self.debug_window is not None:
            try:
                self.debug_window.destroy()
            except Exception:
                pass
            self.debug_window = None
        self.debug_labels = None
        self.debug_preview_lbl = None
        self.debug_photo = None

    # ----------------- 共用更新迴圈 -----------------
    def _start_debug_loop(self):
        """除錯視窗與 ROI 覆蓋層共用一個 200ms 迴圈，每次只擷取一次畫面"""
        if getattr(self, "_debug_loop_running", False):
            return
        self._debug_loop_running = True
        self.root.after(200, self._debug_tick)

    def _debug_tick(self):
        """UI 更新：只讀取背景執行緒的快取結果，主執行緒不做截圖與比對"""
        if not (self.debug_enabled or self.roi_overlay_enabled):
            self._debug_loop_running = False
            return
        try:
            is_downed, stats = self.auto_detector.last_result
            bbox = self.auto_detector.get_bbox()
            self._update_debug_window(is_downed, stats, bbox)
            self._update_roi_status(is_downed, stats, bbox)
        except Exception as e:
            print(f"[WARN DEBUG] {e}")
        self.root.after(100, self._debug_tick)

    def _update_debug_window(self, is_downed, stats, bbox):
        """更新除錯視窗內容"""
        if self.debug_window is None or not self.debug_labels:
            return

        if stats.get("error"):
            self.debug_labels["result"].config(text=tr("debug.error") + ": " + str(stats["error"]), fg="#ff3344")
        else:
            self.debug_labels["score"].config(text="{:.3f}".format(stats.get("score", 0.0)))
            self.debug_labels["threshold"].config(text="{:.2f}".format(stats.get("threshold", 0.0)))
            self.debug_labels["result"].config(text=(tr("debug.downed") if is_downed else tr("debug.normal")),
                                               fg="#ff3344" if is_downed else "#00ff88")
        self.debug_labels["bbox"].config(text="{}, {}, {}, {}".format(*bbox))

        region = stats.get("region")
        if region is not None and self.debug_preview_lbl is not None:
            from PIL import Image, ImageTk
            h, w = region.shape[0], region.shape[1]
            img = Image.fromarray(region).resize((w * 4, h * 4), Image.NEAREST)
            self.debug_photo = ImageTk.PhotoImage(img)
            self.debug_preview_lbl.config(image=self.debug_photo, text="", width=0, height=0)

    # ----------------- 螢幕 ROI 覆蓋層 -----------------
    ROI_PAD = 4          # 框線畫在判斷區域外側，不會進入擷取範圍
    ROI_LABEL_W = 110    # 判斷區域右側的分數文字空間

    def _show_roi_overlay(self):
        """在判斷區域外側畫出框線與即時分數。
        視窗以 SetWindowRgn 挖空判斷區域 (內側完全透明)，並設為點擊穿透。"""
        if self.roi_overlay is not None:
            return
        bbox = self.auto_detector.get_bbox()
        x1, y1, x2, y2 = bbox
        if x2 <= x1 or y2 <= y1:
            print(f"[WARN ROI] bbox 無效: {bbox}，不建立覆蓋層")
            return

        self.roi_overlay_enabled = True
        self.roi_bbox = tuple(bbox)
        pad = self.ROI_PAD
        bw, bh = x2 - x1, y2 - y1
        win_w = bw + pad * 2 + self.ROI_LABEL_W
        win_h = bh + pad * 2

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.attributes("-topmost", True)
        overlay.configure(bg="#101216")
        overlay.geometry(f"{win_w}x{win_h}+{x1 - pad}+{y1 - pad}")

        canvas = tk.Canvas(overlay, width=win_w, height=win_h,
                           bg="#101216", highlightthickness=0, bd=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        self.roi_rect = canvas.create_rectangle(pad - 3, pad - 3, pad + bw + 2, pad + bh + 2,
                                                outline="#00ff00", width=2)
        self.roi_text = canvas.create_text(pad + bw + 10, win_h // 2, text=tr("debug.waiting"),
                                           fill="#ffff00", anchor="w",
                                           font=("Microsoft JhengHei", 10, "bold"))

        overlay.update_idletasks()
        self._apply_roi_window_style(overlay, win_w, win_h, pad, bw, bh)

        self.roi_overlay = overlay
        self.roi_canvas = canvas
        print(f"[DEBUG ROI] 建立覆蓋層: 視窗 {win_w}x{win_h}, 判斷區域 {bbox}")
        self._start_debug_loop()

    def _apply_roi_window_style(self, overlay, win_w, win_h, pad, bw, bh):
        """以 Win32 API 設定視窗形狀 (挖空) 與點擊穿透"""
        try:
            # wm_frame() 回傳的是外層視窗 HWND (十六進位字串)
            hwnd = int(overlay.wm_frame(), 16)
            gdi32 = ctypes.windll.gdi32
            gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
            gdi32.CreateRectRgn.restype = ctypes.c_void_p
            gdi32.CombineRgn.argtypes = [ctypes.c_void_p] * 3 + [ctypes.c_int]
            gdi32.CombineRgn.restype = ctypes.c_int
            gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
            user32.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
            user32.SetWindowRgn.restype = ctypes.c_int
            user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

            # 外框矩形減去判斷區域 = 只保留外側框線，內側挖空
            outer = gdi32.CreateRectRgn(0, 0, win_w, win_h)
            inner = gdi32.CreateRectRgn(pad, pad, pad + bw, pad + bh)
            gdi32.CombineRgn(outer, outer, inner, 4)  # RGN_DIFF = 4
            gdi32.DeleteObject(inner)
            # SetWindowRgn 成功後系統擁有 outer 區域，不可再 DeleteObject
            user32.SetWindowRgn(hwnd, outer, True)

            # 點擊穿透 + 不出現在工作列
            # 注意：不加 WS_EX_LAYERED，Tk 未設定 SetLayeredWindowAttributes，加了會導致覆蓋層不顯示
            WS_EX_TOOLWINDOW = 0x00000080
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW)
            print(f"[DEBUG ROI] 視窗樣式已套用 hwnd={hwnd}")
        except Exception as e:
            print(f"[WARN ROI] 視窗樣式設定失敗: {e}")

    def _hide_roi_overlay(self):
        """隱藏 ROI 覆蓋層"""
        self.roi_overlay_enabled = False
        if self.roi_overlay is not None:
            try:
                self.roi_overlay.destroy()
            except Exception:
                pass
        self.roi_overlay = None
        self.roi_canvas = None

    def _update_roi_status(self, is_downed, stats, bbox):
        """更新覆蓋層分數與框色；判斷區域改變時重建覆蓋層"""
        if not self.roi_overlay_enabled or self.roi_canvas is None:
            return
        if tuple(bbox) != self.roi_bbox:
            self._hide_roi_overlay()
            self._show_roi_overlay()
            return

        if stats.get("error"):
            text, color = tr("debug.error"), "#ff3344"
        elif is_downed:
            text, color = tr("roi.downed").format(stats.get("score", 0.0)), "#ff3344"
        else:
            text, color = tr("roi.normal").format(stats.get("score", 0.0)), "#00ff00"
        self.roi_canvas.itemconfig(self.roi_text, text=text, fill=color)
        self.roi_canvas.itemconfig(self.roi_rect, outline=color)

    def close(self):
        self.cfg["startup"]["remember_x"] = self.root.winfo_x()
        self.cfg["startup"]["remember_y"] = self.root.winfo_y()
        self.cfg_mgr.save()
        save_history(self.history)
        self.stop_key_listener = True
        if hasattr(self, 'auto_detector'):
            self.auto_detector.stop()
        if hasattr(self, 'debug_enabled') and self.debug_enabled:
            self._close_debug_window()
        if hasattr(self, 'roi_overlay') and self.roi_overlay is not None:
            self._hide_roi_overlay()
        self._stop_clock_flash(restore=False)
        self.root.destroy()


def _cli_debug_enabled(argv):
    """CLI 是否帶除錯旗標：--debug 或 -d (不寫回 config.json)"""
    return "--debug" in (argv or []) or "-d" in (argv or [])


def main():
    # 必須在建立任何視窗前設定 DPI 感知，座標與截圖才會一致
    from fast_grab import set_dpi_aware
    set_dpi_aware()
    root = tk.Tk()
    app = DBDDuelTimer(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.bind("<Escape>", lambda e: app.close() if not app.is_locked else None)

    # 除錯啟動：--debug / -d 開啟除錯面板與判斷框 (不寫回 config.json)
    if _cli_debug_enabled(sys.argv[1:]):
        root.after(150, app._open_debug_window)
        root.after(150, app._show_roi_overlay)

    root.mainloop()


if __name__ == "__main__":
    main()
