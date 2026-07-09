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
THEMES = {
    "CYAN":   {"accent": "#00e5ff", "accent2": "#0091ea", "glow": "#18ffff"},
    "GREEN":  {"accent": "#00e676", "accent2": "#00c853", "glow": "#69f0ae"},
    "RED":    {"accent": "#ff5252", "accent2": "#d50000", "glow": "#ff8a80"},
    "GOLD":   {"accent": "#ffd54f", "accent2": "#ffab00", "glow": "#ffe57f"},
    "PURPLE": {"accent": "#b388ff", "accent2": "#7c4dff", "glow": "#e1bee7"},
    "MATRIX": {"accent": "#39ff14", "accent2": "#00ff41", "glow": "#76ff03"},
    "ORANGE": {"accent": "#ff9100", "accent2": "#ff6d00", "glow": "#ffab40"},
}
BG = "#05070a"
BG2 = "#0b0f14"
BG3 = "#11161d"
FG = "#c8d6e5"
FG_DIM = "#5a6b7b"

_GUN = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
_AY = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
       "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


class JarvisHUD:
    def __init__(self, orchestrator, voice_output=None, voice_input=None,
                 smart_home=None, weather=None, settings=None, bluetooth=None):
        self.orch = orchestrator
        self.voice_output = voice_output
        self.voice_input = voice_input
        self.smart_home = smart_home
        self.weather = weather
        self.bluetooth = bluetooth
        self.settings = settings or {}

        self.theme_name = "CYAN"
        self.theme = THEMES[self.theme_name]
        self.accent = self.theme["accent"]

        # animasyon durumu
        self._reactor_angle = 0.0
        self._radar_angle = 0.0
        self._wave_phase = 0.0
        self._voice_state = "idle"   # idle / listening / processing
        self._particles = []

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
            "buradan konuş", "sesi varsayılana al",
            "/help", "/clear", "/theme CYAN", "/theme GREEN", "/theme MATRIX",
            "/exit", "/stats",
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

        # toast katmanı
        self._toasts = []

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
            text=("Bir ses cihazı seçip 'BURADAN KONUŞ' deyin; JARVIS'in sesi\n"
                  "o cihaza yönlendirilir. (Cihaz önce işletim sisteminde eşleştirilmiş olmalı.)"))
        info.pack(anchor="w", padx=10, pady=(8, 4))

        btnrow = tk.Frame(tab, bg=BG)
        btnrow.pack(fill="x", padx=8, pady=4)
        for label, fn in [("🔍 Tara (BLE)", self._bt_scan),
                          ("🎧 Ses Cihazları", self._bt_audio_list),
                          ("🔗 Eşleşmiş", self._bt_paired),
                          ("🔈 Buradan Konuş", self._bt_speak_here),
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
    #  ANİMASYONLAR
    # =================================================================
    def _start_animations(self):
        self._animate_reactor()
        self._animate_wave()

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
        self.accent = self.theme["accent"]
        self.theme_var.set(name)
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
