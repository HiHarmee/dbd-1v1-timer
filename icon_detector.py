# -*- coding: utf-8 -*-
"""
DBD 倒地圖標偵測 (紅色形狀比對, Dice 係數)
- 參考圖 downed_ref_roi.png：倒地時的判斷區域截圖
- 只看「紅色剪影」的形狀，不比對整塊畫面，避免頭像與背景干擾
- 候選區域允許 ±SHIFT 像素平移，容忍截圖位置誤差
- 僅依賴 numpy / PIL (專案已使用)
"""

import os
import sys
import numpy as np
from PIL import Image

# PyInstaller onefile：資源解壓在 sys._MEIPASS；開發時用專案目錄
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
_EXE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else BASE_DIR
DEFAULT_TEMPLATE = os.path.join(BASE_DIR, "downed_ref_roi.png")
if not os.path.exists(DEFAULT_TEMPLATE):
    DEFAULT_TEMPLATE = os.path.join(_EXE_DIR, "downed_ref_roi.png")
SHIFT = 4


def red_mask(arr):
    """紅色像素遮罩 (float32 0/1)，arr: (H, W, 3)"""
    r = arr[..., 0]
    g = arr[..., 1]
    b = arr[..., 2]
    return ((r > 120) & (r - g > 60) & (r - b > 60)).astype(np.float32)


def _shift(mask, dy, dx):
    """平移遮罩，超出範圍補 0"""
    h, w = mask.shape
    out = np.zeros_like(mask)
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        mask[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return out


def dice_best(cand, tpl, shift=SHIFT):
    """在 ±shift 範圍內平移候選遮罩，回傳最高 Dice 係數 (0~1)"""
    best = 0.0
    tsum = float(tpl.sum())
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            sh = _shift(cand, dy, dx)
            denom = float(sh.sum()) + tsum
            if denom <= 0:
                continue
            best = max(best, 2.0 * float((sh * tpl).sum()) / denom)
    return best


class DownedIconMatcher:
    """
    倒地圖標形狀比對器

    參數:
        template_path: 倒地參考截圖路徑
        threshold: Dice 門檻，>= 視為倒地 (config: match_threshold)
        pad: 保留參數 (相容舊呼叫)，實際位移範圍為 SHIFT
    """

    def __init__(self, template_path=DEFAULT_TEMPLATE, threshold=0.5, pad=2):
        self.template_path = template_path
        tpl_img = Image.open(template_path).convert("RGB")
        self.tpl_size = tpl_img.size  # (W, H)
        self.template_mask = red_mask(np.asarray(tpl_img, dtype=np.float32))
        self.threshold = threshold

    def score(self, region):
        """回傳 ROI 與倒地參考的紅色形狀 Dice 分數 (0~1)"""
        img = Image.fromarray(np.clip(region, 0, 255).astype(np.uint8))
        if img.size != self.tpl_size:
            img = img.resize(self.tpl_size, Image.Resampling.BILINEAR)
        cand = red_mask(np.asarray(img, dtype=np.float32))
        return dice_best(cand, self.template_mask)

    def is_downed(self, region):
        """回傳 (是否倒地, Dice 分數)"""
        s = self.score(region)
        return s >= self.threshold, s
