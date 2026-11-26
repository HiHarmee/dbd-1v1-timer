# -*- coding: utf-8 -*-
"""
DBD 1v1 Timer - 設定視窗 (深色卡片式)
- 分頁：外觀 / 快捷鍵 / 計時 / 音效 / 倒地偵測
- 底部：還原預設 / 取消 / 套用 / 儲存並關閉
"""

import tkinter as tk
from tkinter import ttk
import ctypes

from config_manager import THEMES, KEY_VK_MAP, DEFAULT_CONFIG
from history_manager import load_history, save_history, render_text
from i18n import set_lang, tr

user32 = ctypes.windll.user32

# ---- 色盤 ----
BG = "#0f1117"          # 視窗背景
CARD = "#1b202b"        # 卡片
CARD_LINE = "#2b3342"   # 卡片邊線
TEXT = "#e8edf5"        # 主文字
TEXT_DIM = "#8d98aa"    # 次要文字
ACCENT = "#00d47e"      # 強調色 (綠)
DANGER = "#ff4d5e"      # 危險操作
BTN = "#262c3a"         # 一般按鈕
BTN_HOVER = "#313849"
FONT = "Microsoft JhengHei"


class SettingsWindow:
    def __init__(self, parent, config_manager, sound_engine, on_apply_callback):
        self.parent = parent
        self.cfg_mgr = config_manager
        self.sound_engine = sound_engine
        self.on_apply = on_apply_callback

        self.cfg = self.cfg_mgr.load()
        set_lang(self.cfg.get("appearance", {}).get("language", "en"))

        self.top = tk.Toplevel(parent)
        self.top.title(tr("settings.title"))
        self.top.geometry("460x820")
        self.top.minsize(440, 640)
        self.top.configure(bg=BG)
        self.top.attributes("-topmost", True)

        self._build_header()
        self._build_footer()
        self._build_tabs()
        self._select_tab(0)

    # ---------- 通用元件 ----------
    def _build_header(self):
        header = tk.Frame(self.top, bg=BG)
        header.pack(fill=tk.X, padx=16, pady=(14, 6))
        tk.Label(header, text=tr("settings.header"), font=(FONT, 13, "bold"),
                 fg=TEXT, bg=BG).pack(side=tk.LEFT)
        tk.Label(header, text=tr("settings.hint"), font=(FONT, 8),
                 fg=TEXT_DIM, bg=BG).pack(side=tk.RIGHT, pady=(4, 0))

        self.tab_bar = tk.Frame(self.top, bg=BG)
        self.tab_bar.pack(fill=tk.X, padx=16, pady=(4, 8))
        self.tab_buttons = []
        self.pages = []

    def _build_footer(self):
        footer = tk.Frame(self.top, bg=BG)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=14)

        self._button(footer, tr("settings.reset"), self._reset_defaults, DANGER, TEXT).pack(side=tk.LEFT)
        self._button(footer, tr("settings.cancel"), self.top.destroy, BTN, TEXT_DIM).pack(side=tk.RIGHT)
        self._button(footer, tr("settings.save_close"), self._save_and_close, ACCENT, "#06130c").pack(side=tk.RIGHT, padx=8)
        self._button(footer, tr("settings.apply"), self._apply_only, BTN, TEXT).pack(side=tk.RIGHT)

    def _button(self, parent, text, command, bg, fg):
        btn = tk.Button(parent, text=text, command=command, font=(FONT, 9, "bold"),
                        bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                        relief=tk.FLAT, bd=0, padx=14, pady=6, cursor="hand2")
        btn.bind("<Enter>", lambda e: btn.config(bg=BTN_HOVER if bg == BTN else bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        return btn

    def _card(self, parent, title=None):
        """卡片：深色底 + 細邊線，回傳內容 Frame"""
        outer = tk.Frame(parent, bg=CARD_LINE, padx=1, pady=1)
        outer.pack(fill=tk.X, pady=6)
        inner = tk.Frame(outer, bg=CARD, padx=14, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)
        if title:
            tk.Label(inner, text=title, font=(FONT, 9, "bold"), fg=ACCENT, bg=CARD).pack(anchor="w", pady=(0, 6))
        return inner

    def _label(self, parent, text, dim=False):
        return tk.Label(parent, text=text, font=(FONT, 9), fg=TEXT_DIM if dim else TEXT, bg=CARD)

    def _radio(self, parent, text, value, var):
        return tk.Radiobutton(parent, text=text, value=value, variable=var, font=(FONT, 9),
                              fg=TEXT, bg=CARD, activeforeground=TEXT, activebackground=CARD,
                              selectcolor=BG, highlightthickness=0)

    def _check(self, parent, text, var):
        return tk.Checkbutton(parent, text=text, variable=var, font=(FONT, 9),
                              fg=TEXT, bg=CARD, activeforeground=TEXT, activebackground=CARD,
                              selectcolor=BG, highlightthickness=0)

    def _slider(self, parent, var, frm, to, resolution, fmt, command_extra=None):
        """滑桿 + 右側數值標籤，回傳 (frame, value_label)"""
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill=tk.X)
        val_lbl = tk.Label(row, text=fmt(var.get()), font=(FONT, 9, "bold"),
                           fg=ACCENT, bg=CARD, width=7, anchor="e")
        val_lbl.pack(side=tk.RIGHT)

        def on_move(v):
            val_lbl.config(text=fmt(float(v)))
            if command_extra:
                command_extra(v)

        tk.Scale(row, from_=frm, to=to, resolution=resolution, orient=tk.HORIZONTAL,
                 variable=var, showvalue=0, bg=CARD, troughcolor=BG,
                 activebackground=ACCENT, highlightthickness=0, bd=0,
                 command=on_move).pack(side=tk.LEFT, fill=tk.X, expand=True)
        return row, val_lbl

    # ---------- 分頁切換 ----------
    def _add_tab(self, title):
        """建立分頁按鈕與可捲動內容頁，回傳內容 Frame"""
        idx = len(self.pages)
        btn = tk.Label(self.tab_bar, text=title, font=(FONT, 9, "bold"),
                       fg=TEXT_DIM, bg=BG, padx=10, pady=5, cursor="hand2")
        btn.pack(side=tk.LEFT, padx=(0, 4))
        btn.bind("<Button-1>", lambda e, i=idx: self._select_tab(i))
        self.tab_buttons.append(btn)

        page = tk.Frame(self.top, bg=BG, padx=16)
        page.pack_propagate(True)
        self.pages.append(page)
        return page

    def _select_tab(self, idx):
        for i, (btn, page) in enumerate(zip(self.tab_buttons, self.pages)):
            if i == idx:
                btn.config(fg=ACCENT, bg=CARD)
                page.pack(fill=tk.BOTH, expand=True)
                if i == getattr(self, "_history_tab_index", -1):
                    self._refresh_history()  # 切到紀錄分頁時自動讀取最新
            else:
                btn.config(fg=TEXT_DIM, bg=BG)
                page.pack_forget()

    # ---------- 分頁內容 ----------
    def _build_tabs(self):
        self._build_display_tab()
        self._build_hotkeys_tab()
        self._build_timing_tab()
        self._build_sound_tab()
        self._build_auto_detect_tab()
        self._build_history_tab()

    def _build_display_tab(self):
        page = self._add_tab(tr("settings.tabs.appearance"))

        c = self._card(page, tr("settings.appearance.bg_style"))
        self.bg_mode_var = tk.StringVar(value=self.cfg["appearance"].get("bg_mode", "transparent"))
        self._radio(c, tr("settings.appearance.bg_transparent"), "transparent", self.bg_mode_var).pack(anchor="w", pady=2)
        self._radio(c, tr("settings.appearance.bg_dark"), "dark_tint", self.bg_mode_var).pack(anchor="w", pady=2)

        c = self._card(page, tr("settings.appearance.font_size"))
        self.font_size_var = tk.StringVar(value=self.cfg["appearance"].get("font_size", "huge"))
        row = tk.Frame(c, bg=CARD)
        row.pack(anchor="w")
        for val, name in [("huge", tr("settings.appearance.font_huge")),
                          ("large", tr("settings.appearance.font_large")),
                          ("normal", tr("settings.appearance.font_normal"))]:
            self._radio(row, name, val, self.font_size_var).pack(side=tk.LEFT, padx=(0, 10))

        c = self._card(page, tr("settings.appearance.theme"))
        self.theme_var = tk.StringVar(value=self.cfg["appearance"].get("theme", "neon_green"))
        grid = tk.Frame(c, bg=CARD)
        grid.pack(anchor="w")
        for i, (k, v) in enumerate(THEMES.items()):
            self._radio(grid, v["name"], k, self.theme_var).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=2)

        c = self._card(page, tr("settings.appearance.position"))
        self.pos_var = tk.StringVar(value=self.cfg["startup"].get("position", "top_center"))
        row = tk.Frame(c, bg=CARD)
        row.pack(anchor="w")
        for p_val, p_name in [("top_center", tr("settings.appearance.pos_top_center")),
                              ("top_right", tr("settings.appearance.pos_top_right")),
                              ("remember", tr("settings.appearance.pos_remember"))]:
            self._radio(row, p_name, p_val, self.pos_var).pack(side=tk.LEFT, padx=(0, 10))

        c = self._card(page, tr("settings.appearance.language"))
        self.lang_var = tk.StringVar(value=self.cfg["appearance"].get("language", "en"))
        row = tk.Frame(c, bg=CARD)
        row.pack(anchor="w")
        self._radio(row, tr("settings.appearance.lang_en"), "en", self.lang_var).pack(side=tk.LEFT, padx=(0, 12))
        self._radio(row, tr("settings.appearance.lang_zh"), "zh-TW", self.lang_var).pack(side=tk.LEFT, padx=(0, 12))
        self._radio(row, tr("settings.appearance.lang_zh_cn"), "zh-CN", self.lang_var).pack(side=tk.LEFT)

    def _build_hotkeys_tab(self):
        page = self._add_tab(tr("settings.tabs.hotkeys"))
        c = self._card(page, tr("settings.hotkeys.title"))

        key_list = list(KEY_VK_MAP.keys())
        self.hk_vars = {}
        fields = [
            ("start_pause", tr("settings.hotkeys.start")),
            ("split_hit_down", tr("settings.hotkeys.hit")),
            ("reset", tr("settings.hotkeys.reset")),
            ("toggle_lock", tr("settings.hotkeys.lock")),
            ("toggle_sound", tr("settings.hotkeys.sound")),
        ]
        defaults = {"start_pause": "T", "split_hit_down": "F2", "reset": "Del",
                    "toggle_lock": "F4", "toggle_sound": "F8"}
        for k_id, label in fields:
            row = tk.Frame(c, bg=CARD)
            row.pack(fill=tk.X, pady=4)
            self._label(row, label).pack(side=tk.LEFT)
            default_val = defaults.get(k_id, "F1")
            var = tk.StringVar(value=self.cfg["hotkeys"].get(k_id, default_val))
            self.hk_vars[k_id] = var
            ttk.Combobox(row, textvariable=var, values=key_list, state="readonly", width=10).pack(side=tk.RIGHT)

    def _build_timing_tab(self):
        page = self._add_tab(tr("settings.tabs.timing"))

        c = self._card(page, tr("settings.timing.mode"))
        self.timing_mode_var = tk.StringVar(value=self.cfg["timing"].get("mode", "dbd_1v1"))
        self._radio(c, tr("settings.timing.dbd"), "dbd_1v1", self.timing_mode_var).pack(anchor="w", pady=2)
        self._radio(c, tr("settings.timing.stopwatch"), "stopwatch", self.timing_mode_var).pack(anchor="w", pady=2)
        self._radio(c, tr("settings.timing.countdown"), "countdown", self.timing_mode_var).pack(anchor="w", pady=2)

        c = self._card(page, tr("settings.timing.rounds"))
        self.auto_next_var = tk.BooleanVar(value=self.cfg["timing"].get("auto_next_round", True))
        self._check(c, tr("settings.timing.auto_next"), self.auto_next_var).pack(anchor="w", pady=2)

    def _build_auto_detect_tab(self):
        page = self._add_tab(tr("settings.tabs.detect"))
        ad = self.cfg["auto_detect"]

        c = self._card(page, tr("settings.detect.toggles"))
        self.auto_detect_var = tk.BooleanVar(value=ad.get("enabled", False))
        self._check(c, tr("settings.detect.enable"), self.auto_detect_var).pack(anchor="w", pady=2)
        self.use_icon_detection_var = tk.BooleanVar(value=ad.get("use_icon_detection", True))
        self._check(c, tr("settings.detect.red_match"), self.use_icon_detection_var).pack(anchor="w", pady=2)

        c = self._card(page, tr("settings.detect.params"))
        self._label(c, tr("settings.detect.threshold")).pack(anchor="w")
        self.match_threshold_var = tk.DoubleVar(value=ad.get("match_threshold", 0.5))
        self._slider(c, self.match_threshold_var, 0.20, 0.90, 0.01, lambda v: "{:.2f}".format(float(v)))
        self._label(c, tr("settings.detect.interval"), dim=True).pack(anchor="w", pady=(10, 0))
        self.interval_var = tk.IntVar(value=ad.get("check_interval", 150))
        self._slider(c, self.interval_var, 50, 500, 10, lambda v: "{} ms".format(int(float(v))))

        c = self._card(page, tr("settings.detect.region"))
        self._button(c, tr("settings.detect.pick"), self._open_bbox_picker, ACCENT, "#06130c").pack(anchor="w", pady=(0, 8))

        # 進階 / 除錯選項：預設收合
        c = self._card(page, None)
        self.debug_var = tk.BooleanVar(value=ad.get("debug", False))
        self.bbox_vars = {}
        self._build_advanced_section(c)

    def _build_advanced_section(self, parent):
        """進階 / 除錯區塊：標題可展開收合，內容包含除錯面板開關與 BBox 微調"""
        ad = self.cfg["auto_detect"]
        self._advanced_open = False

        head = tk.Label(parent, text=tr("settings.detect.advanced"), font=(FONT, 9, "bold"),
                        fg=TEXT_DIM, bg=CARD, cursor="hand2")
        head.pack(anchor="w")

        body = tk.Frame(parent, bg=CARD)

        self._check(body, tr("settings.detect.debug"), self.debug_var).pack(anchor="w", pady=2)
        self._label(body, tr("settings.detect.bbox_fine"), dim=True).pack(anchor="w", pady=(8, 0))

        grid = tk.Frame(body, bg=CARD)
        grid.pack(fill=tk.X, pady=(4, 0))
        defaults = [("x1", 0.028), ("y1", 0.744), ("x2", 0.065), ("y2", 0.796)]
        for i, (key, default) in enumerate(defaults):
            var = tk.DoubleVar(value=ad.get("bbox_" + key, default))
            self.bbox_vars[key] = var
            cell = tk.Frame(grid, bg=CARD)
            cell.grid(row=0, column=i, sticky="ew", padx=3)
            grid.columnconfigure(i, weight=1)
            tk.Label(cell, text=key.upper(), font=(FONT, 8), fg=TEXT_DIM, bg=CARD).pack()
            tk.Scale(cell, from_=0.0, to=1.0, resolution=0.001, orient=tk.HORIZONTAL,
                     variable=var, showvalue=0, bg=CARD, troughcolor=BG,
                     highlightthickness=0, bd=0, activebackground=ACCENT).pack(fill=tk.X)

        def toggle(_event=None):
            self._advanced_open = not self._advanced_open
            if self._advanced_open:
                head.config(text=tr("settings.detect.advanced_open"))
                body.pack(fill=tk.X, pady=(4, 0))
            else:
                head.config(text=tr("settings.detect.advanced"))
                body.pack_forget()

        head.bind("<Button-1>", toggle)
        self._advanced_body = body

    def _build_history_tab(self):
        """紀錄分頁：顯示 history.json 內容，可重新整理或清除"""
        self._history_tab_index = len(self.pages)  # 記住此分頁編號
        page = self._add_tab(tr("settings.tabs.history"))

        ctrl = tk.Frame(page, bg=BG)
        ctrl.pack(fill=tk.X, pady=(0, 4))
        self._label(ctrl, tr("settings.history.desc"), dim=True).pack(side=tk.LEFT)
        self._button(ctrl, tr("settings.history.refresh"), self._refresh_history, BTN, TEXT).pack(side=tk.RIGHT)
        self._button(ctrl, tr("settings.history.clear"), self._clear_history, DANGER, TEXT).pack(side=tk.RIGHT, padx=6)

        outer = tk.Frame(page, bg=CARD_LINE, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(outer, bg=CARD, padx=8, pady=8)
        inner.pack(fill=tk.BOTH, expand=True)

        self.history_text = tk.Text(inner, bg=CARD, fg=TEXT, font=(FONT, 10),
                                    wrap=tk.NONE, relief=tk.FLAT, bd=0,
                                    highlightthickness=0, insertbackground=TEXT, state=tk.DISABLED)
        self.history_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(inner, command=self.history_text.yview, bg=BG, troughcolor=CARD, bd=0)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_text.configure(yscrollcommand=sb.set)
        self._refresh_history()

    def _refresh_history(self):
        """重新讀取 history.json 並更新文字區"""
        if getattr(self, "history_text", None) is None:
            return
        text = render_text(load_history())
        self.history_text.config(state=tk.NORMAL)
        self.history_text.delete("1.0", tk.END)
        self.history_text.insert("1.0", text)
        self.history_text.config(state=tk.DISABLED)

    def _clear_history(self):
        from tkinter import messagebox
        if messagebox.askyesno(tr("settings.history.confirm_title"), tr("settings.history.confirm_msg")):
            save_history([])
            self._refresh_history()

    def _open_bbox_picker(self):
        """開啟全螢幕框選工具，框選結果寫回比例座標"""
        self.top.withdraw()

        def on_bbox_selected(bbox):
            if bbox is None:
                self.top.deiconify()
                return
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            self.bbox_vars["x1"].set(round(bbox[0] / screen_w, 4))
            self.bbox_vars["y1"].set(round(bbox[1] / screen_h, 4))
            self.bbox_vars["x2"].set(round(bbox[2] / screen_w, 4))
            self.bbox_vars["y2"].set(round(bbox[3] / screen_h, 4))
            self.top.deiconify()

        from bbox_picker import BBoxPicker
        BBoxPicker(on_bbox_selected)

    # ---------- 存檔 / 套用 ----------
    def _collect(self):
        """收集目前所有控件的值，組成設定字典"""
        return {
            "hotkeys": {k: v.get() for k, v in self.hk_vars.items()},
            "startup": {
                "mode": self.cfg["startup"].get("mode", "unlocked"),
                "position": self.pos_var.get(),
                "remember_x": self.cfg["startup"].get("remember_x", 800),
                "remember_y": self.cfg["startup"].get("remember_y", 25),
                "play_sound": self.cfg["startup"].get("play_sound", True),
            },
            "timing": {
                "mode": self.timing_mode_var.get(),
                "countdown_seconds": self.cfg["timing"].get("countdown_seconds", 60),
                "auto_next_round": self.auto_next_var.get(),
            },
            "appearance": {
                "bg_mode": self.bg_mode_var.get(),
                "font_size": self.font_size_var.get(),
                "theme": self.theme_var.get(),
                "opacity": self.cfg["appearance"].get("opacity", 0.95),
                "language": self.lang_var.get(),
            },
            "sound": {
                "enabled": self.sound_enabled_var.get(),
                "volume": round(self.volume_var.get(), 2),
                "style": self.sound_style_var.get(),
            },
            "auto_detect": {
                "enabled": self.auto_detect_var.get(),
                "check_interval": int(self.interval_var.get()),
                "match_threshold": round(self.match_threshold_var.get(), 2),
                "use_icon_detection": self.use_icon_detection_var.get(),
                "debug": self.debug_var.get(),
                "bbox_x1": round(self.bbox_vars["x1"].get(), 4),
                "bbox_y1": round(self.bbox_vars["y1"].get(), 4),
                "bbox_x2": round(self.bbox_vars["x2"].get(), 4),
                "bbox_y2": round(self.bbox_vars["y2"].get(), 4),
            },
        }

    def _apply_only(self):
        """套用：寫入設定並即時生效，視窗保持開啟"""
        new_cfg = self._collect()
        self.cfg_mgr.save(new_cfg)
        self.on_apply(new_cfg)

    def _save_and_close(self):
        self._apply_only()
        self.top.destroy()

    def _reset_defaults(self):
        self.cfg_mgr.save(DEFAULT_CONFIG)
        self.on_apply(DEFAULT_CONFIG)
        self.top.destroy()

    def _build_sound_tab(self):
        page = self._add_tab(tr("settings.tabs.sound"))

        c = self._card(page, tr("settings.sound.title"))
        self.sound_enabled_var = tk.BooleanVar(value=self.cfg["sound"].get("enabled", True))
        self._check(c, tr("settings.sound.enable"), self.sound_enabled_var).pack(anchor="w", pady=2)

        self._label(c, tr("settings.sound.style"), dim=True).pack(anchor="w", pady=(8, 2))
        self.sound_style_var = tk.StringVar(value=self.cfg["sound"].get("style", "lofi"))
        row = tk.Frame(c, bg=CARD)
        row.pack(anchor="w")
        for s_val, s_name in [("lofi", tr("settings.sound.lofi")), ("classic", tr("settings.sound.classic")), ("mute", tr("settings.sound.mute"))]:
            self._radio(row, s_name, s_val, self.sound_style_var).pack(side=tk.LEFT, padx=(0, 10))

        self._label(c, tr("settings.sound.volume"), dim=True).pack(anchor="w", pady=(8, 2))
        self.volume_var = tk.DoubleVar(value=self.cfg["sound"].get("volume", 0.20))
        self._slider(c, self.volume_var, 0.0, 1.0, 0.05,
                     lambda v: "{}%".format(int(round(float(v) * 100))))

        c = self._card(page, tr("settings.sound.preview"))
        row = tk.Frame(c, bg=CARD)
        row.pack(anchor="w")
        for s_val, s_type in [("settings.sound.play_start", "start"), ("settings.sound.play_pause", "pause"),
                              ("settings.sound.play_hit", "hit"), ("settings.sound.play_down", "down")]:
            self._button(row, tr(s_val), lambda st=s_type: self._preview(st), BTN, TEXT).pack(side=tk.LEFT, padx=(0, 6))

    def _preview(self, sound_type):
        self.sound_engine.set_config(volume=self.volume_var.get(),
                                     sound_style=self.sound_style_var.get(), enabled=True)
        self.sound_engine.play(sound_type)

