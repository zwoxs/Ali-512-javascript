"""JARVIS2 — Stark HUD (Tkinter arayüzü).

Animasyonlu Arc Reaktör, sol sistem paneli (analog/dijital saat, CPU/RAM/DISK/PİL,
akıllı ev durumu, hızlı butonlar, hava durumu), çok sekmeli merkez panel
(TERMİNAL, WHATSAPP, LOG, GEÇMİŞ, NOTLAR, YAPILACAK, HATIRLATICI, İSTATİSTİK, TAKVİM),
tema motoru, sesli mod ve toast bildirimleri.

Orchestrator ile callback'ler üzerinden konuşur; ağır işler arka planda
çalışır, arayüz güncellemeleri ana iş parçacığına marshallanır.

Not: Bu dosya masaüstü (Windows/Linux/Mac, ekranlı) ortamda çalışır.
"""
import calendar
import math
import threading
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from config.loader import save_settings

try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False


# =====================================================================
#  TEMALAR
# =====================================================================
# Her tema tam palet taşır: accent (ana vurgu), accent2 (koyu vurgu),
# glow (parlama), bg/bg_soft/bg_card (arka plan katmanları), white (parlak
# metin), fg/fg_dim (gövde metni). PURPLE varsayılan temadır (mor-siyah).
_DARK = {"bg": "#05070a", "bg_soft": "#0b0f14", "bg_card": "#11161d",
         "white": "#e8f4ff", "fg": "#c8d6e5", "fg_dim": "#5a6b7b"}
THEMES = {
    "PURPLE": {"accent": "#c084fc", "accent2": "#6d28d9", "glow": "#e1bee7",
               "bg": "#0a0512", "bg_soft": "#0c0518", "bg_card": "#0a0416",
               "white": "#f1e6ff", "fg": "#cfc2e8", "fg_dim": "#6b5a8a"},
    "VIOLET": {"accent": "#d4b3ff", "accent2": "#9d6bff", "glow": "#efe0ff",
               "bg": "#120a20", "bg_soft": "#170d2a", "bg_card": "#140b24",
               "white": "#f8f0ff", "fg": "#dccdf2", "fg_dim": "#7d6b9e"},
    "CYAN":   {"accent": "#00e5ff", "accent2": "#0091ea", "glow": "#18ffff", **_DARK},
    "GREEN":  {"accent": "#00e676", "accent2": "#00c853", "glow": "#69f0ae", **_DARK},
    "RED":    {"accent": "#ff5252", "accent2": "#d50000", "glow": "#ff8a80", **_DARK},
    "GOLD":   {"accent": "#ffd54f", "accent2": "#ffab00", "glow": "#ffe57f", **_DARK},
    "MATRIX": {"accent": "#39ff14", "accent2": "#00ff41", "glow": "#76ff03", **_DARK},
    "ORANGE": {"accent": "#ff9100", "accent2": "#ff6d00", "glow": "#ffab40", **_DARK},
}
DEFAULT_THEME = "PURPLE"

# Global palet değişkenleri — _apply_theme() ile değişir. Sakin mod her
# karede bu globalleri okuduğu için tema değişikliği anında yansır.
ACCENT = ACCENT_LOW = ACCENT_DIM = GLOW = ""
BG = BG_SOFT = BG_CARD = BG2 = BG3 = ""
WHITE = FG = FG_DIM = ""


_PAL_KEYS = ("accent", "accent2", "glow", "bg", "bg_soft", "bg_card",
             "white", "fg", "fg_dim")
_THEME_FROM = {}
_THEME_TO = {}
_THEME_PROG = 1.0


def _set_theme_globals(p):
    global ACCENT, ACCENT_LOW, ACCENT_DIM, GLOW
    global BG, BG_SOFT, BG_CARD, BG2, BG3, WHITE, FG, FG_DIM
    ACCENT = p["accent"]
    ACCENT_LOW = p["accent2"]
    ACCENT_DIM = ACCENT_LOW
    GLOW = p["glow"]
    BG = p["bg"]
    BG_SOFT = BG2 = p["bg_soft"]
    BG_CARD = BG3 = p["bg_card"]
    WHITE = p["white"]
    FG = p["fg"]
    FG_DIM = p["fg_dim"]


def _apply_theme(name, animate=False):
    """Palet hedefini ayarlar; animate=True ise renkler kademeli akar
    (_theme_tick her karede hedefe doğru bir adım karıştırır)."""
    global _THEME_FROM, _THEME_TO, _THEME_PROG
    t = THEMES.get(name, THEMES[DEFAULT_THEME])
    _THEME_TO = {k: t[k] for k in _PAL_KEYS}
    if animate and ACCENT:
        _THEME_FROM = {"accent": ACCENT, "accent2": ACCENT_LOW, "glow": GLOW,
                       "bg": BG, "bg_soft": BG_SOFT, "bg_card": BG_CARD,
                       "white": WHITE, "fg": FG, "fg_dim": FG_DIM}
        _THEME_PROG = 0.0
    else:
        _THEME_FROM = dict(_THEME_TO)
        _THEME_PROG = 1.0
        _set_theme_globals(_THEME_TO)


def _theme_tick(step=0.05):
    """Tema geçişini bir adım ilerletir; renk değiştiyse True döner."""
    global _THEME_PROG
    if _THEME_PROG >= 1.0:
        return False
    _THEME_PROG = min(1.0, _THEME_PROG + step)
    k = _THEME_PROG
    ease = k * k * (3 - 2 * k)   # smoothstep
    _set_theme_globals({key: _mix(_THEME_FROM[key], _THEME_TO[key], ease)
                        for key in _PAL_KEYS})
    return True


_apply_theme(DEFAULT_THEME)


# ---- renk yardımcıları (sahte saydamlık: BG'ye doğru karıştır) ----
def _hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(c1, c2, t):
    """c1 → c2 arası doğrusal karışım (t: 0..1)."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_rgb(c1)
    r2, g2, b2 = _hex_rgb(c2)
    return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t),
                              int(g1 + (g2 - g1) * t),
                              int(b1 + (b2 - b1) * t))


def _fade(col, alpha):
    """Rengi arka plana doğru soldurarak saydamlık taklidi yapar."""
    return _mix(BG, col, alpha)

_GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
_AY = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
       "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class JarvisHUD:
    def __init__(self, orchestrator, voice_output=None, voice_input=None,
                 smart_home=None, weather=None, settings=None, bluetooth=None,
                 companion=None):
        self.orch = orchestrator
        self.voice_output = voice_output
        self.voice_input = voice_input
        self.smart_home = smart_home
        self.weather = weather
        self.bluetooth = bluetooth
        self.companion = companion
        self.settings = settings or {}

        name = str(self.settings.get("theme", DEFAULT_THEME)).upper()
        self.theme_name = name if name in THEMES else DEFAULT_THEME
        _apply_theme(self.theme_name)
        self.theme = THEMES[self.theme_name]
        self.accent = self.theme["accent"]

        # animasyon durumu
        self._reactor_angle = 0.0
        self._radar_angle = 0.0
        self._wave_phase = 0.0
        self._voice_state = "idle"   # idle / listening / processing / speaking
        self._particles = []

        # sakin mod durumu
        self._calm_visible = False
        self._calm_t = 0.0
        self._calm_scale = 0.0        # 0..1 arası yumuşatılmış aktiflik
        self._calm_prev_state = "idle"
        self._calm_stars = []         # arka plan yıldız alanı
        self._calm_sparks = []        # durum değişimi kıvılcımları
        self._calm_pulses = []        # dışa yayılan nabız halkaları
        self._calm_pulse_cd = 0
        self._calm_glitch = 0
        self._calm_shoot = None       # nadir kayan yıldız
        self._calm_hint_i = 0
        self._calm_hint_f = 0
        self._calm_mic_pos = (0, 0)
        self._calm_intro = 0.0        # açılış geçişi (0 → 1)
        self._calm_mouse = [0.0, 0.0]  # yumuşatılmış fare ofseti (-0.5..0.5)
        self._calm_mouse_t = (0.0, 0.0)
        self._calm_mouse_px = (-999, -999)  # hover için ham piksel konumu
        self._calm_notif = 0          # sakin moddayken gelen bildirim sayısı
        self._calm_sweep = 0.0        # radar açısı (hız durumla değişir)
        self._sys_vals = {}           # calm telemetri için son sistem değerleri
        self._calm_whisper = None     # son yanıt fısıltısı: (metin, zaman)
        self._calm_agenda = ""        # ajanda satırı (5 sn'de bir tazelenir)
        self._calm_agenda_ts = -99.0
        self._calm_weather = None     # hava köşesi için son veri
        self._calm_dt = 0.02          # uyarlanabilir kare süresi (sn)
        self._calm_last_mouse_move = 0.0
        self._last_activity = time.time()  # otomatik sakin mod için
        self._calm_dim = 1.0          # gece kısılması (1.0 gündüz, 0.6 gece)
        self._calm_night = None       # None=saate göre; test/manuel override
        self._calm_rem_dt = None      # sıradaki hatırlatıcının zamanı
        self._calm_hints = [
            "REAKTÖR ÇEVRİMİÇİ", "AĞ STABİL", "GÜVENLİK PROTOKOLLERİ AKTİF",
            "SENSÖR AĞI TARANIYOR", "ENERJİ AKIŞI NOMİNAL",
            "TÜM SİSTEMLER NOMİNAL", "BEKLEME MODU",
            "YAZARAK KOMUT VEREBİLİRSİNİZ",
        ]

        # komut geçmişi
        self._cmd_history = []
        self._hist_idx = 0

        # bilinen komutlar (autocomplete)
        self._known = [
            "saat kaç", "tarih", "günaydın", "hava durumu", "istatistik",
            "priz aç", "priz kapat", "priz durumu", "lamba aç", "lamba kapat",
            "whatsapp aç", "whatsapp kişileri listele", "yardım",
            "ekranı kilitle", "ekran görüntüsü al", "uyku moduna al",
            "ses seviyesi 50", "sonraki şarkı", "önceki şarkı", "müziği duraklat",
            "bluetooth tara", "ses cihazlarını listele", "eşleşmiş cihazlar",
            "buradan konuş", "sesi varsayılana al", "kulaklığa bağlan",
            "hoparlöre bağlan", "takma ad ekle kulaklık",
            "telefona bağlan", "arayüzü telefona geçir", "arayüzü bilgisayara al",
            "/help", "/clear", "/theme PURPLE", "/theme VIOLET", "/theme CYAN",
            "/theme GREEN", "/theme MATRIX", "/exit", "/stats", "sakin mod",
        ]

        self._build_window()
        self._wire_callbacks()
        self._boot_sequence()
        self._start_animations()
        self._start_clocks()

    # =================================================================
    #  PENCERE KURULUMU
    # =================================================================
    def _build_window(self):
        self.root = tk.Tk()
        name = self.settings.get("assistant_name", "JARVIS")
        self.root.title(f"{name} — Stark HUD")
        self.root.geometry("1200x760")
        self.root.minsize(1000, 640)
        self.root.configure(bg=BG)

        self._build_topbar()

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._build_left_panel(body)
        self._build_center(body)
        self._polish_entries()

        # sakin mod (tam ekran canvas, açılış görünümü)
        self._build_calm_mode()
        self.root.bind("<Escape>", lambda e: self._toggle_calm())

        # her tuş/tık etkileşimi otomatik sakin mod sayacını sıfırlar
        self.root.bind_all("<Key>", self._mark_activity, add="+")
        self.root.bind_all("<Button>", self._mark_activity, add="+")

        # toast katmanı
        self._toasts = []

        # uygulama açılışta sakin moda düşer
        self.root.after(80, self._show_calm)

    def _polish_entries(self):
        """Giriş kutularına odaklanınca vurgu rengiyle parlayan kenarlık."""
        for e in (self.entry, self.wa_contact, self.wa_msg, self.hist_search,
                  self.note_entry, self.todo_entry):
            try:
                e.config(highlightthickness=1,
                         highlightbackground=self.theme["bg_soft"],
                         highlightcolor=self.accent)
            except Exception:
                pass

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=BG2, height=44)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        name = self.settings.get("assistant_name", "JARVIS")
        self.title_lbl = tk.Label(bar, text=f"◆ {name}  v2", bg=BG2,
                                  fg=self.accent, font=("Consolas", 15, "bold"))
        self.title_lbl.pack(side="left", padx=14)

        # sağ taraf: saat + pil + butonlar
        right = tk.Frame(bar, bg=BG2)
        right.pack(side="right", padx=10)

        self.battery_lbl = tk.Label(right, text="", bg=BG2, fg=FG,
                                    font=("Consolas", 11))
        self.battery_lbl.pack(side="right", padx=8)

        self.top_clock = tk.Label(right, text="--:--:--", bg=BG2, fg=self.accent,
                                  font=("Consolas", 13, "bold"))
        self.top_clock.pack(side="right", padx=8)

        self.mute_btn = tk.Button(right, text="🔊", bg=BG3, fg=FG, bd=0,
                                  activebackground=BG, font=("Segoe UI", 11),
                                  cursor="hand2", command=self._toggle_mute)
        self.mute_btn.pack(side="right", padx=4)

        self.calm_btn = tk.Button(right, text="◎", bg=BG3, fg=FG, bd=0,
                                  activebackground=BG, font=("Segoe UI", 11),
                                  cursor="hand2", command=self._toggle_calm)
        self.calm_btn.pack(side="right", padx=4)

        self.voice_btn = tk.Button(right, text="🎤 OFF", bg=BG3, fg=FG_DIM, bd=0,
                                   activebackground=BG, font=("Consolas", 10, "bold"),
                                   cursor="hand2", command=self._toggle_voice)
        self.voice_btn.pack(side="right", padx=4)

        # tema seçici
        self.theme_var = tk.StringVar(value=self.theme_name)
        theme_menu = ttk.Combobox(right, textvariable=self.theme_var, width=8,
                                  state="readonly", values=list(THEMES.keys()))
        theme_menu.pack(side="right", padx=6)
        theme_menu.bind("<<ComboboxSelected>>",
                        lambda e: self.set_theme(self.theme_var.get()))

    # ---------------- SOL PANEL ----------------
    def _card(self, parent, title):
        """Sol panel kartı: ince temalı kenarlık + vurgu çubuklu başlık.
        Gövde çerçevesini döndürür; kart set_theme ile yeniden boyanır."""
        outer = tk.Frame(parent, bg=BG_CARD, highlightthickness=1,
                         highlightbackground=_mix(BG_CARD, ACCENT, 0.25))
        outer.pack(fill="x", padx=10, pady=(0, 8))
        head = tk.Frame(outer, bg=BG_CARD)
        head.pack(fill="x")
        bar = tk.Frame(head, bg=ACCENT, width=3, height=14)
        bar.pack(side="left", padx=(8, 6), pady=6)
        bar.pack_propagate(False)
        lbl = tk.Label(head, text=title, bg=BG_CARD, fg=FG_DIM,
                       font=("Consolas", 9, "bold"), anchor="w")
        lbl.pack(side="left")
        body = tk.Frame(outer, bg=BG_CARD)
        body.pack(fill="both", expand=True)
        self._cards.append((outer, bar))
        return body

    def _build_left_panel(self, parent):
        self._cards = []
        left = tk.Frame(parent, bg=BG2, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        tk.Frame(left, bg=BG2, height=8).pack()   # üst boşluk

        # SAAT kartı: analog + dijital
        cb = self._card(left, "SAAT")
        self.clock_canvas = tk.Canvas(cb, width=260, height=150, bg=BG_CARD,
                                      highlightthickness=0)
        self.clock_canvas.pack(pady=(2, 0))
        self.digital_clock = tk.Label(cb, text="--:--:--", bg=BG_CARD,
                                      fg=self.accent, font=("Consolas", 20, "bold"))
        self.digital_clock.pack()
        self.date_lbl = tk.Label(cb, text="", bg=BG_CARD, fg=FG_DIM,
                                 font=("Consolas", 10))
        self.date_lbl.pack(pady=(0, 6))

        # HAVA kartı
        wb = self._card(left, "HAVA DURUMU")
        self.weather_lbl = tk.Label(wb, text="—", bg=BG_CARD, fg=FG,
                                    font=("Consolas", 11), wraplength=250,
                                    justify="center")
        self.weather_lbl.pack(pady=(0, 6), fill="x")

        # SİSTEM DURUMU kartı
        self._build_sys_bars(self._card(left, "SİSTEM DURUMU"))

        # AKILLI EV kartı
        hb = self._card(left, "AKILLI EV")
        self.home_lbl = tk.Label(hb, text="🏠 Akıllı Ev: —", bg=BG_CARD, fg=FG,
                                 font=("Consolas", 10))
        self.home_lbl.pack(pady=(0, 6))

        # HIZLI ERİŞİM kartı
        self._build_quick_buttons(self._card(left, "HIZLI ERİŞİM"))

    def _build_sys_bars(self, parent):
        frame = tk.Frame(parent, bg=BG_CARD)
        frame.pack(fill="x", padx=10, pady=(0, 6))
        self.bars = {}
        for key in ("CPU", "RAM", "DİSK", "PİL"):
            row = tk.Frame(frame, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=key, bg=BG_CARD, fg=FG_DIM, width=5,
                     anchor="w", font=("Consolas", 9)).pack(side="left")
            cv = tk.Canvas(row, width=160, height=12, bg=BG,
                           highlightthickness=0)
            cv.pack(side="left", padx=4)
            val = tk.Label(row, text="0%", bg=BG_CARD, fg=FG, width=4,
                           font=("Consolas", 9))
            val.pack(side="left")
            self.bars[key] = (cv, val)

    def _build_quick_buttons(self, parent):
        grid = tk.Frame(parent, bg=BG_CARD)
        grid.pack(fill="x", padx=8, pady=(0, 6))
        quick = [
            ("Priz Aç", "priz aç"), ("Priz Kapat", "priz kapat"),
            ("WhatsApp", "whatsapp aç"), ("Hava", "hava durumu"),
            ("Plan", "günaydın"), ("İstatistik", "istatistik"),
            ("Kilitle", "ekranı kilitle"), ("Ekran G.", "ekran görüntüsü al"),
        ]
        btn_bg = _mix(BG_CARD, WHITE, 0.06)
        for i, (label, cmd) in enumerate(quick):
            b = tk.Button(grid, text=label, bg=btn_bg, fg=FG, bd=0,
                          activebackground=self.accent, activeforeground=BG,
                          font=("Consolas", 9), cursor="hand2", width=12,
                          command=lambda c=cmd: self._run_command(c))
            b.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

    # ---------------- MERKEZ ----------------
    def _build_center(self, parent):
        center = tk.Frame(parent, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        # Arc reaktör + ses dalgası üst şerit
        top = tk.Frame(center, bg=BG)
        top.pack(fill="x")
        self.reactor = tk.Canvas(top, width=170, height=170, bg=BG,
                                 highlightthickness=0)
        self.reactor.pack(side="left", padx=8, pady=4)
        self.reactor.bind("<Button-1>", self._reactor_click)

        wave_frame = tk.Frame(top, bg=BG)
        wave_frame.pack(side="left", fill="both", expand=True)
        self.status_lbl = tk.Label(wave_frame, text="SİSTEM HAZIR", bg=BG,
                                   fg=self.accent, font=("Consolas", 12, "bold"),
                                   anchor="w")
        self.status_lbl.pack(fill="x", padx=6, pady=(18, 0))
        self.wave = tk.Canvas(wave_frame, height=90, bg=BG, highlightthickness=0)
        self.wave.pack(fill="x", padx=6, pady=4)

        # sekmeler
        self._build_tabs(center)

    def _style_ttk(self):
        """ttk stillerini hedef paletle (yeniden) uygular.
        Tema geçişi animasyonlu aktığı için globaller yerine
        self.theme'deki hedef renkler kullanılır."""
        th = self.theme
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=th["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=th["bg_soft"],
                        foreground=th["fg_dim"],
                        padding=(12, 6), font=("Consolas", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", th["bg_card"])],
                  foreground=[("selected", th["accent"])])
        # koyu temalı scrollbar
        style.configure("Jarvis.Vertical.TScrollbar",
                        background=_mix(th["bg_card"], th["accent"], 0.18),
                        troughcolor=th["bg"], bordercolor=th["bg"],
                        arrowcolor=th["fg_dim"], relief="flat")
        style.map("Jarvis.Vertical.TScrollbar",
                  background=[("active", _mix(th["bg_card"], th["accent"], 0.4))])

    def _scrolled(self, text_widget):
        """Metin paneline temalı dikey scrollbar bağlar (pack'ten önce çağır)."""
        sb = ttk.Scrollbar(text_widget.master, orient="vertical",
                           command=text_widget.yview,
                           style="Jarvis.Vertical.TScrollbar")
        text_widget.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=4)

    def _build_tabs(self, parent):
        self._style_ttk()
        self.nb = ttk.Notebook(parent)
        self.nb.pack(fill="both", expand=True, pady=(4, 0))

        self._build_terminal_tab()
        self._build_whatsapp_tab()
        self._build_log_tab()
        self._build_history_tab()
        self._build_notes_tab()
        self._build_todo_tab()
        self._build_reminder_tab()
        self._build_bluetooth_tab()
        self._build_mobile_tab()
        self._build_stats_tab()
        self._build_calendar_tab()
        self._build_settings_tab()

    # ---- TERMİNAL ----
    def _build_terminal_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="TERMİNAL")

        self.chat = tk.Text(tab, bg=BG, fg=FG, bd=0, wrap="word",
                            font=("Consolas", 11), state="disabled",
                            insertbackground=self.accent, padx=10, pady=8)
        self._scrolled(self.chat)
        self.chat.pack(fill="both", expand=True, padx=4, pady=4)
        self.chat.tag_config("user", foreground="#7fdbff")
        self.chat.tag_config("jarvis", foreground=self.accent)
        self.chat.tag_config("sys", foreground=FG_DIM, font=("Consolas", 9))

        # sağ tık menüsü
        self.chat_menu = tk.Menu(self.chat, tearoff=0, bg=BG2, fg=FG,
                                 activebackground=self.accent, activeforeground=BG)
        self.chat_menu.add_command(label="Kopyala", command=self._copy_selection)
        self.chat_menu.add_command(label="Tümünü Seç", command=self._select_all_chat)
        self.chat_menu.add_separator()
        self.chat_menu.add_command(label="Temizle",
                                   command=lambda: self._handle_response("", "__CLEAR__"))
        self.chat.bind("<Button-3>", self._show_chat_menu)

        entry_row = tk.Frame(tab, bg=BG2)
        entry_row.pack(fill="x", padx=4, pady=(0, 4))
        tk.Label(entry_row, text="›", bg=BG2, fg=self.accent,
                 font=("Consolas", 14, "bold")).pack(side="left", padx=(8, 2))
        self.entry = tk.Entry(entry_row, bg=BG2, fg=FG, bd=0,
                              insertbackground=self.accent, font=("Consolas", 12))
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=4)
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Up>", self._hist_up)
        self.entry.bind("<Down>", self._hist_down)
        self.entry.bind("<Tab>", self._autocomplete)
        self.entry.focus_set()

        tk.Button(entry_row, text="GÖNDER", bg=BG3, fg=self.accent, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 10, "bold"), cursor="hand2",
                  command=lambda: self._on_enter(None)).pack(side="right", padx=6)

    # ---- WHATSAPP ----
    def _build_whatsapp_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="WHATSAPP")

        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", padx=8, pady=8)
        tk.Label(top, text="Kişi:", bg=BG, fg=FG, font=("Consolas", 10)).pack(side="left")
        self.wa_contact = tk.Entry(top, bg=BG2, fg=FG, bd=0, width=18,
                                   insertbackground=self.accent, font=("Consolas", 11))
        self.wa_contact.pack(side="left", padx=6, ipady=4)
        tk.Label(top, text="Mesaj:", bg=BG, fg=FG, font=("Consolas", 10)).pack(side="left")
        self.wa_msg = tk.Entry(top, bg=BG2, fg=FG, bd=0,
                               insertbackground=self.accent, font=("Consolas", 11))
        self.wa_msg.pack(side="left", padx=6, ipady=4, fill="x", expand=True)
        tk.Button(top, text="AÇ & HAZIRLA", bg=BG3, fg=self.accent, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 10, "bold"), cursor="hand2",
                  command=self._wa_send).pack(side="left", padx=6)

        tk.Button(tab, text="WhatsApp Web'i Aç", bg=BG3, fg=FG, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 10), cursor="hand2",
                  command=lambda: self._run_command("whatsapp aç")).pack(pady=4)

        self.wa_contacts = tk.Listbox(tab, bg=BG2, fg=FG, bd=0,
                                      font=("Consolas", 10), selectbackground=self.accent,
                                      selectforeground=BG, highlightthickness=0)
        self.wa_contacts.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_contacts()

    # ---- LOG ----
    def _build_log_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="LOG")
        self.log_text = tk.Text(tab, bg=BG, fg=FG_DIM, bd=0, wrap="word",
                                font=("Consolas", 9), state="disabled", padx=8, pady=6)
        self._scrolled(self.log_text)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ---- GEÇMİŞ ----
    def _build_history_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="GEÇMİŞ")
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="🔍", bg=BG, fg=self.accent).pack(side="left")
        self.hist_search = tk.Entry(top, bg=BG2, fg=FG, bd=0,
                                    insertbackground=self.accent, font=("Consolas", 10))
        self.hist_search.pack(side="left", fill="x", expand=True, ipady=4, padx=6)
        self.hist_search.bind("<KeyRelease>", lambda e: self._refresh_history())
        tk.Button(top, text="Yenile", bg=BG3, fg=FG, bd=0, cursor="hand2",
                  command=self._refresh_history).pack(side="right")

        self.hist_text = tk.Text(tab, bg=BG, fg=FG, bd=0, wrap="word",
                                 font=("Consolas", 10), state="disabled", padx=8, pady=6)
        self._scrolled(self.hist_text)
        self.hist_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._refresh_history()

    # ---- NOTLAR ----
    def _build_notes_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="NOTLAR")
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", padx=8, pady=6)
        self.note_entry = tk.Entry(top, bg=BG2, fg=FG, bd=0,
                                   insertbackground=self.accent, font=("Consolas", 11))
        self.note_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=4)
        self.note_entry.bind("<Return>", lambda e: self._add_note())
        tk.Button(top, text="+ EKLE", bg=BG3, fg=self.accent, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 10, "bold"), cursor="hand2",
                  command=self._add_note).pack(side="left", padx=4)
        self.notes_list = tk.Listbox(tab, bg=BG2, fg=FG, bd=0,
                                     font=("Consolas", 10), selectbackground=self.accent,
                                     selectforeground=BG, highlightthickness=0)
        self.notes_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.notes_list.bind("<Double-Button-1>", lambda e: self._delete_note())
        self._refresh_notes()

    # ---- YAPILACAK ----
    def _build_todo_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="YAPILACAK")
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", padx=8, pady=6)
        self.todo_entry = tk.Entry(top, bg=BG2, fg=FG, bd=0,
                                   insertbackground=self.accent, font=("Consolas", 11))
        self.todo_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=4)
        self.todo_entry.bind("<Return>", lambda e: self._add_todo())
        self.todo_priority = ttk.Combobox(top, width=8, state="readonly",
                                          values=["yüksek", "orta", "normal"])
        self.todo_priority.set("normal")
        self.todo_priority.pack(side="left", padx=4)
        tk.Button(top, text="+ EKLE", bg=BG3, fg=self.accent, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 10, "bold"), cursor="hand2",
                  command=self._add_todo).pack(side="left", padx=4)
        self.todo_list = tk.Listbox(tab, bg=BG2, fg=FG, bd=0,
                                    font=("Consolas", 11), selectbackground=self.accent,
                                    selectforeground=BG, highlightthickness=0)
        self.todo_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.todo_list.bind("<Double-Button-1>", lambda e: self._toggle_todo())
        tk.Label(tab, text="Çift tık: tamamlandı işaretle  •  Del: sil",
                 bg=BG, fg=FG_DIM, font=("Consolas", 8)).pack()
        self.todo_list.bind("<Delete>", lambda e: self._delete_todo())
        self._refresh_todos()

    # ---- HATIRLATICI ----
    def _build_reminder_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="HATIRLATICI")
        top = tk.Frame(tab, bg=BG)
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="Örn: 10 dakika sonra su iç hatırlat", bg=BG,
                 fg=FG_DIM, font=("Consolas", 9)).pack(side="left")
        # hazır öneriler
        sug = tk.Frame(tab, bg=BG)
        sug.pack(fill="x", padx=8)
        for label, cmd in [("5 dk mola", "5 dakika sonra mola ver hatırlat"),
                           ("30 dk su", "30 dakika sonra su iç hatırlat"),
                           ("1 saat toplantı", "60 dakika sonra toplantı hatırlat")]:
            tk.Button(sug, text=label, bg=BG3, fg=FG, bd=0, cursor="hand2",
                      font=("Consolas", 9),
                      command=lambda c=cmd: self._run_command(c)).pack(side="left", padx=4, pady=4)
        self.rem_list = tk.Listbox(tab, bg=BG2, fg=FG, bd=0,
                                   font=("Consolas", 10), selectbackground=self.accent,
                                   selectforeground=BG, highlightthickness=0)
        self.rem_list.pack(fill="both", expand=True, padx=8, pady=8)
        self._refresh_reminders()

    # ---- İSTATİSTİK ----
    def _build_stats_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="İSTATİSTİK")
        self.stats_text = tk.Text(tab, bg=BG, fg=self.accent, bd=0, wrap="word",
                                  font=("Consolas", 12), state="disabled", padx=12, pady=12)
        self.stats_text.pack(fill="both", expand=True, padx=4, pady=4)
        self._refresh_stats()

    # ---- TAKVİM ----
    def _build_calendar_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="TAKVİM")
        self._cal_year = datetime.now().year
        self._cal_month = datetime.now().month
        nav = tk.Frame(tab, bg=BG)
        nav.pack(fill="x", pady=8)
        tk.Button(nav, text="◄", bg=BG3, fg=self.accent, bd=0, cursor="hand2",
                  font=("Consolas", 12, "bold"),
                  command=lambda: self._cal_shift(-1)).pack(side="left", padx=20)
        self.cal_title = tk.Label(nav, text="", bg=BG, fg=self.accent,
                                  font=("Consolas", 14, "bold"))
        self.cal_title.pack(side="left", expand=True)
        tk.Button(nav, text="►", bg=BG3, fg=self.accent, bd=0, cursor="hand2",
                  font=("Consolas", 12, "bold"),
                  command=lambda: self._cal_shift(1)).pack(side="right", padx=20)
        self.cal_grid = tk.Frame(tab, bg=BG)
        self.cal_grid.pack(fill="both", expand=True, padx=12, pady=8)
        self._draw_calendar()

    # ---- BLUETOOTH ----
    def _build_bluetooth_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="BLUETOOTH")

        info = tk.Label(
            tab, bg=BG, fg=FG_DIM, justify="left", font=("Consolas", 9),
            text=("Ses cihazını seçip 'BURADAN KONUŞ' deyin; JARVIS'in sesi oraya gider.\n"
                  "SESLİ KOMUT için: cihaza 'TAKMA AD' verin (örn. kulaklık), sonra\n"
                  "\"jarvis kulaklığa bağlan\" deyin — otomatik bağlanıp oradan konuşur.\n"
                  "(Cihaz önce işletim sisteminde eşleştirilmiş olmalı.)"))
        info.pack(anchor="w", padx=10, pady=(8, 4))

        btnrow = tk.Frame(tab, bg=BG)
        btnrow.pack(fill="x", padx=8, pady=4)
        for label, fn in [("🔍 Tara (BLE)", self._bt_scan),
                          ("🎧 Ses Cihazları", self._bt_audio_list),
                          ("🔗 Eşleşmiş", self._bt_paired),
                          ("🔈 Buradan Konuş", self._bt_speak_here),
                          ("🏷 Takma Ad", self._bt_set_alias),
                          ("↩ Varsayılan", self._bt_reset)]:
            tk.Button(btnrow, text=label, bg=BG3, fg=self.accent, bd=0,
                      activebackground=self.accent, activeforeground=BG,
                      font=("Consolas", 9, "bold"), cursor="hand2",
                      command=fn).pack(side="left", padx=3)

        self.bt_status = tk.Label(tab, text="Ses hedefi: varsayılan cihaz",
                                  bg=BG, fg=self.accent, font=("Consolas", 10, "bold"))
        self.bt_status.pack(anchor="w", padx=10, pady=4)

        self.bt_list = tk.Listbox(tab, bg=BG2, fg=FG, bd=0, font=("Consolas", 10),
                                  selectbackground=self.accent, selectforeground=BG,
                                  highlightthickness=0)
        self.bt_list.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(tab, text="Listeden bir ses cihazı seçip 'Buradan Konuş'a basın.",
                 bg=BG, fg=FG_DIM, font=("Consolas", 8)).pack()
        self._bt_current_kind = None  # 'audio' / 'ble' / 'paired'

    def _bt_run(self, fn, kind, label):
        """Bluetooth işlemini arka planda çalıştırıp listeyi doldurur."""
        self.bt_list.delete(0, "end")
        self.bt_list.insert("end", f"  {label}…")

        def worker():
            try:
                items = fn()
            except Exception as e:
                items = [{"name": f"Hata: {e}"}]
            self.root.after(0, lambda: self._bt_fill(items, kind))
        threading.Thread(target=worker, daemon=True).start()

    def _bt_fill(self, items, kind):
        self.bt_list.delete(0, "end")
        self._bt_current_kind = kind
        self._bt_items = items
        if not items:
            self.bt_list.insert("end", "  (cihaz bulunamadı)")
            return
        for it in items:
            if kind == "audio":
                mark = " ★" if it.get("default") else ""
                self.bt_list.insert("end", f"  [{it['index']}] {it['name']}{mark}")
            else:
                addr = f"  ({it['address']})" if it.get("address") else ""
                self.bt_list.insert("end", f"  {it['name']}{addr}")

    def _bt_scan(self):
        if not self.bluetooth:
            return
        self._bt_run(self.bluetooth.scan, "ble", "Taranıyor")

    def _bt_audio_list(self):
        if not self.bluetooth:
            return
        self._bt_run(self.bluetooth.list_audio_outputs, "audio", "Ses cihazları alınıyor")

    def _bt_paired(self):
        if not self.bluetooth:
            return
        self._bt_run(self.bluetooth.list_paired, "paired", "Eşleşmiş cihazlar")

    def _bt_speak_here(self):
        if not self.bluetooth:
            return
        sel = self.bt_list.curselection()
        if not sel or self._bt_current_kind != "audio":
            self._toast("Önce 'Ses Cihazları'ndan birini seçin")
            return
        item = self._bt_items[sel[0]]
        resp = self.bluetooth.set_speak_device(item["index"])
        self.bt_status.config(text=f"Ses hedefi: {item['name']}")
        self._toast(resp)
        self.bluetooth.speak_here_test()

    def _bt_reset(self):
        if not self.bluetooth:
            return
        resp = self.bluetooth.reset_to_default()
        self.bt_status.config(text="Ses hedefi: varsayılan cihaz")
        self._toast(resp)

    def _bt_set_alias(self):
        """Seçili ses cihazına sesli komut için takma ad ata."""
        if not self.bluetooth:
            return
        sel = self.bt_list.curselection()
        if not sel or self._bt_current_kind != "audio":
            self._toast("Önce 'Ses Cihazları'ndan birini seçin")
            return
        from tkinter import simpledialog
        item = self._bt_items[sel[0]]
        alias = simpledialog.askstring(
            "Takma Ad", f"'{item['name']}' cihazı için sesli komut adı:\n"
            "(örn. kulaklık, hoparlör)", parent=self.root)
        if alias:
            resp = self.bluetooth.set_alias(alias, item["name"])
            self._toast(resp)

    # ---- MOBİL (companion) ----
    def _build_mobile_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="MOBİL")

        tk.Label(tab, text="📱 Companion Web Arayüzü", bg=BG, fg=self.accent,
                 font=("Consolas", 14, "bold")).pack(pady=(14, 4))
        tk.Label(tab, bg=BG, fg=FG_DIM, justify="left", font=("Consolas", 9),
                 text=("Telefon/saatinizin tarayıcısından aşağıdaki adresi açın.\n"
                       "Bir cihaza bağlanınca arayüz otomatik o cihazın moduna geçer;\n"
                       "aşağıdaki butonlarla manuel de değiştirebilirsiniz.")).pack(padx=16)

        self.mobile_url = tk.Label(tab, text="(sunucu başlatılmadı)", bg=BG3,
                                   fg=self.accent, font=("Consolas", 13, "bold"),
                                   padx=14, pady=10)
        self.mobile_url.pack(pady=12)

        self.mobile_mode = tk.Label(tab, text="Aktif mod: —", bg=BG, fg=FG,
                                    font=("Consolas", 11))
        self.mobile_mode.pack(pady=4)

        row = tk.Frame(tab, bg=BG)
        row.pack(pady=10)
        for label, target in [("🖥 Masaüstü", "desktop"), ("📱 Telefon", "phone")]:
            tk.Button(row, text=label, bg=BG3, fg=self.accent, bd=0,
                      activebackground=self.accent, activeforeground=BG,
                      font=("Consolas", 10, "bold"), cursor="hand2", width=12,
                      command=lambda t=target: self._mobile_set_mode(t)).pack(
                side="left", padx=6)

        tk.Label(tab, bg=BG, fg=FG_DIM, font=("Consolas", 8),
                 text="URL'i telefonda açmak için aynı Wi-Fi ağında olmalısınız "
                      "(veya Tailscale VPN).").pack(pady=(16, 0))
        self._refresh_mobile()

    def _refresh_mobile(self):
        if not self.companion:
            return
        if getattr(self.companion, "running", False):
            self.mobile_url.config(text=self.companion.local_url())
        labels = {"desktop": "masaüstü", "phone": "telefon"}
        dev = f"  ·  {self.companion.active_device}" if self.companion.active_device else ""
        self.mobile_mode.config(
            text=f"Aktif mod: {labels.get(self.companion.active_mode, '—')}{dev}")

    def _mobile_set_mode(self, target):
        if not self.companion:
            self._toast("Companion sunucusu yok")
            return
        self.companion.set_mode(target)
        self._refresh_mobile()
        self._toast(f"Arayüz modu: {target}")

    # ---- AYARLAR ----
    def _build_settings_tab(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="AYARLAR")
        self._setting_vars = {}

        fields = [
            ("assistant_name", "Asistan adı"),
            ("wake_word", "Uyanma kelimesi"),
            ("owner_name", "Hitap"),
            ("tts_voice", "TTS ses (edge-tts)"),
            ("tts_rate", "Konuşma hızı (wpm)"),
            ("search_results_count", "Arama sonuç sayısı"),
            ("calm_idle_minutes", "Sakin moda geçiş (dk, 0=kapalı)"),
        ]
        for i, (key, label) in enumerate(fields):
            row = tk.Frame(tab, bg=BG)
            row.pack(fill="x", padx=20, pady=6)
            tk.Label(row, text=label, bg=BG, fg=FG, width=22, anchor="w",
                     font=("Consolas", 10)).pack(side="left")
            var = tk.StringVar(value=str(self.settings.get(key, "")))
            self._setting_vars[key] = var
            tk.Entry(row, textvariable=var, bg=BG2, fg=self.accent, bd=0,
                     insertbackground=self.accent, font=("Consolas", 11)).pack(
                side="left", fill="x", expand=True, ipady=4, padx=6)

        # WhatsApp otomatik gönderim
        row = tk.Frame(tab, bg=BG)
        row.pack(fill="x", padx=20, pady=6)
        self._wa_auto_var = tk.BooleanVar(value=bool(self.settings.get("whatsapp_auto_send")))
        tk.Checkbutton(row, text="WhatsApp otomatik gönderim (pywhatkit)",
                       variable=self._wa_auto_var, bg=BG, fg=FG,
                       selectcolor=BG2, activebackground=BG, activeforeground=self.accent,
                       font=("Consolas", 10)).pack(side="left")

        tk.Button(tab, text="💾 KAYDET", bg=BG3, fg=self.accent, bd=0,
                  activebackground=self.accent, activeforeground=BG,
                  font=("Consolas", 11, "bold"), cursor="hand2",
                  command=self._save_settings).pack(pady=16)
        tk.Label(tab, text="Değişiklikler kaydedilince anında uygulanır.",
                 bg=BG, fg=FG_DIM, font=("Consolas", 9)).pack()

    def _save_settings(self):
        for key, var in self._setting_vars.items():
            val = var.get().strip()
            # sayısal alanları dönüştür
            if key in ("tts_rate", "search_results_count", "calm_idle_minutes"):
                try:
                    val = int(val)
                except ValueError:
                    continue
            self.settings[key] = val
        self.settings["whatsapp_auto_send"] = self._wa_auto_var.get()
        try:
            save_settings(self.settings)
        except Exception as e:
            self._toast(f"Kaydedilemedi: {e}")
            return
        # canlı uygula
        self.orch.reload_settings(self.settings)
        if self.voice_output:
            self.voice_output.reload_settings(self.settings)
        self._toast("Ayarlar kaydedildi")

    # ---- sağ tık menüsü yardımcıları ----
    def _show_chat_menu(self, event):
        try:
            self.chat_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.chat_menu.grab_release()

    def _copy_selection(self):
        try:
            sel = self.chat.get("sel.first", "sel.last")
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
        except tk.TclError:
            pass

    def _select_all_chat(self):
        self.chat.tag_add("sel", "1.0", "end")

    # =================================================================
    #  CALLBACK BAĞLAMA
    # =================================================================
    def _wire_callbacks(self):
        self.orch.set_notify_callback(self._on_notify)

    def _on_notify(self, msg):
        self.root.after(0, lambda: (self._toast(msg), self._refresh_reminders()))

    # =================================================================
    #  KOMUT AKIŞI
    # =================================================================
    def _on_enter(self, event):
        text = self.entry.get().strip()
        if not text:
            return "break"
        self.entry.delete(0, "end")
        self._cmd_history.append(text)
        self._hist_idx = len(self._cmd_history)
        self._run_command(text)
        return "break"

    def _run_command(self, text, from_voice=False):
        self._append_chat("Siz", text, "user")
        self._log(f"» {text}")

        def worker():
            resp = self.orch.handle(text, from_voice=from_voice)
            self.root.after(0, lambda: self._handle_response(text, resp))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_response(self, text, resp):
        if resp == "__EXIT__":
            self._shutdown()
            return
        if resp == "__CLEAR__":
            self.chat.config(state="normal")
            self.chat.delete("1.0", "end")
            self.chat.config(state="disabled")
            return
        if resp.startswith("__THEME__:"):
            self.set_theme(resp.split(":", 1)[1].strip())
            self._append_chat("JARVIS", f"Tema {self.theme_name} olarak ayarlandı.", "jarvis")
            return

        self._append_chat("JARVIS", resp, "jarvis")
        self._log(f"« {resp}")
        # sakin mod fısıltısı: yanıtın ilk satırı, kısaltılmış
        line = resp.strip().splitlines()[0] if resp.strip() else ""
        if line:
            if len(line) > 72:
                line = line[:72] + "…"
            self._calm_whisper = (line, time.time())
        self._last_activity = time.time()
        if self.voice_output:
            self.voice_output.speak(resp, blocking=False)

        # ilgili sekmeleri tazele
        self._refresh_reminders()
        self._refresh_history()
        self._refresh_contacts()
        self._refresh_stats()
        self._refresh_mobile()

    def _append_chat(self, who, text, tag):
        self.chat.config(state="normal")
        ts = datetime.now().strftime("%H:%M")
        self.chat.insert("end", f"[{ts}] {who}: ", "sys")
        self.chat.insert("end", f"{text}\n\n", tag)
        self.chat.see("end")
        self.chat.config(state="disabled")

    def _log(self, line):
        self.log_text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {line}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ---- komut geçmişi & autocomplete ----
    def _hist_up(self, event):
        if self._cmd_history and self._hist_idx > 0:
            self._hist_idx -= 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self._cmd_history[self._hist_idx])
        return "break"

    def _hist_down(self, event):
        if self._hist_idx < len(self._cmd_history) - 1:
            self._hist_idx += 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self._cmd_history[self._hist_idx])
        else:
            self._hist_idx = len(self._cmd_history)
            self.entry.delete(0, "end")
        return "break"

    def _autocomplete(self, event):
        cur = self.entry.get().strip().lower()
        if not cur:
            return "break"
        for cmd in self._known:
            if cmd.lower().startswith(cur):
                self.entry.delete(0, "end")
                self.entry.insert(0, cmd)
                break
        return "break"

    # =================================================================
    #  SEKME TAZELEYİCİLER
    # =================================================================
    def _refresh_contacts(self):
        try:
            self.wa_contacts.delete(0, "end")
            for name, phone in self.orch.memory.list_contacts().items():
                self.wa_contacts.insert("end", f"  {name}  —  {phone}")
        except Exception:
            pass

    def _refresh_history(self):
        q = ""
        try:
            q = self.hist_search.get().strip().lower()
        except Exception:
            pass
        self.hist_text.config(state="normal")
        self.hist_text.delete("1.0", "end")
        for h in self.orch.memory.get_history(100):
            line = f"[{h.get('ts','')}] {h.get('user','')} → {h.get('jarvis','')}"
            if not q or q in line.lower():
                self.hist_text.insert("end", line + "\n\n")
        self.hist_text.config(state="disabled")

    def _refresh_notes(self):
        self.notes_list.delete(0, "end")
        for n in self.orch.memory.list_notes():
            self.notes_list.insert("end", f"  • {n['text']}   ({n.get('ts','')[:16]})")

    def _add_note(self):
        text = self.note_entry.get().strip()
        if text:
            self.orch.memory.add_note(text)
            self.note_entry.delete(0, "end")
            self._refresh_notes()
            self._toast("Not eklendi")

    def _delete_note(self):
        sel = self.notes_list.curselection()
        if sel and self.orch.memory.delete_note(sel[0]):
            self._refresh_notes()

    def _refresh_todos(self):
        self.todo_list.delete(0, "end")
        for t in self.orch.memory.list_todos():
            mark = "✓" if t.get("done") else "○"
            pri = {"yüksek": "🔴", "orta": "🟡", "normal": "⚪"}.get(t.get("priority"), "⚪")
            self.todo_list.insert("end", f"  {mark} {pri} {t['text']}")

    def _add_todo(self):
        text = self.todo_entry.get().strip()
        if text:
            self.orch.memory.add_todo(text, self.todo_priority.get())
            self.todo_entry.delete(0, "end")
            self._refresh_todos()
            self._toast("Görev eklendi")

    def _toggle_todo(self):
        sel = self.todo_list.curselection()
        if sel and self.orch.memory.toggle_todo(sel[0]):
            self._refresh_todos()

    def _delete_todo(self):
        sel = self.todo_list.curselection()
        if sel and self.orch.memory.delete_todo(sel[0]):
            self._refresh_todos()

    def _refresh_reminders(self):
        try:
            self.rem_list.delete(0, "end")
            for r in self.orch.memory.list_reminders():
                self.rem_list.insert("end", f"  ⏰ {r['text']}   →  {r.get('at','')}")
        except Exception:
            pass

    def _refresh_stats(self):
        try:
            s = self.orch.stats
            up = int(time.time() - s["started"])
            mins, secs = divmod(up, 60)
            txt = (f"◆ OTURUM İSTATİSTİKLERİ\n\n"
                   f"  Komut       : {s['commands']}\n"
                   f"  Arama       : {s['searches']}\n"
                   f"  Mesaj       : {s['messages']}\n"
                   f"  Sesli komut : {s['voice_cmds']}\n"
                   f"  Süre        : {mins} dk {secs} sn\n")
            self.stats_text.config(state="normal")
            self.stats_text.delete("1.0", "end")
            self.stats_text.insert("end", txt)
            self.stats_text.config(state="disabled")
        except Exception:
            pass

    def _wa_send(self):
        contact = self.wa_contact.get().strip()
        msg = self.wa_msg.get().strip()
        if contact and msg:
            self._run_command(f"{contact}e {msg} yaz")
            self.wa_msg.delete(0, "end")

    # =================================================================
    #  TAKVİM
    # =================================================================
    def _cal_shift(self, delta):
        self._cal_month += delta
        if self._cal_month < 1:
            self._cal_month = 12
            self._cal_year -= 1
        elif self._cal_month > 12:
            self._cal_month = 1
            self._cal_year += 1
        self._draw_calendar()

    def _draw_calendar(self):
        for w in self.cal_grid.winfo_children():
            w.destroy()
        self.cal_title.config(text=f"{_AY[self._cal_month - 1]} {self._cal_year}")
        gunler = ["Pt", "Sa", "Ça", "Pe", "Cu", "Ct", "Pa"]
        for i, g in enumerate(gunler):
            fg = "#ff5252" if i >= 5 else FG_DIM
            tk.Label(self.cal_grid, text=g, bg=BG, fg=fg,
                     font=("Consolas", 10, "bold"), width=4).grid(row=0, column=i, pady=4)
        today = datetime.now()
        cal = calendar.Calendar(firstweekday=0)
        row = 1
        for week in cal.monthdayscalendar(self._cal_year, self._cal_month):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                is_today = (day == today.day and self._cal_month == today.month
                            and self._cal_year == today.year)
                bg = self.accent if is_today else BG2
                fg = BG if is_today else ("#ff5252" if col >= 5 else FG)
                tk.Label(self.cal_grid, text=str(day), bg=bg, fg=fg,
                         font=("Consolas", 10, "bold" if is_today else "normal"),
                         width=4, height=2).grid(row=row, column=col, padx=1, pady=1)
            row += 1

    # =================================================================
    #  SAKİN MOD — tam ekran arc-reactor rozeti
    # =================================================================
    # Tasarım ilkeleri: ince çizgi + düşük opaklık (BG'ye soldurma),
    # sabit piksel boyutlar (DPI ölçeklemesine orantılama YOK),
    # merkezden kenara uzanan kalın huzme/ışın YOK.
    def _build_calm_mode(self):
        import random
        self.calm_c = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.calm_c.bind("<Button-1>", self._calm_click)
        self.calm_c.bind("<Motion>", self._calm_motion)
        self.calm_c.bind("<Key>", self._calm_key)
        # yıldız alanı: göreli koordinatlar (0..1), yavaş sürüklenme + titreşim
        self._calm_stars = [{
            "x": random.random(), "y": random.random(),
            "vx": random.uniform(-0.00006, 0.00006),
            "vy": random.uniform(-0.00003, 0.00003),
            "ph": random.uniform(0, math.tau),
            "sp": random.uniform(0.6, 1.8),
            "sz": random.choice((1, 1, 1, 2)),
            "ac": random.random() < 0.15,   # %15'i vurgu renginde
        } for _ in range(55)]
        # yörünge uyduları (veri zerreleri)
        self._calm_motes = [{
            "tilt": math.radians(t), "speed": s, "ph": random.uniform(0, math.tau)
        } for t, s in ((18, 0.35), (-24, 0.27), (64, 0.21))]

    def _toggle_calm(self):
        if self._calm_visible:
            self._hide_calm()
        else:
            self._show_calm()

    def _show_calm(self):
        self.calm_c.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lift(self.calm_c)   # Canvas.lift öğe kaldırır, widget değil
        self.calm_c.focus_set()
        self._calm_visible = True
        self._calm_intro = 0.0      # yumuşak açılış geçişi
        # saate göre selamlama, ipucu döngüsünün başına
        hr = datetime.now().hour
        greet = ("GÜNAYDIN" if 5 <= hr < 12 else
                 "İYİ GÜNLER" if 12 <= hr < 18 else
                 "İYİ AKŞAMLAR" if 18 <= hr < 23 else "İYİ GECELER")
        greets = ("GÜNAYDIN", "İYİ GÜNLER", "İYİ AKŞAMLAR", "İYİ GECELER")
        if self._calm_hints and self._calm_hints[0] in greets:
            self._calm_hints[0] = greet
        else:
            self._calm_hints.insert(0, greet)
        self._calm_hint_i = 0
        self._calm_hint_f = 0

    def _calm_motion(self, event):
        w = self.calm_c.winfo_width() or 1
        h = self.calm_c.winfo_height() or 1
        self._calm_mouse_t = (event.x / w - 0.5, event.y / h - 0.5)
        self._calm_mouse_px = (event.x, event.y)
        self._calm_last_mouse_move = time.time()

    def _mark_activity(self, event=None):
        self._last_activity = time.time()

    def _tick_idle(self):
        """HUD'da uzun süre etkileşim olmazsa kendiliğinden sakin moda geç."""
        try:
            mins = float(self.settings.get("calm_idle_minutes", 3))
        except (TypeError, ValueError):
            mins = 3.0
        if (mins > 0 and not self._calm_visible
                and time.time() - self._last_activity > mins * 60):
            self._show_calm()
        self.root.after(5000, self._tick_idle)

    def _calm_key(self, event):
        """Sakin modda yazmaya başlayınca terminale düş (akıcı geçiş)."""
        ch = event.char
        if not ch or not ch.isprintable() or not ch.strip():
            return
        self._hide_calm()
        try:
            self.nb.select(0)               # TERMİNAL sekmesi
            self.entry.insert("end", ch)
            self.entry.focus_set()
            self.entry.icursor("end")
        except Exception:
            pass

    def _hide_calm(self):
        self.calm_c.place_forget()
        self._calm_visible = False
        self._calm_notif = 0
        try:
            self.entry.focus_set()
        except Exception:
            pass

    def _calm_click(self, event):
        w = self.calm_c.winfo_width() or 1
        h = self.calm_c.winfo_height() or 1
        mx, my = self._calm_mic_pos
        if (event.x - mx) ** 2 + (event.y - my) ** 2 <= 36 ** 2:
            self._toggle_voice()
            return
        if event.x > w - 180 and event.y > h - 56:
            self._hide_calm()
            return
        # sağ üst bildirim rozeti → HUD'a geç
        if self._calm_notif and (event.x - (w - 52)) ** 2 + (event.y - 52) ** 2 <= 20 ** 2:
            self._hide_calm()
            return
        # rozete tıklama: kıvılcım + nabız geri bildirimi
        cx, cy = w / 2, h / 2 - 26
        if (event.x - cx) ** 2 + (event.y - cy) ** 2 <= 200 ** 2:
            self._calm_burst()

    def _calm_burst(self):
        import random
        if len(self._calm_sparks) > 80:   # görünmezken birikmesin
            del self._calm_sparks[:16]
        for _ in range(16):
            a = random.uniform(0, math.tau)
            v = random.uniform(2.2, 4.6)
            self._calm_sparks.append({
                "a": a, "r": 120.0,
                "vr": v, "life": 1.0,
            })
        self._calm_pulses.append({"r": 120.0, "v": 2.4, "a0": 0.5})

    def _animate_calm(self):
        # uyarlanabilir kare hızı: boşta 25fps, hareket varken 50fps,
        # sakin mod kapalıyken sadece seyrek nabız kontrolü
        delay = 120
        if self._calm_visible:
            try:
                self._draw_calm_frame()
            except Exception:
                pass
            fast = (self._voice_state != "idle" or self._calm_sparks
                    or self._calm_glitch or self._calm_intro < 0.95
                    or time.time() - self._calm_last_mouse_move < 1.5)
            delay = 20 if fast else 40
        self._calm_dt = delay / 1000.0
        self.root.after(delay, self._animate_calm)

    def _draw_calm_frame(self):
        import random
        c = self.calm_c
        c.delete("all")
        self._calm_t += self._calm_dt
        t = self._calm_t
        w = c.winfo_width() or 1200
        h = c.winfo_height() or 760

        # tema geçişi: renkler hedefe doğru akar
        if _theme_tick():
            c.config(bg=BG)

        # gece kısılması: 23:00–07:00 arası genel parlaklık yumuşakça düşer
        hr = datetime.now().hour
        night = (self._calm_night if self._calm_night is not None
                 else (hr >= 23 or hr < 7))
        self._calm_dim += ((0.6 if night else 1.0) - self._calm_dim) * 0.03

        # fare ofsetini yumuşat (paralaks için)
        tx, ty = self._calm_mouse_t
        self._calm_mouse[0] += (tx - self._calm_mouse[0]) * 0.05
        self._calm_mouse[1] += (ty - self._calm_mouse[1]) * 0.05

        self._draw_calm_bg(c, w, h, t)
        self._draw_calm_scene(c, w, h, t)

    # ---- arka plan: radyal parlama, yıldızlar, köşe parantezleri ----
    def _draw_calm_bg(self, c, w, h, t):
        import random
        cx, cy = w / 2, h / 2 - 26
        dim = self._calm_dim   # gece kısılması çarpanı

        # merkezden dışa mor-siyah radyal parlama (iç içe soluk oval katmanlar)
        rmax = max(w, h) * 0.75
        for i in range(9, 0, -1):
            r = rmax * i / 9
            col = _mix(BG, ACCENT_LOW, 0.085 * dim * (1 - i / 9) ** 1.6)
            c.create_oval(cx - r, cy - r * 0.82, cx + r, cy + r * 0.82,
                          fill=col, outline="")

        # yıldız alanı: yavaş sürüklenme + parlaklık titreşimi + fare paralaksı
        mxo, myo = self._calm_mouse
        for s in self._calm_stars:
            s["x"] = (s["x"] + s["vx"]) % 1.0
            s["y"] = (s["y"] + s["vy"]) % 1.0
            b = (0.18 + 0.42 * abs(math.sin(t * s["sp"] + s["ph"]))) * dim
            depth = 0.5 if s["sz"] == 1 else 1.0   # büyük yıldız = yakın katman
            x = s["x"] * w - mxo * 9 * depth
            y = s["y"] * h - myo * 7 * depth
            r = s["sz"]
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill=_fade(ACCENT if s["ac"] else WHITE, b),
                          outline="")

        # çok nadir, kısa ve soluk kayan yıldız
        if self._calm_shoot is None and random.random() < 0.002:
            self._calm_shoot = {"x": random.uniform(0.1, 0.9) * w,
                                "y": random.uniform(0.05, 0.4) * h,
                                "vx": random.choice((-1, 1)) * random.uniform(4, 6),
                                "vy": random.uniform(1.5, 3), "life": 1.0}
        if self._calm_shoot:
            sh = self._calm_shoot
            sh["x"] += sh["vx"]
            sh["y"] += sh["vy"]
            sh["life"] -= 0.04
            if sh["life"] <= 0:
                self._calm_shoot = None
            else:
                a = 0.3 * sh["life"] * dim
                c.create_line(sh["x"], sh["y"],
                              sh["x"] - sh["vx"] * 7, sh["y"] - sh["vy"] * 7,
                              fill=_fade(WHITE, a), width=1)

        # köşe HUD parantezleri + üzerinde dolaşan minik ışık noktası
        m, L = 22, 34
        corners = [
            ((m + L, m), (m, m), (m, m + L)),
            ((w - m - L, m), (w - m, m), (w - m, m + L)),
            ((w - m - L, h - m), (w - m, h - m), (w - m, h - m - L)),
            ((m + L, h - m), (m, h - m), (m, h - m - L)),
        ]
        for p1, p2, p3 in corners:
            c.create_line(*p1, *p2, *p3, fill=_fade(ACCENT, 0.45 * dim), width=1)
        # ışık noktası: 4 parantezi sırayla dolaşır
        prog = (t * 0.22) % 1.0
        ci = int(prog * 4)
        u = (prog * 4) % 1.0
        p1, p2, p3 = corners[ci]
        if u < 0.5:
            k = u * 2
            px = p1[0] + (p2[0] - p1[0]) * k
            py = p1[1] + (p2[1] - p1[1]) * k
        else:
            k = (u - 0.5) * 2
            px = p2[0] + (p3[0] - p2[0]) * k
            py = p2[1] + (p3[1] - p2[1]) * k
        c.create_oval(px - 1.6, py - 1.6, px + 1.6, py + 1.6,
                      fill=_fade(GLOW, 0.9 * dim), outline="")

        # üst orta: yumuşak fade ile dönen durum ipuçları
        period = 320  # kare (~6.4 sn)
        self._calm_hint_f = (self._calm_hint_f + 1) % period
        f = self._calm_hint_f
        if f == 0:
            self._calm_hint_i = (self._calm_hint_i + 1) % len(self._calm_hints)
        if f < 50:
            alpha = f / 50
        elif f > period - 50:
            alpha = (period - f) / 50
        else:
            alpha = 1.0
        hint = self._calm_hints[self._calm_hint_i]
        c.create_text(w / 2, 34, text="  ".join(hint),
                      fill=_fade(ACCENT, 0.55 * alpha * dim),
                      font=("Consolas", 9))

        # ipuçlarının altında: son JARVIS yanıtının fısıltısı (~9 sn)
        # (bilgi taşıdığı için gecede fazla kısılmaz)
        if self._calm_whisper:
            wtxt, wts = self._calm_whisper
            age = time.time() - wts
            if age > 9:
                self._calm_whisper = None
            else:
                env = min(1.0, age / 0.5) * min(1.0, max(0.0, (9 - age) / 2))
                c.create_text(w / 2, 58, text=wtxt,
                              fill=_fade(WHITE, 0.5 * env * max(dim, 0.85)),
                              font=("Consolas", 9))

        # sol üst: hava durumu köşesi
        wd = self._calm_weather
        if wd:
            try:
                wtx = f"{wd['icon']} {wd['temp']}°  {str(wd['desc']).upper()[:20]}"
                c.create_text(26, 34, anchor="w", text=wtx,
                              fill=_fade(FG, 0.45 * dim), font=("Consolas", 9))
            except Exception:
                pass

        # sol alt: soluk sistem telemetrisi
        try:
            up_min = int(time.time() - self.orch.stats.get("started", time.time())) // 60
        except Exception:
            up_min = 0
        cpu = self._sys_vals.get("CPU", 0)
        ram = self._sys_vals.get("RAM", 0)
        tele = f"CPU {cpu:.0f}%   ·   RAM {ram:.0f}%   ·   OTURUM {up_min} DK"
        c.create_text(26, h - 26, anchor="sw", text=tele,
                      fill=_fade(FG, 0.42 * dim), font=("Consolas", 9))

        # sağ üst: bekleyen bildirim rozeti (tıklanınca HUD'a geçer)
        if self._calm_notif:
            bx, by = w - 52, 52
            pulse = 0.55 + 0.18 * math.sin(t * 3.2)
            c.create_oval(bx - 13, by - 13, bx + 13, by + 13,
                          outline=_fade(ACCENT, pulse), width=1,
                          fill=_mix(BG, ACCENT_LOW, 0.2))
            c.create_text(bx, by, text=str(min(self._calm_notif, 9)),
                          fill=_fade(WHITE, 0.85), font=("Consolas", 10, "bold"))
            c.create_text(bx, by + 24, text="BİLDİRİM",
                          fill=_fade(ACCENT, 0.4 * pulse), font=("Consolas", 7))

    # ---- merkez sahne: rozet + uydu ögeleri ----
    def _draw_calm_scene(self, c, w, h, t):
        import random
        # açılış geçişi: sahne yumuşakça belirir + reaktör parça parça kurulur
        self._calm_intro += (1 - self._calm_intro) * 0.06
        if self._calm_intro > 0.995:
            self._calm_intro = 1.0
        ia = self._calm_intro
        dim = self._calm_dim

        def fade(col, a):
            return _fade(col, a * ia * dim)

        def stage(a0, a1):
            """Kurulum sahnesi: ia [a0..a1] aralığında 0→1 rampası."""
            if ia >= a1:
                return 1.0
            if ia <= a0:
                return 0.0
            return (ia - a0) / (a1 - a0)

        # aktiflik hedefi: boşta küçük, dinlerken en büyük
        target = {"idle": 0.0, "listening": 1.0,
                  "processing": 0.7, "speaking": 0.85}.get(self._voice_state, 0.0)
        self._calm_scale += (target - self._calm_scale) * 0.08
        sc = self._calm_scale

        # holografik glitch: sadece rozet birkaç piksel titrer
        if self._calm_glitch > 0:
            self._calm_glitch -= 1
            gdx = random.uniform(-3, 3)
            gdy = random.uniform(-2, 2)
        else:
            gdx = gdy = 0.0
            if random.random() < 0.004:
                self._calm_glitch = 3

        # yavaş süzülme (Lissajous, ±6 px) + fare paralaksı (ön katman)
        gdx += 5 * math.sin(t * 0.13) - self._calm_mouse[0] * 16
        gdy += 4 * math.sin(t * 0.11 + 1.7) - self._calm_mouse[1] * 12

        breathe = 1 + 0.045 * math.sin(t * 1.7)
        Rbase = 190 * (0.55 + 0.45 * sc)
        R = Rbase * breathe * (0.92 + 0.08 * ia)
        cx = w / 2 + gdx
        cy = h / 2 - 26 + gdy

        # dönen halkalar için mor ↔ mavi-mor renk kayması (shimmer)
        shim = 0.5 + 0.5 * math.sin(t * 0.6)
        deco_ac = _mix(ACCENT, "#7aa2ff", 0.45 * shim)

        # --- dış chevron/diş halkası (18 üçgen, kurulumda sırayla belirir) ---
        rj = R * 1.14
        ang0 = t * 9
        for k in range(int(18 * stage(0.5, 0.85))):
            a = math.radians(ang0 + k * 20)
            tipx = cx + (rj + 7) * math.cos(a)
            tipy = cy + (rj + 7) * math.sin(a)
            b1x = cx + rj * math.cos(a - 0.055)
            b1y = cy + rj * math.sin(a - 0.055)
            b2x = cx + rj * math.cos(a + 0.055)
            b2y = cy + rj * math.sin(a + 0.055)
            c.create_polygon(tipx, tipy, b1x, b1y, b2x, b2y,
                             fill=fade(deco_ac, 0.45), outline="")

        # --- ince sabit çemberler (kurulumda yay olarak çizilir) ---
        s_circ = stage(0.15, 0.5)
        for r, a in ((R, 0.35), (R * 0.78, 0.3), (R * 0.55, 0.25)):
            if s_circ < 1.0:
                c.create_arc(cx - r, cy - r, cx + r, cy + r,
                             start=90, extent=-359.9 * s_circ, style="arc",
                             outline=fade(ACCENT, a), width=1)
            else:
                c.create_oval(cx - r, cy - r, cx + r, cy + r,
                              outline=fade(ACCENT, a), width=1)

        # --- ince tik kadranı (60 tik = 60 saniye, gerçek saniye ibresi) ---
        now = datetime.now()
        hl = ((now.second + now.microsecond / 1e6) * 6 - 90) % 360
        for k in range(int(60 * stage(0.35, 0.65))):
            adeg = k * 6
            diff = min(abs(adeg - hl), 360 - abs(adeg - hl))
            a = math.radians(adeg)
            r1, r2 = R * 0.94, R * 0.99
            al = 0.22 + 0.48 * max(0.0, 1 - diff / 18)
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=fade(ACCENT, al), width=1)

        # --- rozet içinde yavaşça dönen mikro-yazı halkası ---
        s_txt = stage(0.3, 0.55)
        if s_txt > 0:
            ring_txt = "JARVIS · STARK INDUSTRIES · ARC REACTOR · MK VII · "
            n = len(ring_txt)
            rr = R * 0.715
            base = -t * 5
            for i, ch in enumerate(ring_txt):
                if ch == " ":
                    continue
                adeg = base + i * (360 / n)
                a = math.radians(adeg)
                x = cx + rr * math.cos(a)
                y = cy + rr * math.sin(a)
                try:
                    c.create_text(x, y, text=ch, fill=fade(ACCENT, 0.3 * s_txt),
                                  font=("Consolas", 7), angle=-adeg - 90)
                except tk.TclError:
                    c.create_text(x, y, text=ch, fill=fade(ACCENT, 0.3 * s_txt),
                                  font=("Consolas", 7))

        # --- amber geri sayım yayı: hatırlatıcıya son 10 dakika ---
        if self._calm_rem_dt:
            rem_s = (self._calm_rem_dt - now).total_seconds()
            if 0 < rem_s <= 600:
                frac = rem_s / 600
                amber = "#ffb74d"
                ra = R * 0.85
                s_amb = stage(0.6, 0.9)
                c.create_arc(cx - ra, cy - ra, cx + ra, cy + ra,
                             start=90, extent=-359.9 * frac, style="arc",
                             outline=fade(amber, 0.5 * s_amb), width=1)
                th = math.radians(90 - 360 * frac)
                px_ = cx + ra * math.cos(th)
                py_ = cy - ra * math.sin(th)
                pl = 0.6 + 0.25 * math.sin(t * 4)
                c.create_oval(px_ - 2, py_ - 2, px_ + 2, py_ + 2,
                              fill=fade(amber, pl * s_amb), outline="")
                c.create_text(cx, cy - ra - 12,
                              text=f"⏰ {int(rem_s // 60) + 1} DK",
                              fill=fade(amber, 0.55 * s_amb),
                              font=("Consolas", 8))

        # --- dış dönen yay parçaları + kromatik (RGB) kayma ---
        s_arc = stage(0.55, 0.85)
        for k in range(4):
            a0 = t * 40 + k * 90
            box = (cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8)
            c.create_arc(box[0] + 2, box[1], box[2] + 2, box[3],
                         start=a0, extent=38, style="arc",
                         outline=fade("#ff6666", 0.22 * s_arc), width=1)
            c.create_arc(box[0] - 2, box[1], box[2] - 2, box[3],
                         start=a0, extent=38, style="arc",
                         outline=fade("#5ee7ff", 0.22 * s_arc), width=1)
            c.create_arc(*box, start=a0, extent=38, style="arc",
                         outline=fade(ACCENT, 0.85 * s_arc), width=2)

        # --- dekoratif uydu noktaları (shimmer renkli) ---
        s_sat = stage(0.6, 0.9)
        for k in range(6):
            a = math.radians(-t * 16 + k * 60)
            x = cx + R * 0.88 * math.cos(a)
            y = cy + R * 0.88 * math.sin(a)
            c.create_oval(x - 2, y - 2, x + 2, y + 2,
                          fill=fade(deco_ac, 0.8 * s_sat), outline="")

        # --- içte ters yönde dönen 22 noktalı ikinci kadran ---
        s_dial = stage(0.2, 0.45)
        for k in range(22):
            a = math.radians(-t * 26 + k * (360 / 22))
            x = cx + R * 0.66 * math.cos(a)
            y = cy + R * 0.66 * math.sin(a)
            c.create_oval(x - 1.4, y - 1.4, x + 1.4, y + 1.4,
                          fill=fade(deco_ac, 0.55 * s_dial), outline="")

        # --- radar tarama huzmesi (işlem sırasında hızlanır) ---
        self._calm_sweep -= 6.2 if self._voice_state == "processing" else 2.6
        sweep = self._calm_sweep
        s_swp = stage(0.15, 0.4)
        for i in range(26):
            a = math.radians(sweep + i * 2.4)
            al = 0.42 * (1 - i / 26) ** 1.4 * s_swp
            c.create_line(cx + R * 0.12 * math.cos(a), cy + R * 0.12 * math.sin(a),
                          cx + R * 0.52 * math.cos(a), cy + R * 0.52 * math.sin(a),
                          fill=fade(ACCENT, al), width=1)

        # --- çekirdek parlama (konuşurken hece ritmiyle nabız atar) ---
        if self._voice_state == "speaking":
            talk = abs(math.sin(t * 9)) * 0.6 + abs(math.sin(t * 23.7)) * 0.4
        else:
            talk = 0.0
        core_m = 1 + 0.18 * talk
        for r, col, al in ((R * 0.20, ACCENT_LOW, 0.35), (R * 0.14, ACCENT, 0.55),
                           (R * 0.09, ACCENT, 1.0), (R * 0.045, WHITE, 1.0)):
            r *= core_m
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill=fade(col, al), outline="")
        if talk > 0:
            # sesle nefes alan iki ince konuşma halkası
            for j, (rf, al) in enumerate(((0.27, 0.3), (0.36, 0.18))):
                r = R * rf * (1 + 0.08 * talk)
                c.create_oval(cx - r, cy - r, cx + r, cy + r,
                              outline=fade(ACCENT, al + 0.15 * talk), width=1)

        # --- dışa yayılan nabız halkaları (boşta da, daha yavaş/soluk) ---
        self._calm_pulse_cd -= 1
        if self._calm_pulse_cd <= 0:
            idle = self._voice_state == "idle"
            self._calm_pulses.append({"r": R * 0.95,
                                      "v": 1.1 if idle else 2.2,
                                      "a0": 0.22 if idle else 0.45})
            self._calm_pulse_cd = 135 if idle else 62
        alive = []
        for p in self._calm_pulses:
            p["r"] += p["v"]
            span = R * 0.85
            k = (p["r"] - R * 0.95) / span
            if k < 1.0:
                al = p["a0"] * (1 - k)
                r = p["r"]
                c.create_oval(cx - r, cy - r, cx + r, cy + r,
                              outline=fade(ACCENT, al), width=1)
                alive.append(p)
        self._calm_pulses = alive

        # --- durum değişimi kıvılcımları ---
        alive = []
        for s in self._calm_sparks:
            s["r"] += s["vr"]
            s["life"] -= 0.045
            if s["life"] > 0:
                x = cx + s["r"] * math.cos(s["a"])
                y = cy + s["r"] * math.sin(s["a"])
                c.create_oval(x - 1.8, y - 1.8, x + 1.8, y + 1.8,
                              fill=fade(GLOW, s["life"]), outline="")
                alive.append(s)
        self._calm_sparks = alive

        # --- eğik yörüngelerde süzülen veri zerreleri (kuyruklu) ---
        s_mote = stage(0.7, 1.0)
        for mo in (self._calm_motes if s_mote > 0 else ()):
            rx, ry = R * 1.32, R * 0.44
            ct_, st_ = math.cos(mo["tilt"]), math.sin(mo["tilt"])
            for j in range(5):
                a = t * mo["speed"] * 2 - j * 0.09 + mo["ph"]
                ex, ey = rx * math.cos(a), ry * math.sin(a)
                x = cx + ex * ct_ - ey * st_
                y = cy + ex * st_ + ey * ct_
                al = (0.7 if j == 0 else 0.32 * (1 - j / 5)) * s_mote
                r = 2 if j == 0 else 1.2
                c.create_oval(x - r, y - r, x + r, y + r,
                              fill=fade(deco_ac, al), outline="")

        # --- rozet altı: durum etiketi + yumuşak saat ---
        s_ui = stage(0.75, 1.0)
        labels = {"idle": "BEKLEMEDE", "listening": "DİNLİYOR",
                  "processing": "İŞLİYOR", "speaking": "KONUŞUYOR"}
        stxt = labels.get(self._voice_state, "BEKLEMEDE")
        base_y = h / 2 - 26 + 190 * (0.55 + 0.45 * sc)
        c.create_text(w / 2, base_y + 34, text="  ".join(stxt),
                      fill=fade(ACCENT, 0.6 * s_ui), font=("Consolas", 10))
        c.create_text(w / 2, base_y + 66, text=now.strftime("%H:%M"),
                      fill=fade(WHITE, 0.72 * s_ui), font=("Consolas", 24))
        c.create_text(w / 2, base_y + 90,
                      text=f"{_GUN[now.weekday()]}, {now.day} {_AY[now.month-1]}",
                      fill=fade(FG, 0.5 * s_ui), font=("Consolas", 9))

        # --- ajanda satırı: sıradaki hatırlatıcı + açık görevler (boşta) ---
        if t - self._calm_agenda_ts > 5:
            self._calm_agenda_ts = t
            parts = []
            self._calm_rem_dt = None
            try:
                best = None
                for r in self.orch.memory.list_reminders():
                    try:
                        dtv = datetime.fromisoformat(str(r.get("at", "")))
                    except (TypeError, ValueError):
                        continue
                    if best is None or dtv < best[0]:
                        best = (dtv, r)
                if best:
                    self._calm_rem_dt = best[0]
                    parts.append(f"⏰ {best[0].strftime('%H:%M')}  "
                                 f"{str(best[1].get('text', ''))[:24]}")
            except Exception:
                pass
            try:
                open_n = sum(1 for x in self.orch.memory.list_todos()
                             if not x.get("done"))
                if open_n:
                    parts.append(f"◻ {open_n} görev")
            except Exception:
                pass
            self._calm_agenda = "   ·   ".join(parts)
        if self._calm_agenda and sc < 0.3:
            c.create_text(w / 2, base_y + 114, text=self._calm_agenda,
                          fill=fade(FG, 0.42 * s_ui), font=("Consolas", 9))

        # --- mikrofon düğmesi + çevresinde dönen mini yaylar ---
        mx, my = w / 2, h - 84
        self._calm_mic_pos = (mx, my)
        mpx, mpy = self._calm_mouse_px
        near_mic = (mpx - mx) ** 2 + (mpy - my) ** 2 <= 60 ** 2
        voice_on = bool(self.voice_input and getattr(self.voice_input, "_running", False))
        hov = 0.22 if near_mic else 0.0
        c.create_oval(mx - 26, my - 26, mx + 26, my + 26,
                      fill=_mix(BG, ACCENT_LOW, (0.18 + 0.1 * near_mic) * s_ui),
                      outline=fade(ACCENT, ((0.8 if voice_on else 0.5) + hov) * s_ui),
                      width=1)
        c.create_text(mx, my, text="🎤", font=("Segoe UI", 15),
                      fill=fade(WHITE, ((0.9 if voice_on else 0.6) + hov) * s_ui))
        for k in range(3):
            a0 = t * 55 + k * 120
            c.create_arc(mx - 34, my - 34, mx + 34, my + 34,
                         start=a0, extent=46, style="arc",
                         outline=fade(ACCENT,
                                      ((0.62 if voice_on else 0.34) + hov) * s_ui),
                         width=1)
        if near_mic:
            tip = "SESLİ MODU KAPAT" if voice_on else "SESLİ MODU AÇ"
            c.create_text(mx, my + 42, text=tip,
                          fill=fade(ACCENT, 0.55), font=("Consolas", 8))

        # --- mikrofonun iki yanında ince dalga kanatları ---
        active = self._voice_state in ("listening", "processing", "speaking")
        amp = 2.2 + 4.5 * sc + 2.5 * talk   # konuşma ritmi genliğe de işler
        wing_al = 0.28 + 0.3 * sc
        for side in (1, -1):
            pts = []
            for i in range(0, 141, 6):
                x = mx + side * (46 + i)
                ph = t * (6 if active else 2.4) + i * 0.09
                yy = (math.sin(ph) + 0.5 * math.sin(ph * 2.7 + 1.3)) \
                    * amp * (1 - i / 160)
                pts += [x, my + yy]
            c.create_line(pts, fill=fade(ACCENT, wing_al * s_ui), width=1,
                          smooth=True)

        # --- sağ alt: HUD arayüzüne dönüş (hover'da parlar) ---
        near_hud = mpx > w - 180 and mpy > h - 56
        c.create_text(w - 26, h - 26, text="◈ HUD ARAYÜZÜ  [ESC]",
                      anchor="se", fill=_fade(FG, 0.8 if near_hud else 0.5),
                      font=("Consolas", 9))

    # =================================================================
    #  ANİMASYONLAR
    # =================================================================
    def _start_animations(self):
        self._animate_reactor()
        self._animate_wave()
        self._animate_calm()

    def _animate_reactor(self):
        c = self.reactor
        c.delete("all")
        cx, cy, R = 85, 85, 70
        acc, glow = self.accent, self.theme["glow"]
        self._reactor_angle = (self._reactor_angle + 3) % 360

        # dış hex grid halkası
        for i in range(3):
            r = R - i * 14
            spin = self._reactor_angle * (1 + i * 0.4) * (1 if i % 2 == 0 else -1)
            pts = []
            for k in range(6):
                a = math.radians(spin + k * 60)
                pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
            c.create_polygon(pts, outline=acc if i == 0 else glow,
                             fill="", width=2 - (i * 0.3))

        # dönen ark segmentleri
        for k in range(8):
            a0 = self._reactor_angle * 2 + k * 45
            c.create_arc(cx - R + 4, cy - R + 4, cx + R - 4, cy + R - 4,
                         start=a0, extent=22, style="arc", outline=glow, width=2)

        # çekirdek parlama
        for r, col in [(22, acc), (14, glow), (7, "#ffffff")]:
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline="")

        # parçacıklar
        self._update_particles(c, cx, cy, R)

        self.root.after(50, self._animate_reactor)

    def _update_particles(self, c, cx, cy, R):
        import random
        if len(self._particles) < 18 and random.random() < 0.5:
            a = random.uniform(0, 2 * math.pi)
            self._particles.append({"a": a, "r": R, "life": 1.0})
        alive = []
        for p in self._particles:
            p["r"] -= 2.2
            p["life"] -= 0.03
            if p["r"] > 20 and p["life"] > 0:
                x = cx + p["r"] * math.cos(p["a"])
                y = cy + p["r"] * math.sin(p["a"])
                c.create_oval(x - 2, y - 2, x + 2, y + 2,
                              fill=self.theme["glow"], outline="")
                alive.append(p)
        self._particles = alive

    def _reactor_click(self, event):
        # tıklamada enerji dalgası (parçacık patlaması)
        import random
        for _ in range(12):
            self._particles.append({"a": random.uniform(0, 2 * math.pi),
                                    "r": 70, "life": 1.0})
        self._toast("Reaktör senkronize")

    def _animate_wave(self):
        c = self.wave
        c.delete("all")
        w = c.winfo_width() or 600
        h = 90
        acc = self.accent
        self._wave_phase += 0.3

        if self._voice_state in ("listening", "processing"):
            # aktif bar spektrumu
            import random
            n = 40
            bw = w / n
            for i in range(n):
                amp = abs(math.sin(self._wave_phase + i * 0.4)) * (h / 2 - 8)
                amp *= 0.5 + random.random() * 0.7
                x = i * bw + bw / 2
                c.create_line(x, h / 2 - amp, x, h / 2 + amp, fill=acc, width=max(2, bw - 3))
        else:
            # sakin sinüs dalgası
            pts = []
            for x in range(0, w, 6):
                y = h / 2 + math.sin(x * 0.02 + self._wave_phase) * 12
                pts += [x, y]
            if len(pts) >= 4:
                c.create_line(pts, fill=acc, width=2, smooth=True)

        self.root.after(60, self._animate_wave)

    def set_voice_state(self, state):
        if state != self._calm_prev_state:
            self._calm_prev_state = state
            # sakin modda durum geçişi: kıvılcım + genişleyen halka
            self._calm_burst()
        self._voice_state = state
        labels = {"idle": "SİSTEM HAZIR", "listening": "DİNLİYORUM…",
                  "processing": "İŞLENİYOR…", "speaking": "KONUŞUYOR…"}
        try:
            self.status_lbl.config(text=labels.get(state, "SİSTEM HAZIR"))
        except Exception:
            pass

    # =================================================================
    #  SAAT & SİSTEM
    # =================================================================
    def _start_clocks(self):
        self._tick_clock()
        self._tick_system()
        self._tick_idle()

    def _tick_clock(self):
        now = datetime.now()
        t = now.strftime("%H:%M:%S")
        self.top_clock.config(text=t)
        self.digital_clock.config(text=t)
        self.date_lbl.config(text=f"{_GUN[now.weekday()]}, {now.day} {_AY[now.month-1]} {now.year}")
        self._draw_analog_clock(now)
        self.root.after(1000, self._tick_clock)

    def _draw_analog_clock(self, now):
        c = self.clock_canvas
        c.delete("all")
        cx, cy, R = 130, 76, 64
        acc, glow = self.accent, self.theme["glow"]
        # sakin modla aynı dil: ince çift çember + soluk tikler
        c.create_oval(cx - R, cy - R, cx + R, cy + R,
                      outline=_mix(BG_CARD, acc, 0.7), width=1)
        r2_ = R - 5
        c.create_oval(cx - r2_, cy - r2_, cx + r2_, cy + r2_,
                      outline=_mix(BG_CARD, acc, 0.25), width=1)
        for i in range(12):
            a = math.radians(i * 30 - 90)
            r1, r2 = R - 8, R - 2
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=_mix(BG_CARD, glow, 0.55), width=1)
        # akrep, yelkovan, saniye
        h = now.hour % 12 + now.minute / 60
        m = now.minute + now.second / 60
        s = now.second
        for val, length, width, col, full in [
            (h / 12, R * 0.5, 4, FG, 12),
            (m / 60, R * 0.72, 3, acc, 60),
            (s / 60, R * 0.82, 1, "#ff5252", 60)]:
            a = math.radians(val * 360 - 90)
            c.create_line(cx, cy, cx + length * math.cos(a),
                          cy + length * math.sin(a), fill=col, width=width)
        c.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=acc, outline="")

    def _tick_system(self):
        # sistem çubukları
        vals = {"CPU": 0, "RAM": 0, "DİSK": 0, "PİL": 0}
        if _PSUTIL_OK:
            try:
                vals["CPU"] = psutil.cpu_percent()
                vals["RAM"] = psutil.virtual_memory().percent
                vals["DİSK"] = psutil.disk_usage("/").percent
                batt = psutil.sensors_battery()
                if batt:
                    vals["PİL"] = batt.percent
                    plug = "⚡" if batt.power_plugged else "🔋"
                    self.battery_lbl.config(text=f"{plug} {int(batt.percent)}%")
            except Exception:
                pass
        self._sys_vals = vals   # sakin mod telemetrisi de bunu okur
        for key, (cv, lbl) in self.bars.items():
            v = vals[key]
            cv.delete("all")
            # segmentli HUD çubuğu: dolu kısım vurguya doğru parlayan dilimler
            segs, bw = 20, 160 / 20
            lit = round(segs * v / 100)
            hot = v > 85
            for i in range(segs):
                x0 = i * bw
                if i < lit:
                    col = ("#ff5252" if hot else
                           _mix(BG, self.accent, 0.4 + 0.6 * (i + 1) / segs))
                else:
                    col = _mix(BG, WHITE, 0.05)
                cv.create_rectangle(x0 + 1, 2, x0 + bw - 1, 10,
                                    fill=col, outline="")
            lbl.config(text=f"{int(v)}%")

        # akıllı ev durumu
        if self.smart_home and self.smart_home.available:
            state = self.smart_home.get_state("priz")
            tr = {"on": "açık ✅", "off": "kapalı ⭕"}.get(state, state)
            self.home_lbl.config(text=f"🏠 Priz: {tr}")
        else:
            self.home_lbl.config(text="🏠 Akıllı Ev: bağlı değil")

        # hava durumu (her 5 dk)
        if self.weather and self.weather.available:
            if not hasattr(self, "_last_weather") or time.time() - self._last_weather > 300:
                w = self.weather.get()
                if w:
                    self.weather_lbl.config(
                        text=f"{w['icon']} {w['city']} {w['temp']}°C\n{w['desc']}")
                    self._calm_weather = w
                self._last_weather = time.time()

        self.root.after(2000, self._tick_system)

    # =================================================================
    #  TEMA / MUTE / SES
    # =================================================================
    def set_theme(self, name):
        name = name.upper()
        if name not in THEMES:
            return
        self.theme_name = name
        self.theme = THEMES[name]
        _apply_theme(name, animate=True)   # sakin mod renkleri akarak döner
        self.accent = self.theme["accent"]
        self.theme_var.set(name)
        # sakin mod her karede globalleri okur; canvas zeminini de eşitle
        try:
            self.calm_c.config(bg=BG)
        except Exception:
            pass
        # temayı kalıcı yap
        try:
            self.settings["theme"] = name
            save_settings(self.settings)
        except Exception:
            pass
        # renkleri güncelle
        for widget in [self.title_lbl, self.top_clock, self.digital_clock,
                       self.status_lbl, self.home_lbl]:
            try:
                widget.config(fg=self.accent)
            except Exception:
                pass
        try:
            self.chat.tag_config("jarvis", foreground=self.accent)
            self.stats_text.config(fg=self.accent)
        except Exception:
            pass
        # kartlar, ttk stilleri ve giriş kutuları yeni paletle boyanır
        try:
            self._style_ttk()
        except Exception:
            pass
        for outer, bar in getattr(self, "_cards", []):
            try:
                outer.config(highlightbackground=_mix(
                    self.theme["bg_card"], self.accent, 0.25))
                bar.config(bg=self.accent)
            except Exception:
                pass
        self._polish_entries()
        self._toast(f"Tema: {name}")

    def _toggle_mute(self):
        if self.voice_output:
            muted = self.voice_output.toggle_mute()
            self.mute_btn.config(text="🔇" if muted else "🔊")

    def _toggle_voice(self):
        if not self.voice_input or not getattr(self.voice_input, "available", False):
            self._toast("Ses girişi kullanılamıyor")
            return
        if getattr(self.voice_input, "_running", False):
            self.voice_input.stop()
            self.voice_btn.config(text="🎤 OFF", fg=FG_DIM)
            self.set_voice_state("idle")
        else:
            self.voice_input.on_command = lambda cmd: self.root.after(
                0, lambda: self._run_command(cmd, from_voice=True))
            self.voice_input.on_status = lambda s: self.root.after(
                0, lambda: self.set_voice_state(s if s in
                ("listening", "processing", "idle") else "idle"))
            self.voice_input.start()
            self.voice_btn.config(text="🎤 ON", fg=self.accent)
            self._toast("Sesli mod aktif")

    # =================================================================
    #  TOAST BİLDİRİMLERİ
    # =================================================================
    def _toast(self, msg, duration=3000):
        if self._calm_visible:
            self._calm_notif += 1   # sakin mod rozet sayacı
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.configure(bg=self.accent)
        try:
            t.attributes("-topmost", True)
            t.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        lbl = tk.Label(t, text=f"  {msg}  ", bg=BG3, fg=self.accent,
                       font=("Consolas", 10, "bold"), padx=10, pady=8)
        lbl.pack(padx=1, pady=1)
        self.root.update_idletasks()
        fx = self.root.winfo_x() + self.root.winfo_width() - 260
        fy = self.root.winfo_y() + 60 + len(self._toasts) * 50
        t.geometry(f"+{fx + 36}+{fy}")
        self._toasts.append(t)

        def close():
            try:
                self._toasts.remove(t)
            except ValueError:
                pass
            try:
                t.destroy()
            except Exception:
                pass

        def slide(k=0):
            """Sağdan kayarak + soluklaşarak giriş (ease-out)."""
            if not t.winfo_exists():
                return
            p = min(1.0, k / 10)
            ease = 1 - (1 - p) ** 3
            try:
                t.geometry(f"+{int(fx + 36 * (1 - ease))}+{fy}")
                t.attributes("-alpha", ease)
            except tk.TclError:
                pass
            if p < 1.0:
                t.after(16, lambda: slide(k + 1))

        def fade_out(k=0):
            if not t.winfo_exists():
                return
            p = min(1.0, k / 8)
            try:
                t.attributes("-alpha", 1 - p)
            except tk.TclError:
                pass
            if p < 1.0:
                t.after(16, lambda: fade_out(k + 1))
            else:
                close()

        slide()
        t.after(duration, fade_out)

    # =================================================================
    #  BOOT & ÇALIŞTIRMA
    # =================================================================
    def _boot_sequence(self):
        lines = [
            "◆ JARVIS çekirdeği başlatılıyor…",
            "◆ Bellek modülü yüklendi.",
            f"◆ AI Brain: {'aktif' if getattr(self.orch.ai_brain,'available',False) else 'çevrimdışı'}",
            f"◆ Akıllı ev: {'bağlı' if (self.smart_home and self.smart_home.check_connection()) else 'bağlantı yok'}",
            "◆ Tüm sistemler hazır. Buyurun, Efendim.",
        ]
        for i, line in enumerate(lines):
            self.root.after(i * 300, lambda l=line: self._append_chat("SİSTEM", l, "sys"))

    def _shutdown(self):
        try:
            if self.voice_input and getattr(self.voice_input, "_running", False):
                self.voice_input.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        self.root.mainloop()
