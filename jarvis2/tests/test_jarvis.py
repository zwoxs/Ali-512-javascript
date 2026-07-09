"""JARVIS2 birim testleri — harici bağımlılık/ağ gerektirmez.

Çalıştırma:
    cd jarvis2 && python -m unittest discover tests
    veya: python -m pytest tests/
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.loader import load_settings
from memory.manager import MemoryManager
from core.intent_parser import IntentParser
from core.orchestrator import Orchestrator
from modules.whatsapp import WhatsApp
from modules.daily_planner import DailyPlanner


class TestIntentParser(unittest.TestCase):
    def setUp(self):
        self.p = IntentParser(load_settings())

    def _act(self, text):
        return self.p.parse(text)["action"]

    def test_time_date(self):
        self.assertEqual(self._act("saat kaç"), "time")
        self.assertEqual(self._act("bugün tarih ne"), "date")

    def test_greet_and_morning(self):
        self.assertEqual(self._act("merhaba"), "greet")
        self.assertEqual(self._act("günaydın"), "morning_routine")

    def test_devices(self):
        self.assertEqual(self._act("priz aç"), "device_on")
        self.assertEqual(self._act("lamba kapat"), "device_off")
        self.assertEqual(self._act("priz durumu"), "device_state")

    def test_reminder_parsing(self):
        r = self.p.parse("10 dakika sonra su iç hatırlat")
        self.assertEqual(r["action"], "reminder")
        self.assertEqual(r["params"]["seconds"], 600)
        self.assertIn("su", r["params"]["text"])

    def test_system_controls(self):
        self.assertEqual(self._act("ekranı kilitle"), "lock")
        self.assertEqual(self._act("ekran görüntüsü al"), "screenshot")
        self.assertEqual(self.p.parse("ses seviyesi 40")["params"]["percent"], 40)
        self.assertEqual(self._act("sonraki şarkı"), "media")

    def test_bluetooth_routes(self):
        self.assertEqual(self._act("bluetooth tara"), "bt_scan")
        self.assertEqual(self._act("ses cihazlarını listele"), "bt_audio_list")
        self.assertEqual(self._act("eşleşmiş cihazlar"), "bt_paired")
        r = self.p.parse("hoparlörden konuş")
        self.assertEqual(r["action"], "bt_speak")
        self.assertIn("hoparlör", r["params"]["device"])
        self.assertEqual(self._act("sesi varsayılana al"), "bt_reset")

    def test_bluetooth_connect_and_alias(self):
        r = self.p.parse("kulaklığa bağlan")
        self.assertEqual(r["action"], "bt_connect")
        self.assertIn("kulak", r["params"]["device"])
        r2 = self.p.parse("jbl hoparlöre bağlansın")
        self.assertEqual(r2["action"], "bt_connect")
        r3 = self.p.parse("takma ad ekle kulaklık AirPods Pro")
        self.assertEqual(r3["action"], "bt_alias")
        self.assertEqual(r3["params"]["alias"], "kulaklık")
        self.assertIn("airpods", r3["params"]["device"].lower())

    def test_ui_switch_routes(self):
        self.assertEqual(self.p.parse("arayüzü telefona geçir")["params"]["target"], "phone")
        self.assertEqual(self.p.parse("arayüzü bilgisayara al")["params"]["target"], "desktop")
        self.assertEqual(self.p.parse("yanıma gel")["params"]["target"], "phone")
        self.assertEqual(self.p.parse("telefona geç")["params"]["target"], "phone")

    def test_device_classification(self):
        from modules.bluetooth_manager import BluetoothManager as BM
        self.assertEqual(BM.classify_device("iPhone 15 Pro"), "phone")
        self.assertEqual(BM.classify_device("AirPods Pro"), "headphone")
        self.assertEqual(BM.classify_device("JBL Flip 6"), "speaker")
        self.assertEqual(BM.classify_device("Bilinmeyen Cihaz"), "unknown")

    def test_weather_and_wakeword(self):
        self.assertEqual(self._act("hava durumu"), "weather")
        # uyanma kelimesi temizleniyor
        self.assertEqual(self._act("jarvis saat kaç"), "time")

    def test_fallback_to_ai(self):
        self.assertEqual(self._act("bana bir fıkra anlat"), "ai_brain")

    def test_slash_command(self):
        self.assertEqual(self._act("/help"), "command")


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryManager(tempfile.mkdtemp())

    def test_contacts(self):
        self.mem.add_contact("Ahmet", "+905551112233")
        self.assertEqual(self.mem.get_contact("ahmet"), "+905551112233")
        self.assertIn("ahmet", self.mem.list_contacts())
        self.assertTrue(self.mem.remove_contact("ahmet"))
        self.assertIsNone(self.mem.get_contact("ahmet"))

    def test_notes(self):
        self.mem.add_note("Süt al")
        self.assertEqual(len(self.mem.list_notes()), 1)
        self.assertTrue(self.mem.delete_note(0))
        self.assertEqual(len(self.mem.list_notes()), 0)

    def test_todos(self):
        self.mem.add_todo("Rapor", "yüksek")
        self.assertFalse(self.mem.list_todos()[0]["done"])
        self.mem.toggle_todo(0)
        self.assertTrue(self.mem.list_todos()[0]["done"])
        self.assertTrue(self.mem.delete_todo(0))

    def test_reminders(self):
        self.mem.add_reminder("test", "2030-01-01T10:00:00")
        self.assertEqual(len(self.mem.list_reminders()), 1)
        self.mem.mark_reminder_done(0)
        self.assertEqual(len(self.mem.list_reminders()), 0)
        self.assertEqual(len(self.mem.list_reminders(include_done=True)), 1)


class TestWhatsApp(unittest.TestCase):
    def setUp(self):
        self.mem = MemoryManager(tempfile.mkdtemp())
        self.wa = WhatsApp(memory=self.mem)

    def test_number_normalization(self):
        self.assertEqual(self.wa._normalize_number("0555 111 22 33"), "905551112233")
        self.assertTrue(self.wa.is_valid_number("+90 555 111 22 33"))
        self.assertFalse(self.wa.is_valid_number("123"))

    def test_import_contacts(self):
        count = self.wa.import_contacts_from_text("Ali, 05551112233\nVeli: 05559998877")
        self.assertEqual(count, 2)
        self.assertEqual(len(self.mem.list_contacts()), 2)


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        s = load_settings()
        mem = MemoryManager(tempfile.mkdtemp())
        self.o = Orchestrator(s, mem, planner=DailyPlanner())

    def test_time_response(self):
        self.assertIn("Saat", self.o.handle("saat kaç"))

    def test_exit(self):
        self.assertEqual(self.o.handle("çık"), "__EXIT__")

    def test_unknown_without_ai(self):
        # ai_brain yok -> ai_brain action UNKNOWN'a düşer
        resp = self.o.handle("rastgele anlamsız cümle burada")
        self.assertIsInstance(resp, str)

    def test_stats_increment(self):
        before = self.o.stats["commands"]
        self.o.handle("saat kaç")
        self.assertEqual(self.o.stats["commands"], before + 1)

    def test_add_and_list_contact(self):
        self.o.handle("kişi ekle mehmet +905551110000")
        self.assertIn("mehmet", self.o.handle("whatsapp kişileri listele").lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
