# -*- coding: utf-8 -*-
"""
DBD 1v1 Timer - Lo-Fi Sound Engine
純 Python 內建標準庫合成溫潤柔和的 Lo-Fi 音效，無爆音、無刺耳蜂鳴、支援音量調節
"""

import io
import math
import struct
import wave
import winsound
import threading

class LoFiSoundEngine:
    def __init__(self, volume=0.20, sound_style="lofi", enabled=True):
        self.volume = max(0.0, min(1.0, float(volume)))
        self.sound_style = sound_style
        self.enabled = enabled
        self._cache = {}
        self._preload_sounds()

    def set_config(self, volume=None, sound_style=None, enabled=None):
        if volume is not None:
            self.volume = max(0.0, min(1.0, float(volume)))
        if sound_style is not None:
            self.sound_style = sound_style
        if enabled is not None:
            self.enabled = enabled
        self._cache.clear()
        self._preload_sounds()

    def _preload_sounds(self):
        """預先合成所有音效至記憶體中，按鍵觸發零延遲"""
        if not self.enabled or self.volume <= 0.001 or self.sound_style == "mute":
            return
        sound_names = ["startup", "start", "pause", "hit", "down", "reset", "toggle_lock", "alarm", "lap"]
        for s in sound_names:
            self._cache[s] = self._synthesize(s)

    def _synthesize(self, sound_type):
        sample_rate = 22050
        buffer = io.BytesIO()

        if self.sound_style == "classic":
            # 經典電子音
            freq_map = {
                "startup": [(800, 0.4, 15.0), (1200, 0.5, 12.0)],
                "start": [(1100, 0.7, 16.0)],
                "pause": [(750, 0.7, 16.0)],
                "hit": [(1400, 0.8, 14.0)],
                "down": [(1800, 0.6, 12.0), (1300, 0.7, 10.0)],
                "reset": [(600, 0.7, 18.0)],
                "toggle_lock": [(950, 0.8, 25.0)],
                "alarm": [(1200, 0.7, 8.0)],
                "lap": [(1300, 0.7, 15.0)]
            }
            freqs = freq_map.get(sound_type, [(880, 0.6, 15.0)])
            duration = 0.15
        else:
            # 預設 Lo-Fi 暖音風格 (如木琴/電鋼琴/溫潤正弦波，柔和衰減)
            if sound_type == "startup":
                # 溫潤 C 和弦琶音 (C4 -> E4 -> G4)
                freqs = [(261.6, 0.45, 9.0), (329.6, 0.45, 9.0), (392.0, 0.50, 9.0)]
                duration = 0.24
            elif sound_type == "start":
                # 木質暖敲 (340Hz 圓潤衰減)
                freqs = [(340.0, 0.85, 18.0), (170.0, 0.35, 20.0)]
                duration = 0.12
            elif sound_type == "pause":
                # 低沈溫柔空心音 (220Hz)
                freqs = [(220.0, 0.90, 20.0)]
                duration = 0.12
            elif sound_type == "hit":
                # 溫潤 Rhodes 電鋼單音 (523Hz + 微弱八度泛音)
                freqs = [(523.2, 0.75, 13.0), (1046.5, 0.18, 22.0)]
                duration = 0.16
            elif sound_type == "down":
                # 暖色小三度下行 (392Hz -> 330Hz)
                freqs = [(392.0, 0.55, 9.0), (329.6, 0.65, 7.5)]
                duration = 0.22
            elif sound_type == "reset":
                # 輕柔低頻滑音 (196Hz)
                freqs = [(196.0, 0.80, 22.0)]
                duration = 0.10
            elif sound_type == "toggle_lock":
                # 軟鍵切換微敲 (580Hz 極短)
                freqs = [(580.0, 0.80, 35.0)]
                duration = 0.06
            elif sound_type == "alarm":
                # 倒數歸零 暖鈴 (587Hz & 880Hz 柔和泛音)
                freqs = [(587.3, 0.6, 6.0), (880.0, 0.5, 6.0)]
                duration = 0.35
            elif sound_type == "lap":
                # 記圈柔和提示 (440Hz)
                freqs = [(440.0, 0.8, 14.0)]
                duration = 0.14
            else:
                freqs = [(440.0, 0.7, 15.0)]
                duration = 0.15

        n_samples = int(sample_rate * duration)
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            data = bytearray()
            for i in range(n_samples):
                t = i / sample_rate
                sample_val = 0.0
                for f, amp, decay in freqs:
                    # 柔和 4ms 緩入 + 指數衰減，無爆音
                    env = math.exp(-t * decay) * min(1.0, t * 250.0)
                    wave_val = math.sin(2 * math.pi * f * t)
                    # 溫暖泛音
                    wave_val += 0.15 * math.sin(4 * math.pi * f * t)
                    sample_val += wave_val * env * amp

                sample_val *= self.volume
                int_val = int(max(-32767, min(32767, sample_val * 32767)))
                data.extend(struct.pack("<h", int_val))
            wav.writeframes(data)
        return buffer.getvalue()

    def play(self, sound_type):
        """非阻塞非同步播放 Lo-Fi 音效"""
        if not self.enabled or self.volume <= 0.001 or self.sound_style == "mute":
            return

        wav_bytes = self._cache.get(sound_type)
        if not wav_bytes:
            wav_bytes = self._synthesize(sound_type)
            self._cache[sound_type] = wav_bytes

        def _worker():
            try:
                winsound.PlaySound(wav_bytes, winsound.SND_MEMORY)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()
