# -*- coding: utf-8 -*-
"""
BBox Picker - 全螢幕框選工具
讓使用者用滑鼠拖曳框出頭像區域，回傳像素座標
"""

import tkinter as tk
from i18n import tr


class BBoxPicker:
    def __init__(self, callback):
        """
        參數:
            callback: Callable[[tuple], None] - 框選完成後呼叫，傳入 (x1, y1, x2, y2) 或 None (取消)
        """
        self.callback = callback
        self.root = tk.Toplevel()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.3)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black")
        self.root.overrideredirect(True)  # 無視窗邊框

        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()

        # Canvas 用來畫選擇框
        self.canvas = tk.Canvas(
            self.root, width=self.screen_w, height=self.screen_h,
            bg="black", highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack()

        # 框選狀態
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.final_bbox = None

        # 提示文字
        self.label = tk.Label(
            self.root,
            text=tr("picker.hint"),
            fg="lime", bg="black", font=("Microsoft JhengHei", 14, "bold")
        )
        self.label.place(relx=0.5, rely=0.1, anchor="center")

        # 綁定滑鼠事件
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.root.bind("<Escape>", lambda e: self._cancel())

        self.root.focus_force()
        self.root.grab_set()  # 模態，阻止其他視窗操作

    def _on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="lime", width=3
        )

    def _on_drag(self, event):
        if self.start_x is None:
            return
        self.canvas.coords(
            self.rect_id, self.start_x, self.start_y, event.x, event.y
        )

    def _on_release(self, event):
        if self.start_x is None:
            return
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        # 確保 x1<x2, y1<y2
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        self.final_bbox = (x1, y1, x2, y2)
        self.root.grab_release()
        self.root.destroy()
        if self.callback:
            self.callback(self.final_bbox)

    def _cancel(self):
        self.root.grab_release()
        self.root.destroy()
        if self.callback:
            self.callback(None)