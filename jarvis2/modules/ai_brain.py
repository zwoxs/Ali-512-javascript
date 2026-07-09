"""AI Brain — Groq API (llama-3.3-70b-versatile) ile doğal dil işleme.

Özellikler:
- Genel sohbet / soru-cevap
- Function calling ile akıllı ev (priz) kontrolü
- Kota dolunca otomatik model fallback
- Günlük özet (daily_briefing)

`groq` paketi veya GROQ_API_KEY yoksa modül `available=False` olur ve
çağıranlar zarif biçimde bir uyarı mesajı alır.
"""
import json
import os
from datetime import datetime

try:
    from groq import Groq
    _GROQ_IMPORT_OK = True
except ImportError:
    _GROQ_IMPORT_OK = False


SYSTEM_PROMPT = (
    "Sen JARVIS adında, Türkçe konuşan bir yapay zeka masaüstü asistanısın. "
    "Kısa, net ve saygılı cevaplar verirsin. Kullanıcıya 'Efendim' diye hitap "
    "edebilirsin. Gereksiz uzatma, doğrudan konuya gir."
)

# Akıllı ev fonksiyon tanımları (function calling)
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Akıllı ev cihazını (priz, lamba vb.) açar, kapatır veya durumunu sorgular.",
            "parameters": {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Cihaz adı, örn: priz, lamba, klima",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["turn_on", "turn_off", "get_state"],
                        "description": "Yapılacak işlem",
                    },
                },
                "required": ["device", "action"],
            },
        },
    }
]


class AIBrain:
    def __init__(self, settings: dict, smart_home=None):
        self.settings = settings
        self.smart_home = smart_home
        self.model = settings.get("ai_model", "llama-3.3-70b-versatile")
        self.fallback_model = settings.get("ai_fallback_model", "llama-3.1-8b-instant")
        self._client = None
        self.available = False

        api_key = os.getenv("GROQ_API_KEY")
        if _GROQ_IMPORT_OK and api_key:
            try:
                self._client = Groq(api_key=api_key)
                self.available = True
            except Exception as e:  # pragma: no cover
                print(f"[AIBrain] Groq başlatılamadı: {e}")

    # ---------- düşük seviye çağrı (fallback'li) ----------
    def _complete(self, messages, tools=None):
        """Ana modeli dener, kota/hata durumunda fallback modele geçer."""
        last_err = None
        for model in (self.model, self.fallback_model):
            try:
                kwargs = {"model": model, "messages": messages, "temperature": 0.6}
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                return self._client.chat.completions.create(**kwargs)
            except Exception as e:  # kota, ağ vb.
                last_err = e
                continue
        raise last_err

    # ---------- genel sorgu ----------
    def ask(self, user_text: str, history: list = None) -> str:
        if not self.available:
            return ("AI beyni şu anda çevrimdışı, Efendim. "
                    "GROQ_API_KEY ayarlı mı ve `groq` paketi kurulu mu kontrol edin.")

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in (history or [])[-6:]:
            messages.append({"role": "user", "content": h.get("user", "")})
            messages.append({"role": "assistant", "content": h.get("jarvis", "")})
        messages.append({"role": "user", "content": user_text})

        try:
            resp = self._complete(messages, tools=_TOOLS)
            msg = resp.choices[0].message

            # Function calling isteği var mı?
            if getattr(msg, "tool_calls", None):
                return self._handle_tool_calls(messages, msg)

            return (msg.content or "").strip()
        except Exception as e:
            return f"AI beyninde bir hata oluştu, Efendim: {e}"

    # ---------- function calling işleyici ----------
    def _handle_tool_calls(self, messages, assistant_msg) -> str:
        messages.append({
            "role": "assistant",
            "content": assistant_msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in assistant_msg.tool_calls
            ],
        })

        for tc in assistant_msg.tool_calls:
            result = self._execute_tool(tc.function.name, tc.function.arguments)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        # Sonucu doğal dile çevirmesi için modele geri ver
        final = self._complete(messages)
        return (final.choices[0].message.content or "").strip()

    def _execute_tool(self, name: str, arguments: str) -> str:
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return "Geçersiz argüman."

        if name == "control_device":
            if not self.smart_home or not self.smart_home.available:
                return "Akıllı ev bağlantısı yok."
            device = args.get("device", "priz")
            action = args.get("action", "get_state")
            if action == "turn_on":
                ok = self.smart_home.turn_on(device)
                return f"{device} açıldı." if ok else f"{device} açılamadı."
            if action == "turn_off":
                ok = self.smart_home.turn_off(device)
                return f"{device} kapatıldı." if ok else f"{device} kapatılamadı."
            state = self.smart_home.get_state(device)
            return f"{device} durumu: {state}"

        return "Bilinmeyen fonksiyon."

    # ---------- günlük özet ----------
    def daily_briefing(self) -> str:
        if not self.available:
            return self._local_briefing()
        now = datetime.now()
        prompt = (
            f"Şu an {now.strftime('%A %d %B %Y, saat %H:%M')}. "
            "Kullanıcıya kısa (3-4 cümle), motive edici, güne uygun bir günlük "
            "brifing/plan öner. Sabit bir programa bağlı kalma, saate göre uyarla."
        )
        try:
            resp = self._complete([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ])
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return self._local_briefing()

    @staticmethod
    def _local_briefing() -> str:
        h = datetime.now().hour
        if h < 12:
            return "Günaydın Efendim. Güne enerjik başlayın; önceliklerinizi belirleyip ilk işe odaklanın."
        if h < 18:
            return "İyi günler Efendim. Öğleden sonra en önemli işinizi bitirmek için ideal zaman."
        if h < 22:
            return "İyi akşamlar Efendim. Günü değerlendirin, yarın için kısa bir plan yapın."
        return "İyi geceler Efendim. Dinlenmeyi ihmal etmeyin, yarın taze bir başlangıç sizi bekliyor."
