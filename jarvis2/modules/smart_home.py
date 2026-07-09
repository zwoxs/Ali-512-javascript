"""Akıllı Ev — Home Assistant REST API (Sonoff S60 vb.).

Cihaz takma adları config/smart_home_devices.json içinde tutulur:
    { "priz": "switch.sonoff_s60", "lamba": "light.salon" }

HOME_ASSISTANT_URL ve HOME_ASSISTANT_TOKEN yoksa modül available=False olur.
"""
import json
import os
import threading

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

_CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
_DEVICES_PATH = os.path.join(_CONFIG_DIR, "smart_home_devices.json")


class SmartHome:
    def __init__(self):
        self.base_url = (os.getenv("HOME_ASSISTANT_URL") or "").rstrip("/")
        self.token = os.getenv("HOME_ASSISTANT_TOKEN")
        self.devices = self._load_devices()
        self._timers = {}  # device -> threading.Timer
        self.available = bool(_REQUESTS_OK and self.base_url and self.token)

    # ---------- cihaz kayıtları ----------
    @staticmethod
    def _load_devices() -> dict:
        try:
            with open(_DEVICES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # varsayılan tek cihaz
            return {"priz": "switch.sonoff_s60"}

    def _save_devices(self) -> None:
        with open(_DEVICES_PATH, "w", encoding="utf-8") as f:
            json.dump(self.devices, f, ensure_ascii=False, indent=2)

    def add_device(self, alias: str, entity_id: str) -> None:
        self.devices[alias.strip().lower()] = entity_id.strip()
        self._save_devices()

    def remove_device(self, alias: str) -> bool:
        key = alias.strip().lower()
        if key in self.devices:
            del self.devices[key]
            self._save_devices()
            return True
        return False

    def _entity(self, device: str) -> str:
        return self.devices.get(device.strip().lower(), device)

    def _domain(self, entity_id: str) -> str:
        return entity_id.split(".")[0] if "." in entity_id else "switch"

    # ---------- HTTP yardımcıları ----------
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def check_connection(self) -> bool:
        if not self.available:
            return False
        try:
            r = requests.get(f"{self.base_url}/api/", headers=self._headers(), timeout=5)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def _call_service(self, domain: str, service: str, entity_id: str) -> bool:
        if not self.available:
            return False
        try:
            r = requests.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self._headers(),
                json={"entity_id": entity_id},
                timeout=10,
            )
            return r.status_code in (200, 201)
        except requests.RequestException:
            return False

    # ---------- temel kontroller ----------
    def turn_on(self, device: str = "priz") -> bool:
        entity = self._entity(device)
        return self._call_service(self._domain(entity), "turn_on", entity)

    def turn_off(self, device: str = "priz") -> bool:
        entity = self._entity(device)
        return self._call_service(self._domain(entity), "turn_off", entity)

    def toggle(self, device: str = "priz") -> bool:
        entity = self._entity(device)
        return self._call_service(self._domain(entity), "toggle", entity)

    def get_state(self, device: str = "priz") -> str:
        if not self.available:
            return "bağlantı yok"
        entity = self._entity(device)
        try:
            r = requests.get(
                f"{self.base_url}/api/states/{entity}",
                headers=self._headers(), timeout=10,
            )
            if r.status_code == 200:
                return r.json().get("state", "bilinmiyor")
            return "bilinmiyor"
        except requests.RequestException:
            return "bağlantı hatası"

    def get_power(self, device: str = "priz"):
        """Cihazın anlık güç tüketimi (W) — attribute varsa döndürür."""
        if not self.available:
            return None
        entity = self._entity(device)
        try:
            r = requests.get(
                f"{self.base_url}/api/states/{entity}",
                headers=self._headers(), timeout=10,
            )
            if r.status_code == 200:
                attrs = r.json().get("attributes", {})
                return attrs.get("current_power_w") or attrs.get("power")
        except requests.RequestException:
            pass
        return None

    # ---------- toplu ----------
    def turn_on_all(self) -> None:
        for alias in self.devices:
            self.turn_on(alias)

    def turn_off_all(self) -> None:
        for alias in self.devices:
            self.turn_off(alias)

    # ---------- zamanlayıcı ----------
    def schedule_turn_off(self, device: str, seconds: int) -> None:
        self.cancel_timer(device)
        t = threading.Timer(seconds, self.turn_off, args=[device])
        t.daemon = True
        t.start()
        self._timers[device] = t

    def schedule_turn_on(self, device: str, seconds: int) -> None:
        self.cancel_timer(device)
        t = threading.Timer(seconds, self.turn_on, args=[device])
        t.daemon = True
        t.start()
        self._timers[device] = t

    def cancel_timer(self, device: str) -> bool:
        t = self._timers.pop(device, None)
        if t:
            t.cancel()
            return True
        return False
