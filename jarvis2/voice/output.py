"""Ses Çıkışı — edge-tts (online) + pyttsx3 (offline fallback).

edge-tts yoksa/başarısızsa pyttsx3'e düşer. İkisi de yoksa metni konsola yazar.
"""
import asyncio
import os
import tempfile
import threading

try:
    import edge_tts
    _EDGE_OK = True
except ImportError:
    _EDGE_OK = False

try:
    import pygame
    _PYGAME_OK = True
except ImportError:
    _PYGAME_OK = False

try:
    import pyttsx3
    _PYTTSX3_OK = True
except ImportError:
    _PYTTSX3_OK = False


class VoiceOutput:
    def __init__(self, settings: dict):
        self.settings = settings
        self.muted = False
        self._lock = threading.Lock()
        self._pyttsx = None

        if _PYGAME_OK:
            try:
                pygame.mixer.init()
            except Exception:
                pass

    def reload_settings(self, settings: dict) -> None:
        self.settings = settings

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        return self.muted

    # ---------- ana giriş ----------
    def speak(self, text: str, blocking: bool = True) -> None:
        if self.muted or not text:
            return
        if blocking:
            self._speak_now(text)
        else:
            t = threading.Thread(target=self._speak_now, args=(text,), daemon=True)
            t.start()

    def _speak_now(self, text: str) -> None:
        with self._lock:
            if _EDGE_OK and _PYGAME_OK:
                try:
                    self._speak_edge(text)
                    return
                except Exception:
                    pass  # fallback'e düş
            if _PYTTSX3_OK:
                try:
                    self._speak_pyttsx3(text)
                    return
                except Exception:
                    pass
            # son çare
            print(f"[JARVIS 🔊] {text}")

    # ---------- edge-tts ----------
    def _speak_edge(self, text: str) -> None:
        voice = self.settings.get("tts_voice", "tr-TR-EmelNeural")
        pitch = self.settings.get("tts_pitch", "+0Hz")
        # edge-tts rate'i yüzde ister; ayarlardaki wpm'i kabaca eşle
        rate_wpm = self.settings.get("tts_rate", 170)
        rate_pct = max(-50, min(50, int((rate_wpm - 170) / 2)))
        rate = f"{'+' if rate_pct >= 0 else ''}{rate_pct}%"

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        try:
            asyncio.run(self._edge_save(text, voice, rate, pitch, tmp.name))
            pygame.mixer.music.load(tmp.name)
            pygame.mixer.music.set_volume(float(self.settings.get("tts_volume", 1.0)))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
        finally:
            try:
                os.remove(tmp.name)
            except OSError:
                pass

    @staticmethod
    async def _edge_save(text, voice, rate, pitch, path):
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(path)

    # ---------- pyttsx3 (offline) ----------
    def _speak_pyttsx3(self, text: str) -> None:
        if self._pyttsx is None:
            self._pyttsx = pyttsx3.init()
        self._pyttsx.setProperty("rate", int(self.settings.get("tts_rate", 170)))
        self._pyttsx.setProperty("volume", float(self.settings.get("tts_volume", 1.0)))
        self._pyttsx.say(text)
        self._pyttsx.runAndWait()
