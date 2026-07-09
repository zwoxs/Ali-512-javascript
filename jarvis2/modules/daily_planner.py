"""Günlük Planlayıcı — AI varsa Groq'tan dinamik plan, yoksa yerel mesaj."""
import random
from datetime import datetime


class DailyPlanner:
    def __init__(self, ai_brain=None):
        self.ai_brain = ai_brain
        self._local = {
            "sabah": [
                "Günaydın Efendim. Bugünün en önemli işini seçip onunla başlayın.",
                "Günaydın! Kısa bir kahvaltı ve net bir öncelik listesiyle güne başlayalım.",
            ],
            "ogle": [
                "Öğle vakti Efendim. Kısa bir mola verip enerjinizi tazeleyin.",
                "Günün yarısı geçti; en kritik işi öğleden sonraya bırakmayın.",
            ],
            "aksam": [
                "İyi akşamlar Efendim. Günü değerlendirip yarına küçük bir plan yapın.",
                "Akşam oldu; tamamlanan işleri gözden geçirmek için güzel bir zaman.",
            ],
            "gece": [
                "İyi geceler Efendim. Dinlenmek de üretkenliğin bir parçasıdır.",
                "Gece ilerledi; ekranları kapatıp güzel bir uykuya hazırlanın.",
            ],
        }

    def _period(self) -> str:
        h = datetime.now().hour
        if 5 <= h < 12:
            return "sabah"
        if 12 <= h < 18:
            return "ogle"
        if 18 <= h < 22:
            return "aksam"
        return "gece"

    def plan(self) -> str:
        if self.ai_brain and getattr(self.ai_brain, "available", False):
            return self.ai_brain.daily_briefing()
        return random.choice(self._local[self._period()])
