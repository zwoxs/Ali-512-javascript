"""Ses Girişi — SpeechRecognition + Google Speech API.

Sürekli dinleme modu, uyanma kelimesi ("jarvis") desteği, pause/resume
(JARVIS konuşurken kendini duymasın).

SpeechRecognition / PyAudio yoksa modül available=False olur; sistem yine
klavye girişiyle çalışabilir.
"""
import threading
import time

try:
    import speech_recognition as sr
    _SR_OK = True
except ImportError:
    _SR_OK = False


class VoiceInput:
    def __init__(self, settings: dict, on_command=None, on_status=None):
        self.settings = settings
        self.on_command = on_command      # callable(text)
        self.on_status = on_status        # callable(status_str)
        self.wake_word = settings.get("wake_word", "jarvis").lower()
        self.require_wake_word = settings.get("require_wake_word", True)
        self.language = settings.get("language", "tr-TR")

        self._paused = False
        self._running = False
        self._thread = None
        self.available = _SR_OK

        if _SR_OK:
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True
            try:
                self.microphone = sr.Microphone()
            except Exception:
                self.available = False
                self.microphone = None

    def _status(self, s: str) -> None:
        if self.on_status:
            try:
                self.on_status(s)
            except Exception:
                pass

    # ---------- pause / resume ----------
    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # ---------- kalibrasyon ----------
    def calibrate(self, duration: float = 1.0) -> None:
        if not self.available:
            return
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
        except Exception:
            pass

    # ---------- sürekli dinleme ----------
    def start(self) -> None:
        if not self.available or self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        self.calibrate()
        last_calib = time.time()
        while self._running:
            if self._paused:
                time.sleep(0.2)
                continue

            # periyodik kalibrasyon (30 sn)
            if time.time() - last_calib > 30:
                self.calibrate(0.5)
                last_calib = time.time()

            text = self._listen_once()
            if not text:
                continue

            text = text.lower().strip()
            if self.require_wake_word:
                if self.wake_word not in text:
                    continue
                # "jarvis priz aç" -> uyanma kelimesini at, kalanı komut yap
                command = text.split(self.wake_word, 1)[1].strip()
                if not command:
                    self._status("listening")
                    self._emit("Efendim?")  # sadece uyanma; kullanıcı devam etsin
                    command = self._listen_once()
                    command = (command or "").lower().strip()
                if command:
                    self._dispatch(command)
            else:
                self._dispatch(text)

    def _listen_once(self, timeout: float = 5, phrase_limit: float = 8):
        self._status("listening")
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
            self._status("processing")
            return self.recognizer.recognize_google(audio, language=self.language)
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except Exception:
            return None
        finally:
            self._status("idle")

    def _dispatch(self, command: str) -> None:
        if self.on_command:
            self.pause()  # JARVIS konuşurken kendini duymasın
            try:
                self.on_command(command)
            finally:
                self.resume()

    def _emit(self, text: str) -> None:
        # yalnızca bilgi amaçlı; gerçek konuşma orchestrator/main tarafında
        self._status(f"say:{text}")
