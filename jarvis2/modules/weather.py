"""Hava Durumu — OpenWeatherMap API (opsiyonel).

OWM_API_KEY yoksa modül available=False olur ve HUD widget'ı gizlenir.
"""
import os

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

_ICONS = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
    "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️",
    "Haze": "🌫️", "Smoke": "🌫️",
}


class Weather:
    def __init__(self):
        self.api_key = os.getenv("OWM_API_KEY")
        self.city = os.getenv("OWM_CITY", "Istanbul")
        self.available = bool(_REQUESTS_OK and self.api_key)
        self._cache = None
        self._cache_ts = 0

    def get(self) -> dict:
        """{'temp', 'desc', 'icon', 'city'} döndürür; hata olursa boş dict."""
        if not self.available:
            return {}
        import time
        # 10 dakika önbellek
        if self._cache and (time.time() - self._cache_ts) < 600:
            return self._cache
        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": self.city, "appid": self.api_key,
                        "units": "metric", "lang": "tr"},
                timeout=8,
            )
            if r.status_code != 200:
                return {}
            d = r.json()
            main = d["weather"][0]["main"]
            result = {
                "temp": round(d["main"]["temp"]),
                "desc": d["weather"][0]["description"].capitalize(),
                "icon": _ICONS.get(main, "🌡️"),
                "city": d.get("name", self.city),
                "feels": round(d["main"].get("feels_like", d["main"]["temp"])),
                "humidity": d["main"].get("humidity"),
            }
            self._cache = result
            self._cache_ts = time.time()
            return result
        except requests.RequestException:
            return {}

    def summary(self) -> str:
        w = self.get()
        if not w:
            return "Hava durumu bilgisi alınamadı, Efendim."
        return (f"{w['city']}: {w['icon']} {w['temp']}°C, {w['desc']}. "
                f"Hissedilen {w['feels']}°C, nem %{w['humidity']}.")
