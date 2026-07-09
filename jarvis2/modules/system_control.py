"""Sistem Kontrolü — ses seviyesi, kilit, ekran görüntüsü, medya tuşları.

Windows'ta tam işlevsel; diğer platformlarda mümkün olanı yapar, gerisini
zarifçe atlar. Harici bağımlılık gerektirmez (yalnızca stdlib + opsiyonel).
"""
import os
import platform
import subprocess
from datetime import datetime

_IS_WIN = platform.system() == "Windows"
_IS_MAC = platform.system() == "Darwin"
_IS_LINUX = platform.system() == "Linux"


class SystemControl:
    def __init__(self):
        self.platform = platform.system()

    # ---------- ses seviyesi ----------
    def set_volume(self, percent: int) -> str:
        percent = max(0, min(100, int(percent)))
        try:
            if _IS_WIN:
                # nircmd yoksa PowerShell ile dene
                self._win_volume(percent)
            elif _IS_MAC:
                subprocess.run(["osascript", "-e",
                                f"set volume output volume {percent}"], check=False)
            elif _IS_LINUX:
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master",
                                f"{percent}%"], check=False,
                               capture_output=True)
            return f"Ses seviyesi %{percent} yapıldı, Efendim."
        except Exception as e:
            return f"Ses seviyesi ayarlanamadı: {e}"

    def _win_volume(self, percent):
        # PowerShell üzerinden WScript.Shell ile kaba kontrol
        steps = round(percent / 2)  # 0-50 arası VolumeUp basımı
        ps = (
            "$o=New-Object -ComObject WScript.Shell;"
            "1..50 | %{ $o.SendKeys([char]174) };"  # önce sıfırla (kıs)
            f"1..{steps} | %{{ $o.SendKeys([char]175) }}"  # sonra yükselt
        )
        subprocess.run(["powershell", "-c", ps], check=False, capture_output=True)

    def mute(self) -> str:
        try:
            if _IS_WIN:
                subprocess.run(["powershell", "-c",
                                "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"],
                               check=False, capture_output=True)
            elif _IS_MAC:
                subprocess.run(["osascript", "-e", "set volume output muted true"], check=False)
            elif _IS_LINUX:
                subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "toggle"],
                               check=False, capture_output=True)
            return "Ses kapatıldı/açıldı, Efendim."
        except Exception as e:
            return f"İşlem başarısız: {e}"

    # ---------- kilit / uyku ----------
    def lock_screen(self) -> str:
        try:
            if _IS_WIN:
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
            elif _IS_MAC:
                subprocess.run(["pmset", "displaysleepnow"], check=False)
            elif _IS_LINUX:
                # yaygın kilit komutlarını sırayla dene
                for cmd in (["loginctl", "lock-session"],
                            ["xdg-screensaver", "lock"],
                            ["gnome-screensaver-command", "-l"]):
                    if subprocess.run(cmd, check=False, capture_output=True).returncode == 0:
                        break
            return "Ekran kilitlendi, Efendim."
        except Exception as e:
            return f"Kilitlenemedi: {e}"

    def sleep(self) -> str:
        try:
            if _IS_WIN:
                subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                               check=False)
            elif _IS_MAC:
                subprocess.run(["pmset", "sleepnow"], check=False)
            elif _IS_LINUX:
                subprocess.run(["systemctl", "suspend"], check=False)
            return "Sistem uyku moduna alınıyor, Efendim."
        except Exception as e:
            return f"Uyku başarısız: {e}"

    # ---------- ekran görüntüsü ----------
    def screenshot(self, directory: str = None) -> str:
        directory = directory or os.path.expanduser("~")
        fname = f"jarvis_ss_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = os.path.join(directory, fname)
        try:
            # önce pyautogui/PIL varsa onu kullan
            try:
                import pyautogui
                pyautogui.screenshot(path)
                return f"Ekran görüntüsü kaydedildi: {path}"
            except ImportError:
                pass
            if _IS_MAC:
                subprocess.run(["screencapture", path], check=False)
            elif _IS_LINUX:
                subprocess.run(["import", "-window", "root", path], check=False)
            else:
                return "Ekran görüntüsü için pyautogui kurulu değil, Efendim."
            if os.path.exists(path):
                return f"Ekran görüntüsü kaydedildi: {path}"
            return "Ekran görüntüsü alınamadı, Efendim."
        except Exception as e:
            return f"Ekran görüntüsü hatası: {e}"

    # ---------- medya tuşları ----------
    def media(self, action: str) -> str:
        """action: play_pause / next / prev"""
        keymap_win = {"play_pause": 179, "next": 176, "prev": 177}
        try:
            if _IS_WIN and action in keymap_win:
                subprocess.run(
                    ["powershell", "-c",
                     f"(New-Object -ComObject WScript.Shell).SendKeys([char]{keymap_win[action]})"],
                    check=False, capture_output=True)
                return "Medya komutu gönderildi, Efendim."
            if _IS_LINUX:
                cmd = {"play_pause": "play-pause", "next": "next", "prev": "previous"}.get(action)
                if cmd:
                    subprocess.run(["playerctl", cmd], check=False, capture_output=True)
                    return "Medya komutu gönderildi, Efendim."
            return "Medya kontrolü bu platformda desteklenmiyor, Efendim."
        except Exception as e:
            return f"Medya komutu başarısız: {e}"
