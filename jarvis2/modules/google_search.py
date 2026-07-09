"""Web Arama — DuckDuckGo Instant Answer API (anahtar gerektirmez).

Gerçek metin sonuçları döndürür; başarısız olursa tarayıcıda Google araması açar.
"""
import urllib.parse
import webbrowser

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


class WebSearch:
    def __init__(self, max_results: int = 3):
        self.max_results = max_results

    def search(self, query: str) -> dict:
        """{'answer': str, 'results': [ {title, text, url} ]} döndürür."""
        query = (query or "").strip()
        if not query:
            return {"answer": "", "results": []}
        if not _REQUESTS_OK:
            return {"answer": "", "results": []}

        try:
            r = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1,
                        "skip_disambig": 1, "kl": "tr-tr"},
                timeout=8,
            )
            if r.status_code != 200:
                return {"answer": "", "results": []}
            d = r.json()

            answer = d.get("AbstractText") or d.get("Answer") or ""
            results = []
            for topic in d.get("RelatedTopics", []):
                if "Text" in topic and "FirstURL" in topic:
                    results.append({
                        "title": topic["Text"].split(" - ")[0],
                        "text": topic["Text"],
                        "url": topic["FirstURL"],
                    })
                if len(results) >= self.max_results:
                    break
            return {"answer": answer, "results": results}
        except requests.RequestException:
            return {"answer": "", "results": []}

    def summary(self, query: str) -> str:
        data = self.search(query)
        if data["answer"]:
            return data["answer"]
        if data["results"]:
            lines = [f"• {r['text']}" for r in data["results"]]
            return "İşte bulduklarım, Efendim:\n" + "\n".join(lines)
        return ""

    def open_in_browser(self, query: str) -> None:
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open(url)
