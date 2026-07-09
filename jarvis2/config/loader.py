"""Ayar yükleyici — settings.json'u okur, canlı yeniden yükleme destekler."""
import json
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_SETTINGS_PATH = os.path.join(_BASE_DIR, "settings.json")

_DEFAULTS = {
    "assistant_name": "JARVIS",
    "wake_word": "jarvis",
    "language": "tr-TR",
    "tts_voice": "tr-TR-EmelNeural",
    "tts_voice_en": "en-US-SoniaNeural",
    "tts_rate": 170,
    "tts_pitch": "+0Hz",
    "tts_volume": 1.0,
    "owner_name": "Efendim",
    "search_results_count": 3,
    "require_wake_word": True,
    "ai_model": "llama-3.3-70b-versatile",
    "ai_fallback_model": "llama-3.1-8b-instant",
}


def load_settings() -> dict:
    """settings.json'u oku; eksik/bozuksa varsayılanlara düş."""
    data = dict(_DEFAULTS)
    try:
        with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return data


def save_settings(settings: dict) -> None:
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
