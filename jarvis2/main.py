"""JARVIS2 — giriş noktası.

Konsol tabanlı etkileşimli döngü + opsiyonel sesli komut modu.
Tüm modüller eksik paket/anahtar durumunda zarifçe devre dışı kalır,
sistem yine klavyeyle çalışmaya devam eder.

Çalıştırma:
    python main.py            # konsol modu
    python main.py --voice    # sesli dinleme de açık
"""
import sys

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv kurulu değilse .env okumayı atla
    def load_dotenv(*args, **kwargs):
        return False

from config.loader import load_settings
from memory.manager import MemoryManager
from modules.ai_brain import AIBrain
from modules.smart_home import SmartHome
from modules.whatsapp import WhatsApp
from modules.daily_planner import DailyPlanner
from voice.output import VoiceOutput
from voice.input import VoiceInput
from core.orchestrator import Orchestrator


def build_system():
    load_dotenv()
    settings = load_settings()

    memory = MemoryManager()
    voice_output = VoiceOutput(settings)
    smart_home = SmartHome()
    ai_brain = AIBrain(settings, smart_home=smart_home)
    whatsapp = WhatsApp(memory=memory)
    planner = DailyPlanner(ai_brain=ai_brain)

    orchestrator = Orchestrator(
        settings=settings,
        memory=memory,
        ai_brain=ai_brain,
        smart_home=smart_home,
        whatsapp=whatsapp,
        planner=planner,
        voice_output=voice_output,
    )
    return settings, orchestrator, voice_output, smart_home, ai_brain


def print_status(settings, orchestrator, smart_home, ai_brain):
    name = settings.get("assistant_name", "JARVIS")
    print("=" * 48)
    print(f"  {name} v2 — hazır")
    print("=" * 48)
    print(f"  AI Brain (Groq) : {'✅ aktif' if ai_brain.available else '❌ çevrimdışı'}")
    print(f"  Akıllı Ev       : {'✅ bağlı' if smart_home.check_connection() else '❌ bağlantı yok'}")
    print(f"  Ses çıkışı      : ✅")
    print("  Çıkmak için: çık / exit  |  Yardım: yardım")
    print("=" * 48)


def main():
    voice_mode = "--voice" in sys.argv
    settings, orchestrator, voice_output, smart_home, ai_brain = build_system()

    # bildirimleri konsola bas
    orchestrator.set_notify_callback(lambda m: print(f"\n{m}\n> ", end=""))

    print_status(settings, orchestrator, smart_home, ai_brain)

    greeting = orchestrator.handle("günaydın")
    print(f"\nJARVIS: {greeting}\n")
    voice_output.speak(greeting, blocking=False)

    # ----- opsiyonel sesli mod -----
    voice_input = None
    if voice_mode:
        def on_voice_command(cmd):
            print(f"\n[🎤 duyuldu] {cmd}")
            resp = orchestrator.handle(cmd, from_voice=True)
            if resp == "__EXIT__":
                print("JARVIS: Görüşmek üzere, Efendim.")
                voice_output.speak("Görüşmek üzere, Efendim.")
                sys.exit(0)
            print(f"JARVIS: {resp}\n> ", end="")
            voice_output.speak(resp)

        voice_input = VoiceInput(settings, on_command=on_voice_command)
        if voice_input.available:
            voice_input.start()
            print("🎤 Sesli mod aktif — uyanma kelimesi:",
                  settings.get("wake_word", "jarvis"))
        else:
            print("⚠️  Ses girişi kullanılamıyor (SpeechRecognition/PyAudio eksik).")

    # ----- konsol döngüsü -----
    try:
        while True:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue

            resp = orchestrator.handle(text)

            if resp == "__EXIT__":
                farewell = "Görüşmek üzere, Efendim."
                print(f"JARVIS: {farewell}")
                voice_output.speak(farewell)
                break
            if resp == "__CLEAR__":
                print("\n" * 50)
                continue
            if resp.startswith("__THEME__:"):
                print(f"JARVIS: Tema {resp.split(':', 1)[1]} olarak ayarlandı (UI modunda geçerli).")
                continue

            print(f"JARVIS: {resp}\n")
            voice_output.speak(resp, blocking=False)
    finally:
        if voice_input:
            voice_input.stop()


if __name__ == "__main__":
    main()
