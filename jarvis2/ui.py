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


def _apply_theme(name):
    """Global palet değişkenlerini seçilen temaya göre ayarlar."""
    global ACCENT, ACCENT_LOW, ACCENT_DIM, GLOW
    global BG, BG_SOFT, BG_CARD, BG2, BG3, WHITE, FG, FG_DIM
    t = THEMES.get(name, THEMES[DEFAULT_THEME])
    ACCENT = t["accent"]
    ACCENT_LOW = t["accent2"]
    ACCENT_DIM = ACCENT_LOW
    GLOW = t["glow"]
    BG = t["bg"]
    BG_SOFT = BG2 = t["bg_soft"]
    BG_CARD = BG3 = t["bg_card"]
    WHITE = t["white"]
    FG = t["fg"]
    FG_DIM = t["fg_dim"]


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
        self._calm_hints = [
            "REAKTÖR ÇEVRİMİÇİ", "AĞ STABİL", "GÜVENLİK PROTOKOLLERİ AKTİF",
            "SENSÖR AĞI TARANIYOR", "ENERJİ AKIŞI NOMİNAL",
            "TÜM SİSTEMLER NOMİNAL", "BEKLEME MODU",
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

        # sakin mod (tam ekran canvas, açılış görünümü)
        self._build_calm_mode()
        self.root.bind("<Escape>", lambda e: self._toggle_calm())

        # toast katmanı
        self._toasts = []

        # uygulama açılışta sakin moda düşer
        self.root.after(80, self._show_calm)

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
    def _build_left_panel(self, parent):
        left = tk.Frame(parent, bg=BG2, width=300)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        # analog + dijital saat
        self.clock_canvas = tk.Canvas(left, width=280, height=180, bg=BG2,
                                      highlightthickness=0)
        self.clock_canvas.pack(pady=(10, 0))

        self.digital_clock = tk.Label(left, text="--:--:--", bg=BG2,
                                      fg=self.accent, font=("Consolas", 20, "bold"))
        self.digital_clock.pack()
        self.date_lbl = tk.Label(left, text="", bg=BG2, fg=FG_DIM,
                                 font=("Consolas", 10))
        self.date_lbl.pack(pady=(0, 8))

        # hava durumu
        self.weather_lbl = tk.Label(left, text="", bg=BG2, fg=FG,
                                    font=("Consolas", 11), wraplength=270,
                                    justify="center")
        self.weather_lbl.pack(pady=(0, 6))

        # sistem çubukları
        self._build_sys_bars(left)

        # akıllı ev durumu
        self.home_lbl = tk.Label(left, text="🏠 Akıllı Ev: —", bg=BG2, fg=FG,
                                 font=("Consolas", 10))
        self.home_lbl.pack(pady=(8, 4))

        # hızlı butonlar
        self._build_quick_buttons(left)

    def _build_sys_bars(self, parent):
        frame = tk.Frame(parent, bg=BG2)
        frame.pack(fill="x", padx=16, pady=6)
        self.bars = {}
        for key in ("CPU", "RAM", "DİSK", "PİL"):
            row = tk.Frame(frame, bg=BG2)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=key, bg=BG2, fg=FG_DIM, width=5,
                     anchor="w", font=("Consolas", 9)).pack(side="left")
            cv = tk.Canvas(row, width=180, height=12, bg=BG3,
                           highlightthickness=0)
            cv.pack(side="left", padx=4)
            val = tk.Label(row, text="0%", bg=BG2, fg=FG, width=4,
                           font=("Consolas", 9))
            val.pack(side="left")
            self.bars[key] = (cv, val)

    def _build_quick_buttons(self, parent):
        grid = tk.Frame(parent, bg=BG2)
        grid.pack(fill="x", padx=12, pady=8)
        quick = [
            ("Priz Aç", "priz aç"), ("Priz Kapat", "priz kapat"),
            ("WhatsApp", "whatsapp aç"), ("Hava", "hava durumu"),
            ("Plan", "günaydın"), ("İstatistik", "istatistik"),
            ("Kilitle", "ekranı kilitle"), ("Ekran G.", "ekran görüntüsü al"),
        ]
        for i, (label, cmd) in enumerate(quick):
            b = tk.Button(grid, text=label, bg=BG3, fg=FG, bd=0,
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

    def _build_tabs(self, parent):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG2, foreground=FG_DIM,
                        padding=(12, 6), font=("Consolas", 9, "bold"))
        style.map("TNotebook.Tab",
                  background=[("selected", BG3)],
                  foreground=[("selected", self.accent)])

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
            if key in ("tts_rate", "search_results_count"):
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
        # yıldız alanı: göreli koordinatlar (0..1), yavaş sürüklenme + titreşim
        self._calm_stars = [{
            "x": random.random(), "y": random.random(),
            "vx": random.uniform(-0.00006, 0.00006),
            "vy": random.uniform(-0.00003, 0.00003),
            "ph": random.uniform(0, math.tau),
            "sp": random.uniform(0.6, 1.8),
            "sz": random.choice((1, 1, 1, 2)),
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

    def _hide_calm(self):
        self.calm_c.place_forget()
        self._calm_visible = False
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
        if self._calm_visible:
            try:
                self._draw_calm_frame()
            except Exception:
                pass
        self.root.after(20, self._animate_calm)   # ~50 fps

    def _draw_calm_frame(self):
        import random
        c = self.calm_c
        c.delete("all")
        self._calm_t += 0.02
        t = self._calm_t
        w = c.winfo_width() or 1200
        h = c.winfo_height() or 760

        self._draw_calm_bg(c, w, h, t)
        self._draw_calm_scene(c, w, h, t)

    # ---- arka plan: radyal parlama, yıldızlar, köşe parantezleri ----
    def _draw_calm_bg(self, c, w, h, t):
        import random
        cx, cy = w / 2, h / 2 - 26

        # merkezden dışa mor-siyah radyal parlama (iç içe soluk oval katmanlar)
        rmax = max(w, h) * 0.75
        for i in range(9, 0, -1):
            r = rmax * i / 9
            col = _mix(BG, ACCENT_LOW, 0.085 * (1 - i / 9) ** 1.6)
            c.create_oval(cx - r, cy - r * 0.82, cx + r, cy + r * 0.82,
                          fill=col, outline="")

        # yıldız alanı: yavaş sürüklenme + parlaklık titreşimi
        for s in self._calm_stars:
            s["x"] = (s["x"] + s["vx"]) % 1.0
            s["y"] = (s["y"] + s["vy"]) % 1.0
            b = 0.18 + 0.42 * abs(math.sin(t * s["sp"] + s["ph"]))
            x, y = s["x"] * w, s["y"] * h
            r = s["sz"]
            c.create_oval(x - r, y - r, x + r, y + r,
                          fill=_fade(WHITE, b), outline="")

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
                a = 0.3 * sh["life"]
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
            c.create_line(*p1, *p2, *p3, fill=_fade(ACCENT, 0.45), width=1)
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
                      fill=_fade(GLOW, 0.9), outline="")

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
                      fill=_fade(ACCENT, 0.55 * alpha),
                      font=("Consolas", 9))

    # ---- merkez sahne: rozet + uydu ögeleri ----
    def _draw_calm_scene(self, c, w, h, t):
        import random
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

        breathe = 1 + 0.045 * math.sin(t * 1.7)
        Rbase = 190 * (0.55 + 0.45 * sc)
        R = Rbase * breathe
        cx = w / 2 + gdx
        cy = h / 2 - 26 + gdy

        # dönen halkalar için mor ↔ mavi-mor renk kayması (shimmer)
        shim = 0.5 + 0.5 * math.sin(t * 0.6)
        deco_ac = _mix(ACCENT, "#7aa2ff", 0.45 * shim)

        # --- dış chevron/diş halkası (18 üçgen, yavaş dönüş) ---
        rj = R * 1.14
        ang0 = t * 9
        for k in range(18):
            a = math.radians(ang0 + k * 20)
            tipx = cx + (rj + 7) * math.cos(a)
            tipy = cy + (rj + 7) * math.sin(a)
            b1x = cx + rj * math.cos(a - 0.055)
            b1y = cy + rj * math.sin(a - 0.055)
            b2x = cx + rj * math.cos(a + 0.055)
            b2y = cy + rj * math.sin(a + 0.055)
            c.create_polygon(tipx, tipy, b1x, b1y, b2x, b2y,
                             fill=_fade(deco_ac, 0.45), outline="")

        # --- ince sabit çemberler ---
        for r, a in ((R, 0.35), (R * 0.78, 0.3), (R * 0.55, 0.25)):
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          outline=_fade(ACCENT, a), width=1)

        # --- ince tik kadranı (60 çizgi) + dönen vurgu yayı ---
        hl = (t * 24) % 360
        for k in range(60):
            adeg = k * 6
            diff = min(abs(adeg - hl), 360 - abs(adeg - hl))
            a = math.radians(adeg)
            r1, r2 = R * 0.94, R * 0.99
            al = 0.6 if diff < 18 else 0.22
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=_fade(ACCENT, al), width=1)

        # --- dış dönen yay parçaları + kromatik (RGB) kayma ---
        for k in range(4):
            a0 = t * 40 + k * 90
            box = (cx - R - 8, cy - R - 8, cx + R + 8, cy + R + 8)
            c.create_arc(box[0] + 2, box[1], box[2] + 2, box[3],
                         start=a0, extent=38, style="arc",
                         outline=_fade("#ff6666", 0.22), width=1)
            c.create_arc(box[0] - 2, box[1], box[2] - 2, box[3],
                         start=a0, extent=38, style="arc",
                         outline=_fade("#5ee7ff", 0.22), width=1)
            c.create_arc(*box, start=a0, extent=38, style="arc",
                         outline=_fade(ACCENT, 0.85), width=2)

        # --- dekoratif uydu noktaları (shimmer renkli) ---
        for k in range(6):
            a = math.radians(-t * 16 + k * 60)
            x = cx + R * 0.88 * math.cos(a)
            y = cy + R * 0.88 * math.sin(a)
            c.create_oval(x - 2, y - 2, x + 2, y + 2,
                          fill=_fade(deco_ac, 0.8), outline="")

        # --- içte ters yönde dönen 22 noktalı ikinci kadran ---
        for k in range(22):
            a = math.radians(-t * 26 + k * (360 / 22))
            x = cx + R * 0.66 * math.cos(a)
            y = cy + R * 0.66 * math.sin(a)
            c.create_oval(x - 1.4, y - 1.4, x + 1.4, y + 1.4,
                          fill=_fade(deco_ac, 0.55), outline="")

        # --- radar tarama huzmesi (kuyruğu sönümlenen) ---
        sweep = -t * 130
        for i in range(26):
            a = math.radians(sweep + i * 2.4)
            al = 0.42 * (1 - i / 26) ** 1.4
            c.create_line(cx + R * 0.12 * math.cos(a), cy + R * 0.12 * math.sin(a),
                          cx + R * 0.52 * math.cos(a), cy + R * 0.52 * math.sin(a),
                          fill=_fade(ACCENT, al), width=1)

        # --- çekirdek parlama ---
        for r, col, al in ((R * 0.20, ACCENT_LOW, 0.35), (R * 0.14, ACCENT, 0.55),
                           (R * 0.09, ACCENT, 1.0), (R * 0.045, WHITE, 1.0)):
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill=_fade(col, al), outline="")

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
                              outline=_fade(ACCENT, al), width=1)
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
                              fill=_fade(GLOW, s["life"]), outline="")
                alive.append(s)
        self._calm_sparks = alive

        # --- eğik yörüngelerde süzülen veri zerreleri (kuyruklu) ---
        for mo in self._calm_motes:
            rx, ry = R * 1.32, R * 0.44
            ct_, st_ = math.cos(mo["tilt"]), math.sin(mo["tilt"])
            for j in range(5):
                a = t * mo["speed"] * 2 - j * 0.09 + mo["ph"]
                ex, ey = rx * math.cos(a), ry * math.sin(a)
                x = cx + ex * ct_ - ey * st_
                y = cy + ex * st_ + ey * ct_
                al = (0.7 if j == 0 else 0.32 * (1 - j / 5))
                r = 2 if j == 0 else 1.2
                c.create_oval(x - r, y - r, x + r, y + r,
                              fill=_fade(deco_ac, al), outline="")

        # --- rozet altı: durum etiketi + yumuşak saat ---
        labels = {"idle": "BEKLEMEDE", "listening": "DİNLİYOR",
                  "processing": "İŞLİYOR", "speaking": "KONUŞUYOR"}
        stxt = labels.get(self._voice_state, "BEKLEMEDE")
        base_y = h / 2 - 26 + 190 * (0.55 + 0.45 * sc)
        c.create_text(w / 2, base_y + 34, text="  ".join(stxt),
                      fill=_fade(ACCENT, 0.6), font=("Consolas", 10))
        now = datetime.now()
        c.create_text(w / 2, base_y + 66, text=now.strftime("%H:%M"),
                      fill=_fade(WHITE, 0.72), font=("Consolas", 24))
        c.create_text(w / 2, base_y + 90,
                      text=f"{_GUN[now.weekday()]}, {now.day} {_AY[now.month-1]}",
                      fill=_fade(FG, 0.5), font=("Consolas", 9))

        # --- mikrofon düğmesi + çevresinde dönen mini yaylar ---
        mx, my = w / 2, h - 84
        self._calm_mic_pos = (mx, my)
        voice_on = bool(self.voice_input and getattr(self.voice_input, "_running", False))
        c.create_oval(mx - 26, my - 26, mx + 26, my + 26,
                      fill=_mix(BG, ACCENT_LOW, 0.18),
                      outline=_fade(ACCENT, 0.8 if voice_on else 0.5), width=1)
        c.create_text(mx, my, text="🎤", font=("Segoe UI", 15),
                      fill=_fade(WHITE, 0.9 if voice_on else 0.6))
        for k in range(3):
            a0 = t * 55 + k * 120
            c.create_arc(mx - 34, my - 34, mx + 34, my + 34,
                         start=a0, extent=46, style="arc",
                         outline=_fade(ACCENT, 0.62 if voice_on else 0.34), width=1)

        # --- sağ alt: HUD arayüzüne dönüş ---
        c.create_text(w - 26, h - 26, text="◈ HUD ARAYÜZÜ  [ESC]",
                      anchor="se", fill=_fade(FG, 0.5), font=("Consolas", 9))

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
        cx, cy, R = 140, 90, 78
        acc, glow = self.accent, self.theme["glow"]
        c.create_oval(cx - R, cy - R, cx + R, cy + R, outline=acc, width=2)
        for i in range(12):
            a = math.radians(i * 30 - 90)
            r1, r2 = R - 8, R
            c.create_line(cx + r1 * math.cos(a), cy + r1 * math.sin(a),
                          cx + r2 * math.cos(a), cy + r2 * math.sin(a),
                          fill=glow, width=2)
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
        for key, (cv, lbl) in self.bars.items():
            v = vals[key]
            cv.delete("all")
            w = 180 * (v / 100)
            col = "#ff5252" if v > 85 else self.accent
            cv.create_rectangle(0, 0, w, 12, fill=col, outline="")
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
        _apply_theme(name)
        self.accent = ACCENT
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
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.configure(bg=self.accent)
        t.attributes("-topmost", True)
        lbl = tk.Label(t, text=f"  {msg}  ", bg=BG3, fg=self.accent,
                       font=("Consolas", 10, "bold"), padx=10, pady=8)
        lbl.pack(padx=2, pady=2)
        self.root.update_idletasks()
        x = self.root.winfo_x() + self.root.winfo_width() - 260
        y = self.root.winfo_y() + 60 + len(self._toasts) * 50
        t.geometry(f"+{x}+{y}")
        self._toasts.append(t)

        def close():
            try:
                self._toasts.remove(t)
                t.destroy()
            except Exception:
                pass
        t.after(duration, close)

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
