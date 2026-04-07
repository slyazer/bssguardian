import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import subprocess
import threading
import os
import time
import json
from datetime import datetime
from pathlib import Path

# ── Colors ─────────────────────────────────────────────────────────────────────
BG      = "#0d0f14"
BG2     = "#13161e"
BG3     = "#1a1e28"
ACCENT  = "#00e5ff"
GREEN   = "#00ff88"
RED     = "#ff3d5a"
YELLOW  = "#ffd060"
TEXT    = "#c8d0e0"
TEXTDIM = "#4a5568"
BORDER  = "#252a38"

CONFIG_FILE = Path(__file__).parent / "guardian_config.json"
AFK_FILE    = Path(__file__).parent / "afk_mode.flag"
PLACE_ID    = "1537690962"
LOG_FILE    = str(Path(__file__).parent / "roblox_monitor_log.txt")
ERROR_LOG   = str(Path(__file__).parent / "roblox_errors.txt")

CHECK_INTERVAL = 60

DEFAULT_CONFIG = {
    "adb_path":   r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    "mumu_exe":   r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\MuMuManager.exe",
    "inst0_name": "slyazer alt",
    "inst1_name": "slyazer 2",
    "inst2_name": "bougnoul",
}


# ── Config ─────────────────────────────────────────────────────────────────────
def load_config():
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return None

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

def validate_config_paths(cfg):
    adb_path = Path(cfg.get("adb_path", ""))
    mumu_path = Path(cfg.get("mumu_exe", ""))
    if adb_path.exists() and mumu_path.exists():
        return cfg

    # Common fallback locations for MuMu and adb on this machine.
    fallback_paths = {
        "adb_path": [
            Path.home() / "Desktop" / "MuMuPlayerGlobal" / "nx_main" / "adb.exe",
            Path.home() / "Desktop" / "MuMuPlayerGlobal" / "nx_device" / "12.0" / "shell" / "adb.exe",
            Path("C:/Program Files/Microvirt/MEmu/adb.exe"),
        ],
        "mumu_exe": [
            Path.home() / "Desktop" / "MuMuPlayerGlobal" / "nx_main" / "MuMuManager.exe",
        ],
    }

    updated = False
    for key, paths in fallback_paths.items():
        current = Path(cfg.get(key, ""))
        if current.exists():
            continue
        for candidate in paths:
            if candidate.exists():
                cfg[key] = str(candidate)
                updated = True
                break

    if updated:
        save_config(cfg)

    return cfg if Path(cfg.get("adb_path", "")).exists() and Path(cfg.get("mumu_exe", "")).exists() else None


def build_instances(cfg):
    instances, i = [], 0
    while True:
        name = cfg.get(f"inst{i}_name")
        if not name:
            break
        instances.append({"name": name, "port": 16384 + i * 32, "index": i})
        i += 1
    return instances or [
        {"name": "slyazer alt", "port": 16384, "index": 0},
        {"name": "slyazer 2",   "port": 16416, "index": 1},
        {"name": "bougnoul",    "port": 16448, "index": 2},
    ]


# ── UI helpers ─────────────────────────────────────────────────────────────────
def _center(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth()  - w) // 2
    y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")

def _header(win, subtitle=None):
    tk.Frame(win, bg=ACCENT, height=2).pack(fill="x")
    tk.Label(win, text="◈  ROBLOX GUARDIAN",
             font=("Courier New", 12, "bold"), fg=ACCENT, bg=BG2, padx=20, pady=12).pack(fill="x")
    if subtitle:
        tk.Label(win, text=subtitle, font=("Courier New", 8),
                 fg=TEXTDIM, bg=BG2, padx=20).pack(fill="x", pady=(0, 8))
    tk.Frame(win, bg=BORDER, height=1).pack(fill="x")


# ── Setup dialog ───────────────────────────────────────────────────────────────
class SetupDialog(tk.Toplevel):
    def __init__(self, parent, existing=None):
        super().__init__(parent)
        self.result = None
        self.title("Setup")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.grab_set()
        _center(self, 560, 420)
        _header(self, "First launch setup — select your MuMu Player paths")

        body = tk.Frame(self, bg=BG, padx=28, pady=16)
        body.pack(fill="both", expand=True)

        cfg = existing or DEFAULT_CONFIG
        self.fields = {}

        # Path fields
        path_rows = [
            ("adb_path", "adb.exe path",        "adb.exe"),
            ("mumu_exe", "MuMuManager.exe path", "MuMuManager.exe"),
        ]
        for key, label, hint in path_rows:
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label, font=("Courier New", 8, "bold"),
                     fg=TEXTDIM, bg=BG, anchor="w", width=22).pack(side="left")
            var = tk.StringVar(value=cfg.get(key, ""))
            self.fields[key] = var
            tk.Entry(row, textvariable=var, font=("Courier New", 8),
                     bg=BG3, fg=TEXT, insertbackground=ACCENT,
                     relief="flat", bd=0).pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 6))
            def make_browse(v=var, h=hint):
                def browse():
                    p = filedialog.askopenfilename(filetypes=[(h, f"*.{h.split('.')[-1]}"), ("All", "*.*")])
                    if p: v.set(p)
                return browse
            tk.Button(row, text="Browse", font=("Courier New", 7),
                      fg=TEXTDIM, bg=BG3, activeforeground=TEXT, activebackground=BG3,
                      relief="flat", cursor="hand2", bd=0, padx=8, pady=5,
                      command=make_browse()).pack(side="left")

        # Instance name fields — dynamic based on how many are in config
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(10, 6))
        tk.Label(body, text="Instance names:", font=("Courier New", 8, "bold"),
                 fg=TEXTDIM, bg=BG, anchor="w").pack(fill="x", pady=(0, 4))

        # Count how many instances exist in config + always show at least 3
        i = 0
        while True:
            key = f"inst{i}_name"
            if not cfg.get(key) and i >= 3:
                break
            i += 1
        num_inst = max(i, 3)

        for idx in range(num_inst):
            key = f"inst{idx}_name"
            row = tk.Frame(body, bg=BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"Instance {idx}:", font=("Courier New", 8),
                     fg=TEXTDIM, bg=BG, anchor="w", width=14).pack(side="left")
            var = tk.StringVar(value=cfg.get(key, f"instance {idx+1}" if idx >= 3 else ""))
            self.fields[key] = var
            tk.Entry(row, textvariable=var, font=("Courier New", 8),
                     bg=BG3, fg=TEXT, insertbackground=ACCENT,
                     relief="flat", bd=0).pack(side="left", fill="x", expand=True, ipady=4)

        tk.Frame(body, bg=BG, height=12).pack()
        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="Save & Continue", font=("Courier New", 10, "bold"),
                  fg=BG, bg=GREEN, activebackground="#00cc6a", activeforeground=BG,
                  relief="flat", cursor="hand2", bd=0, padx=16, pady=10,
                  command=self._save).pack(side="left", padx=(0, 10))
        tk.Button(btn_row, text="Reset defaults", font=("Courier New", 8),
                  fg=TEXTDIM, bg=BG, relief="flat", cursor="hand2", bd=0, padx=8, pady=10,
                  command=self._reset).pack(side="left")

        self.protocol("WM_DELETE_WINDOW", self._save)
        self.wait_window()

    def _save(self):
        cfg = {k: v.get().strip() for k, v in self.fields.items()}
        if not cfg["adb_path"] or not cfg["mumu_exe"]:
            messagebox.showerror("Missing fields", "Both adb.exe and MuMuManager.exe paths are required.")
            return
        for k in ("inst0_name", "inst1_name", "inst2_name"):
            if not cfg[k]:
                cfg[k] = DEFAULT_CONFIG[k]
        self.result = cfg
        self.destroy()

    def _reset(self):
        for k, v in self.fields.items():
            v.set(DEFAULT_CONFIG.get(k, ""))


# ── Instance picker ────────────────────────────────────────────────────────────
class InstancePicker(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("")
        self.resizable(True, True)
        self.configure(bg=BG)
        self.grab_set()

        self._cfg   = load_config() or DEFAULT_CONFIG
        self._known = build_instances(self._cfg)
        self._extra = {}

        # Calculate initial height based on known instances
        inst_h = max(len(self._known) * 18, 40)
        init_h = min(120 + inst_h + 80, 500)
        _center(self, 440, init_h)
        self.minsize(380, 280)

        _header(self, "How many instances do you want to run?")

        # ── Scrollable body ───────────────────────────────────────────────────
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        body = tk.Frame(canvas, bg=BG, padx=24, pady=16)
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body_cfg(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            if body.winfo_reqheight() > canvas.winfo_height():
                sb.pack(side="right", fill="y")
            else:
                sb.pack_forget()

        def _on_canvas_cfg(e):
            canvas.itemconfig(win_id, width=e.width)

        body.bind("<Configure>", _on_body_cfg)
        canvas.bind("<Configure>", _on_canvas_cfg)

        def _scroll(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        canvas.pack(side="left", fill="both", expand=True)

        # ── Content ───────────────────────────────────────────────────────────
        tk.Label(body, text="Known instances:", font=("Courier New", 8, "bold"),
                 fg=TEXTDIM, bg=BG).pack(anchor="w")
        for inst in self._known:
            tk.Label(body,
                     text=f"  {inst['index']+1}  →  {inst['name']}  (port {inst['port']})",
                     font=("Courier New", 7), fg=TEXTDIM, bg=BG).pack(anchor="w")

        tk.Frame(body, bg=BG, height=10).pack()
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x")
        tk.Frame(body, bg=BG, height=10).pack()

        # Count + GO (always visible at bottom of body)
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        tk.Label(row, text="Count:", font=("Courier New", 9, "bold"),
                 fg=TEXT, bg=BG).pack(side="left", padx=(0, 8))
        self._var = tk.StringVar(value=str(len(self._known)))
        self._entry = tk.Entry(row, textvariable=self._var,
                               font=("Courier New", 16, "bold"),
                               bg=BG3, fg=ACCENT, insertbackground=ACCENT,
                               relief="flat", bd=0, width=4, justify="center")
        self._entry.pack(side="left", ipady=8, padx=(0, 12))
        self._entry.focus_set()
        self._entry.select_range(0, "end")
        tk.Button(row, text="GO  ▶", font=("Courier New", 11, "bold"),
                  fg=BG, bg=GREEN, activebackground="#00cc6a", activeforeground=BG,
                  relief="flat", cursor="hand2", bd=0, padx=16, pady=8,
                  command=self._confirm).pack(side="left")

        self._extra_frame = tk.Frame(body, bg=BG)
        self._extra_frame.pack(fill="x", pady=(10, 0))

        # Settings button top-right
        tk.Button(self, text="⚙ Settings", font=("Courier New", 7),
                  fg=TEXTDIM, bg=BG2, activeforeground=TEXT, activebackground=BG2,
                  relief="flat", cursor="hand2", bd=0, padx=8, pady=4,
                  command=self._open_settings).place(relx=1.0, rely=0.0, anchor="ne", x=-8, y=8)

        self._var.trace_add("write", self._on_count_change)
        self.bind("<Return>", lambda e: self._confirm())
        self.protocol("WM_DELETE_WINDOW", self._confirm)
        self.wait_window()

    def _on_count_change(self, *_):
        for w in self._extra_frame.winfo_children():
            w.destroy()
        self._extra.clear()
        try:
            n = int(self._var.get().strip())
        except ValueError:
            return
        extra = n - len(self._known)
        if extra <= 0:
            return
        tk.Label(self._extra_frame, text="Name extra instances:",
                 font=("Courier New", 8, "bold"), fg=YELLOW, bg=BG).pack(anchor="w", pady=(0, 4))
        for i in range(len(self._known), n):
            r = tk.Frame(self._extra_frame, bg=BG)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=f"  Instance {i+1}:",
                     font=("Courier New", 8), fg=TEXTDIM, bg=BG,
                     width=14, anchor="w").pack(side="left")
            var = tk.StringVar(value=f"instance {i+1}")
            tk.Entry(r, textvariable=var, font=("Courier New", 9),
                     bg=BG3, fg=TEXT, insertbackground=ACCENT,
                     relief="flat", bd=0).pack(side="left", fill="x", expand=True, ipady=4)
            self._extra[i] = var

    def _confirm(self):
        try:
            n = max(1, int(self._var.get().strip()))
        except ValueError:
            n = len(self._known)
        instances = list(self._known[:n])
        for i in range(len(self._known), n):
            name = self._extra.get(i, tk.StringVar(value=f"instance {i+1}")).get().strip()
            if not name:
                name = f"instance {i+1}"
            instances.append({"name": name, "port": 16384 + i * 32, "index": i})
            self._cfg[f"inst{i}_name"] = name
        if n > len(self._known):
            save_config(self._cfg)
        self.result = instances
        self.destroy()

    def _open_settings(self):
        d = SetupDialog(self, existing=self._cfg)
        if d.result:
            save_config(d.result)


class RobloxGuardianApp:
    def __init__(self, root, instances, cfg):
        self.root      = root
        self.instances = instances
        self.cfg       = cfg

        self.root.title("Roblox Guardian v2.0")
        self.root.geometry("820x620")
        self.root.minsize(600, 440)
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        # Allow window to grow/shrink freely
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self._stop      = threading.Event()
        self._thread    = None
        self.running    = False
        self.checks     = 0
        self.restarts   = 0
        self.start_time = time.time()
        self._afk_timer = None
        self._disabled  = set()  # set of instance ports manually disabled

        # Pre-build ADB command prefix (avoids rebuilding every call)
        self._adb_exe    = cfg["adb_path"]
        self._mumu_exe   = cfg["mumu_exe"]

        self._build_ui()

        names = " · ".join(i["name"] for i in instances)
        self._log(f"Ready — {len(instances)} instance(s): {names}", ACCENT)

        if self.afk_on:
            self._log("AFK mode resumed — scheduling 2h restart.", YELLOW)
            self._schedule_afk()
            self.root.after(1000, self.start_monitor)

    # ── UI ─────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        bar = tk.Frame(self.root, bg=BG2, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        tk.Label(bar, text="◈  ROBLOX GUARDIAN", font=("Courier New", 15, "bold"),
                 fg=ACCENT, bg=BG2, padx=18).pack(side="left", pady=14)
        tk.Label(bar, text="v2.0", font=("Courier New", 9),
                 fg=TEXTDIM, bg=BG2, padx=4).pack(side="left", pady=14)
        tk.Label(bar, text=f"[ {len(self.instances)} instances ]",
                 font=("Courier New", 8, "bold"), fg=YELLOW, bg=BG2, padx=4).pack(side="left", pady=14)

        self.afk_on = AFK_FILE.exists()
        self._afk_btn = tk.Button(bar,
            text="💤 AFK ON" if self.afk_on else "💤 AFK",
            font=("Courier New", 9, "bold"),
            fg=BG if self.afk_on else TEXTDIM,
            bg=YELLOW if self.afk_on else BG2,
            activeforeground=BG, activebackground=YELLOW,
            relief="flat", cursor="hand2", bd=0, padx=12,
            command=self._toggle_afk)
        self._afk_btn.pack(side="right", pady=14)

        tk.Button(bar, text="⚙", font=("Courier New", 12),
                  fg=TEXTDIM, bg=BG2, activeforeground=TEXT, activebackground=BG2,
                  relief="flat", cursor="hand2", bd=0, padx=12,
                  command=self._open_settings).pack(side="right", pady=14)

        tk.Frame(self.root, bg=ACCENT, height=2).pack(fill="x")

        content = tk.Frame(self.root, bg=BG)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        # Left panel — scrollable instances + fixed buttons at bottom
        left_outer = tk.Frame(content, bg=BG, width=230)
        left_outer.pack(side="left", fill="y", padx=(0, 12))
        left_outer.pack_propagate(False)

        # ── Scrollable area (instances + stats) ──────────────────────────────
        canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(left_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack scrollbar only if needed (we bind configure to show/hide)
        scroll_frame = tk.Frame(canvas, bg=BG)
        scroll_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Show scrollbar only if content overflows
            if scroll_frame.winfo_reqheight() > canvas.winfo_height():
                scrollbar.pack(side="right", fill="y")
            else:
                scrollbar.pack_forget()

        def _on_canvas_configure(e):
            canvas.itemconfig(scroll_win, width=e.width)

        scroll_frame.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mousewheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        def _bind_scroll(widget):
            """Recursively bind mousewheel to all children so scroll works everywhere."""
            widget.bind("<MouseWheel>", _on_mousewheel)
            for child in widget.winfo_children():
                _bind_scroll(child)

        # Bind now and whenever new cards are added
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scroll_frame.bind("<MouseWheel>", _on_mousewheel)
        scroll_frame.bind("<Configure>", lambda e: (_on_frame_configure(e), _bind_scroll(scroll_frame)))

        # Canvas fills remaining space above the buttons
        canvas.pack(side="top", fill="both", expand=True)

        # INSTANCES label
        tk.Label(scroll_frame, text="INSTANCES", font=("Courier New", 8, "bold"),
                 fg=TEXTDIM, bg=BG, anchor="w").pack(fill="x", pady=(0, 6))

        self._cards = []
        for inst in self.instances:
            self._cards.append(self._make_card(scroll_frame, inst["name"], inst["port"]))

        tk.Frame(scroll_frame, bg=BG, height=12).pack()
        tk.Frame(scroll_frame, bg=BORDER, height=1).pack(fill="x")
        tk.Frame(scroll_frame, bg=BG, height=12).pack()

        tk.Label(scroll_frame, text="SESSION", font=("Courier New", 8, "bold"),
                 fg=TEXTDIM, bg=BG, anchor="w").pack(fill="x", pady=(0, 6))

        self._checks_v   = tk.StringVar(value="0")
        self._uptime_v   = tk.StringVar(value="00:00:00")
        self._restarts_v = tk.StringVar(value="0")
        self._make_stat(scroll_frame, "Checks",   self._checks_v)
        self._make_stat(scroll_frame, "Uptime",   self._uptime_v)
        self._make_stat(scroll_frame, "Restarts", self._restarts_v)

        # ── Fixed buttons at bottom — packed BEFORE canvas so they reserve space
        btn_frame = tk.Frame(left_outer, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(6, 0))

        self._start_btn = tk.Button(btn_frame, text="▶  START", font=("Courier New", 11, "bold"),
                                     fg=BG, bg=GREEN, activebackground="#00cc6a", activeforeground=BG,
                                     relief="flat", cursor="hand2", bd=0, padx=10, pady=10,
                                     command=self.start_monitor)
        self._start_btn.pack(fill="x", pady=(0, 6))

        self._stop_btn = tk.Button(btn_frame, text="■  STOP", font=("Courier New", 11, "bold"),
                                    fg=BG, bg=TEXTDIM, activebackground=RED, activeforeground=BG,
                                    relief="flat", cursor="hand2", bd=0, padx=10, pady=10,
                                    state="disabled", command=self.stop_monitor)
        self._stop_btn.pack(fill="x")

        tk.Frame(left_outer, bg=BORDER, height=1).pack(side="bottom", fill="x")

        # Right panel
        right = tk.Frame(content, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="LIVE LOG", font=("Courier New", 8, "bold"),
                 fg=TEXTDIM, bg=BG, anchor="w").pack(fill="x", pady=(0, 6))

        lf = tk.Frame(right, bg=BORDER, bd=1, relief="flat")
        lf.pack(fill="both", expand=True)

        self._log_box = scrolledtext.ScrolledText(
            lf, font=("Courier New", 9), bg=BG2, fg=TEXT,
            insertbackground=ACCENT, relief="flat", bd=0,
            padx=10, pady=10, state="disabled", wrap="word", selectbackground=BG3)
        self._log_box.pack(fill="both", expand=True)

        for tag, col in [("ok", GREEN), ("fail", RED), ("warn", YELLOW),
                          ("info", ACCENT), ("dim", TEXTDIM), ("normal", TEXT)]:
            self._log_box.tag_config(tag, foreground=col)

        tk.Button(right, text="Clear log", font=("Courier New", 8),
                  fg=TEXTDIM, bg=BG, relief="flat", cursor="hand2", bd=0, pady=3,
                  command=self._clear_log).pack(anchor="e", pady=(4, 0))

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")
        self._status = tk.Label(self.root, text="● IDLE", font=("Courier New", 8),
                                 fg=TEXTDIM, bg=BG2, anchor="w", padx=14, pady=5)
        self._status.pack(fill="x")

    def _make_card(self, parent, name, port):
        f = tk.Frame(parent, bg=BG3, pady=8, padx=10)
        f.pack(fill="x", pady=(0, 8))

        # Top row: dot + name + status
        top = tk.Frame(f, bg=BG3)
        top.pack(fill="x")
        dot = tk.Label(top, text="●", font=("Courier New", 10), fg=TEXTDIM, bg=BG3)
        dot.pack(side="left")
        tk.Label(top, text=f"  {name}", font=("Courier New", 9, "bold"), fg=TEXT, bg=BG3).pack(side="left")
        st = tk.Label(top, text="IDLE", font=("Courier New", 8, "bold"), fg=TEXTDIM, bg=BG3)
        st.pack(side="right")

        # Port + PID row
        info = tk.Frame(f, bg=BG3)
        info.pack(fill="x", pady=(2, 0))
        tk.Label(info, text=f"port {port}", font=("Courier New", 7), fg=TEXTDIM, bg=BG3).pack(side="left")
        pid = tk.Label(info, text="  PID: —", font=("Courier New", 7), fg=TEXTDIM, bg=BG3)
        pid.pack(side="left")

        # Power buttons row
        btn_row = tk.Frame(f, bg=BG3)
        btn_row.pack(fill="x", pady=(6, 0))

        # Find the instance dict from self.instances by port
        inst = next((i for i in self.instances if i["port"] == port), None)

        def _power_on(i=inst):
            if i is None: return
            threading.Thread(target=self._manual_launch, args=(i,), daemon=True).start()

        def _power_off(i=inst):
            if i is None: return
            threading.Thread(target=self._manual_shutdown, args=(i,), daemon=True).start()

        on_btn = tk.Button(btn_row, text="▶ ON",
                           font=("Courier New", 7, "bold"),
                           fg=BG, bg="#1a6640",
                           activebackground=GREEN, activeforeground=BG,
                           relief="flat", cursor="hand2", bd=0, padx=6, pady=3,
                           command=_power_on)
        on_btn.pack(side="left", padx=(0, 4))

        off_btn = tk.Button(btn_row, text="■ OFF",
                            font=("Courier New", 7, "bold"),
                            fg=BG, bg="#6b1a2a",
                            activebackground=RED, activeforeground=BG,
                            relief="flat", cursor="hand2", bd=0, padx=6, pady=3,
                            command=_power_off)
        off_btn.pack(side="left")

        return {"dot": dot, "status": st, "pid": pid, "on_btn": on_btn, "off_btn": off_btn}

    def _manual_launch(self, inst):
        """Manually boot an instance + launch Roblox."""
        name, idx, port = inst["name"], inst["index"], inst["port"]
        self._log(f"[MANUAL] Launching {name}...", YELLOW)
        self._set_status(f"● LAUNCHING {name.upper()}...", YELLOW)
        self._mumu("control", "launch", "-v", str(idx))
        self._log(f"  Waiting for {name} to boot...", YELLOW)
        if not self._wait_mumu(idx, timeout=60):
            self._log(f"  [WARN] {name} slow to start.", YELLOW)
        self._sleep(3)
        self._adb("start-server")
        if not self._wait_adb(port, timeout=60):
            self._log(f"  [WARN] ADB offline for {name}.", YELLOW)
            self._set_status("● IDLE", TEXTDIM)
            return
        self._wait_network(port, timeout=20)
        self._launch_roblox(inst)
        self._sleep(8)
        alive, pid = self._is_alive(inst)
        card_idx = next((i for i, inst2 in enumerate(self.instances) if inst2["port"] == port), None)
        # Re-enable monitoring for this instance
        self._disabled.discard(port)
        if alive and card_idx is not None:
            self._set_card(card_idx, "OK", pid)
            self._log(f"  [OK] {name} launched (PID {pid}) — monitoring resumed.", GREEN)
        else:
            self._log(f"  [WARN] {name} launched but Roblox not detected.", YELLOW)
        self._set_status("● IDLE" if not self.running else "● MONITORING", GREEN if self.running else TEXTDIM)

    def _manual_shutdown(self, inst):
        """Manually shut down an instance and disable monitoring for it."""
        name, idx, port = inst["name"], inst["index"], inst["port"]
        self._log(f"[MANUAL] Shutting down {name}...", YELLOW)
        # Force stop Roblox first
        result = self._mumu("api", "-v", str(idx), "shell", "am", "force-stop", "com.roblox.client")
        if result is False:
            self._log(f"  [WARN] Failed to force-stop Roblox on {name}", YELLOW)
        self._sleep(1)
        # Disconnect ADB
        self._adb("disconnect", f"127.0.0.1:{port}")
        # Shut down the instance
        result = self._mumu("control", "shutdown", "-v", str(idx))
        if result is False:
            self._log(f"  [WARN] Shutdown command failed for {name}", YELLOW)
            return  # Don't disable if shutdown failed
        self._log(f"  Shutdown command succeeded for {name}", GREEN)
        # Wait for process to die
        initial_count = self._mumu_count()
        self._log(f"  Initial MuMu process count: {initial_count}", TEXTDIM)
        for _ in range(20):
            if self._stop.is_set(): return
            current_count = self._mumu_count()
            if current_count <= idx:
                self._log(f"  MuMu process count dropped to {current_count}, instance shut down", GREEN)
                break
            self._sleep(1)
        else:
            self._log(f"  [WARN] MuMu process count still {self._mumu_count()} after 20s, shutdown may have failed", YELLOW)
        self._sleep(2)
        self._adb("disconnect", f"127.0.0.1:{port}")
        # Mark as disabled — monitor will skip this instance
        self._disabled.add(port)
        card_idx = next((i for i, inst2 in enumerate(self.instances) if inst2["port"] == port), None)
        if card_idx is not None:
            def _mark_disabled(ci=card_idx, n=name):
                card = self._cards[ci]
                card["dot"].config(fg=TEXTDIM)
                card["status"].config(text="DISABLED", fg=TEXTDIM)
                card["pid"].config(text="PID: —")
            self._ui(_mark_disabled)
        self._log(f"  [OK] {name} shut down — monitoring paused.", YELLOW)

    def _make_stat(self, parent, label, var):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Courier New", 8), fg=TEXTDIM, bg=BG,
                 anchor="w", width=9).pack(side="left")
        tk.Label(row, textvariable=var, font=("Courier New", 8, "bold"), fg=TEXT, bg=BG).pack(side="left")

    # ── Thread-safe UI updates (batched) ───────────────────────────────────────
    def _ui(self, fn):
        """Schedule fn on main thread."""
        self.root.after(0, fn)

    def _set_card(self, idx, status, pid="—"):
        def _apply():
            c = self._cards[idx]
            if status == "OK":
                c["dot"].config(fg=GREEN)
                c["status"].config(text="RUNNING", fg=GREEN)
            elif status == "FAIL":
                c["dot"].config(fg=RED)
                c["status"].config(text="STOPPED", fg=RED)
            else:
                c["dot"].config(fg=TEXTDIM)
                c["status"].config(text="IDLE", fg=TEXTDIM)
            c["pid"].config(text=f"PID: {pid}")
        self._ui(_apply)

    def _log(self, msg, color=TEXT):
        def _write():
            self._log_box.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_box.insert("end", f"[{ts}] ", "dim")
            tag = {GREEN: "ok", RED: "fail", YELLOW: "warn", ACCENT: "info"}.get(color, "normal")
            self._log_box.insert("end", msg + "\n", tag)
            self._log_box.config(state="disabled")
            self._log_box.see("end")
        self._ui(_write)

    def _clear_log(self):
        self._log_box.config(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.config(state="disabled")

    def _set_status(self, text, color=TEXTDIM):
        self._ui(lambda: self._status.config(text=text, fg=color))

    def _flog(self, msg, path=None):
        target = path or LOG_FILE
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

    # ── Process helpers ────────────────────────────────────────────────────────
    def _run(self, cmd, capture=False):
        """Run a subprocess. Returns stdout string if capture=True."""
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return "" if capture else False  # Return False on failure
            # Check for JSON error response from MuMu
            if r.stdout and r.stdout.strip().startswith('{'):
                try:
                    import json
                    data = json.loads(r.stdout.strip())
                    if data.get('errcode') != 0:
                        return "" if capture else False
                except:
                    pass
            return r.stdout.strip() if capture else True  # Return True on success
        except Exception as exc:
            return "" if capture else False

    def _adb(self, *args, capture=False):
        return self._run([self._adb_exe, *args], capture=capture)

    def _adb_s(self, port, *args, capture=False):
        """ADB with -s serial."""
        return self._run([self._adb_exe, "-s", f"127.0.0.1:{port}", *args], capture=capture)

    def _mumu(self, *args, capture=False):
        return self._run([self._mumu_exe, *args], capture=capture)

    def _sleep(self, seconds):
        """Interruptible sleep — breaks early if stop event is set."""
        self._stop.wait(timeout=seconds)

    # ── Health check — OPTIMIZED ───────────────────────────────────────────────
    def _mumu_count(self):
        try:
            r = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq MuMuVMMHeadless.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5)
            return r.stdout.count("MuMuVMMHeadless.exe")
        except Exception:
            return 99  # assume alive on error

    def _is_alive(self, inst):
        """
        Fast 3-step check (no dumpsys activity top — too slow):
        1. Windows process count
        2. ADB device online (single connect attempt, cached result)
        3. pidof com.roblox.client
        Returns (alive: bool, pid: str)
        """
        port  = inst["port"]
        index = inst["index"]
        serial = f"127.0.0.1:{port}"

        # Ensure ADB server is running before checking device status.
        self._adb("start-server")
        self._sleep(1)

        # 1. MuMu process alive?
        if self._mumu_count() <= index:
            self._log(f"    [DBG:{port}] DEAD — MuMu process gone", TEXTDIM)
            return False, ""

        # 2. ADB online? — try up to 3 connects before declaring dead
        adb_ok = False
        for _ in range(3):
            self._adb("disconnect", serial)
            self._sleep(0.5)
            self._adb("connect", serial)
            self._sleep(1)
            devices = self._adb("devices", capture=True) or ""
            line = next((l for l in devices.splitlines() if serial in l), "")
            if line and "offline" not in line and "unauthorized" not in line:
                adb_ok = True
                break
            if line:
                self._log(f"    [DBG:{port}] ADB status line: {line}", TEXTDIM)
        if not adb_ok:
            self._log(f"    [DBG:{port}] DEAD — ADB offline", TEXTDIM)
            return False, ""

        # 3. Roblox process
        pid = self._adb_s(port, "shell", "pidof", "com.roblox.client", capture=True)
        if not pid:
            self._log(f"    [DBG:{port}] DEAD — no roblox pid", TEXTDIM)
            return False, ""

        pid = pid.split()[0]

        # 4. ANR check (fast grep on processes dump)
        anr = self._adb_s(port, "shell",
                          "dumpsys activity processes 2>/dev/null | grep -c 'not responding'",
                          capture=True)
        if anr and anr.strip() != "0":
            self._log(f"    [DBG:{port}] DEAD — ANR detected", TEXTDIM)
            self._adb_s(port, "shell", "am", "kill", "com.roblox.client")
            return False, ""

        self._log(f"    [DBG:{port}] ALIVE pid={pid}", TEXTDIM)
        return True, pid

    # ── Recovery ───────────────────────────────────────────────────────────────
    def _wait_mumu(self, index, timeout=60):
        """Wait for MuMu instance to appear in tasklist."""
        for _ in range(timeout):
            if self._stop.is_set(): return False
            if self._mumu_count() > index:
                return True
            self._sleep(1)
        return False

    def _wait_adb(self, port, timeout=60):
        """Retry adb connect until online."""
        serial = f"127.0.0.1:{port}"
        for _ in range(timeout // 3):
            if self._stop.is_set(): return False
            self._adb("disconnect", serial)
            self._sleep(0.5)
            self._adb("connect", serial)
            self._sleep(3)
            devices = self._adb("devices", capture=True) or ""
            line = next((l for l in devices.splitlines() if serial in l), "")
            if line and "offline" not in line and "unauthorized" not in line:
                return True
        return False

    def _wait_network(self, port, timeout=30):
        """Ping 8.8.8.8 until network is up."""
        for _ in range(timeout):
            if self._stop.is_set(): return
            ping = self._adb_s(port, "shell",
                               "ping -c 1 -W 1 8.8.8.8 2>/dev/null | grep -c '1 received'",
                               capture=True)
            if ping and ping.strip() != "0":
                return
            self._sleep(1)

    def _launch_roblox(self, inst):
        """Launch Roblox and join game."""
        port = inst["port"]
        idx  = inst["index"]
        # First close any existing Roblox
        result = self._mumu("control", "app", "close", "--package", "com.roblox.client", "-v", str(idx))
        self._sleep(2)
        # Launch Roblox app
        result = self._mumu("control", "app", "launch", "--package", "com.roblox.client", "-v", str(idx))
        if result is False:
            self._log(f"  [WARN] Failed to launch Roblox on instance {idx}", YELLOW)
            return
        self._sleep(5)  # Wait for app to open
        # Join the specific game
        game_url = f"roblox://placeId={PLACE_ID}"
        adb_result = self._adb_s(port, "shell", f'am start -a android.intent.action.VIEW -d "{game_url}"')
        if adb_result is False:
            self._log(f"  [WARN] Failed to join game on instance {idx}", YELLOW)
        self._sleep(3)

    def _recover(self, inst, card_idx):
        name, idx, port = inst["name"], inst["index"], inst["port"]
        self._set_status(f"● RESTARTING {name.upper()}...", YELLOW)

        self._log(f"  [1/5] Killing Roblox on {name}...", YELLOW)
        self._mumu("api", "-v", str(idx), "shell", "am", "force-stop", "com.roblox.client")
        self._sleep(1)

        self._log(f"  [2/5] Closing {name}...", YELLOW)
        self._mumu("control", "shutdown", "-v", str(idx))

        # Wait for process to die
        for _ in range(20):
            if self._stop.is_set(): return
            if self._mumu_count() <= idx:
                break
            self._sleep(1)
        self._sleep(2)

        self._log(f"  [3/5] Launching {name}...", YELLOW)
        self._adb("disconnect", f"127.0.0.1:{port}")
        self._mumu("control", "launch", "-v", str(idx))

        self._log(f"  [4/5] Waiting for Android + ADB...", YELLOW)
        if not self._wait_mumu(idx, timeout=60):
            self._log(f"  [WARN] {name} slow to start, continuing...", YELLOW)
        self._sleep(3)

        self._adb("start-server")
        if not self._wait_adb(port, timeout=60):
            self._log(f"  [WARN] ADB offline after 60s, retry next check.", YELLOW)
            self._set_status("● MONITORING (degraded)", YELLOW)
            return

        self._log(f"  [5/5] Launching Roblox on {name}...", YELLOW)
        self._wait_network(port, timeout=20)
        self._launch_roblox(inst)

        self._sleep(10)
        alive, pid = self._is_alive(inst)
        if alive:
            self._log(f"  [OK] {name} recovered (PID {pid})", GREEN)
            self._set_card(card_idx, "OK", pid)
            self._set_status("● MONITORING", GREEN)
            self.restarts += 1
            self._ui(lambda v=self.restarts: self._restarts_v.set(str(v)))
            self._flog(f"RECOVERED: {name}")
        else:
            self._log(f"  [WARN] {name} still not responding, retry next check.", YELLOW)
            self._set_status("● MONITORING (degraded)", YELLOW)

    # ── AFK ────────────────────────────────────────────────────────────────────
    def _set_startup(self, enable):
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, "RobloxGuardian", 0, winreg.REG_SZ,
                                  f'pythonw "{Path(__file__).resolve()}"')
            else:
                try: winreg.DeleteValue(key, "RobloxGuardian")
                except FileNotFoundError: pass
            winreg.CloseKey(key)
        except Exception as e:
            self._log(f"Startup registry: {e}", RED)

    def _toggle_afk(self):
        self.afk_on = not self.afk_on
        if self.afk_on:
            AFK_FILE.write_text("1")
            self._afk_btn.config(text="💤 AFK ON", fg=BG, bg=YELLOW)
            self._log("AFK ON — restart every 2h.", YELLOW)
            self._set_startup(True)
            self._schedule_afk()
        else:
            if AFK_FILE.exists(): AFK_FILE.unlink()
            self._afk_btn.config(text="💤 AFK", fg=TEXTDIM, bg=BG2)
            self._log("AFK OFF.", YELLOW)
            self._set_startup(False)
            if self._afk_timer:
                self._afk_timer.cancel()
                self._afk_timer = None

    def _schedule_afk(self):
        if self._afk_timer: self._afk_timer.cancel()
        self._afk_timer = threading.Timer(2 * 3600, self._do_afk_restart)
        self._afk_timer.start()
        self._log("AFK restart in 2h.", YELLOW)

    def _do_afk_restart(self):
        if not AFK_FILE.exists(): return
        self._flog("AFK: 2h restart triggered")
        subprocess.run(["shutdown", "/r", "/t", "10", "/c", "Roblox Guardian AFK restart"])

    # ── Settings ───────────────────────────────────────────────────────────────
    def _open_settings(self):
        if self.running:
            messagebox.showwarning("Monitor running", "Stop the monitor first.")
            return
        d = SetupDialog(self.root, existing=self.cfg)
        if d.result:
            save_config(d.result)
            self.cfg = d.result
            self._log("Settings saved. Restart to apply.", YELLOW)

    # ── Monitor ────────────────────────────────────────────────────────────────
    def _manual_launch(self, inst):
        """Manually launch a single instance + Roblox."""
        name, idx, port = inst["name"], inst["index"], inst["port"]
        self._log(f"[MANUAL] Launching {name}...", YELLOW)
        self._set_card(self.instances.index(inst), "IDLE")
        self._mumu("control", "launch", "-v", str(idx))
        # Wait for MuMu to appear
        for _ in range(60):
            if self._mumu_count() > idx:
                break
            self._sleep(1)
        self._sleep(3)
        self._adb("start-server")
        if not self._wait_adb(port, timeout=45):
            self._log(f"[MANUAL] ADB offline for {name}, aborting.", RED)
            return
        self._wait_network(port, timeout=20)
        self._launch_roblox(inst)
        self._sleep(8)
        alive, pid = self._is_alive(inst)
        if alive:
            self._log(f"[MANUAL] {name} launched (PID {pid})", GREEN)
            self._set_card(self.instances.index(inst), "OK", pid)
        else:
            self._log(f"[MANUAL] {name} failed to launch.", RED)
            self._set_card(self.instances.index(inst), "FAIL")

    def _manual_shutdown(self, inst):
        """Manually shut down a single instance."""
        name, idx = inst["name"], inst["index"]
        self._log(f"[MANUAL] Shutting down {name}...", YELLOW)
        self._mumu("api", "-v", str(idx), "shell", "am", "force-stop", "com.roblox.client")
        self._sleep(1)
        self._mumu("control", "shutdown", "-v", str(idx))
        # Wait for process to die
        for _ in range(15):
            if self._mumu_count() <= idx:
                break
            self._sleep(1)
        self._log(f"[MANUAL] {name} shut down.", YELLOW)
        self._set_card(self.instances.index(inst), "IDLE")
        card = self._cards[self.instances.index(inst)]
        self._ui(lambda c=card: c["pid"].config(text="PID: —"))

    def start_monitor(self):
        self._stop.clear()
        self.running  = True
        self.checks   = 0
        self.restarts = 0
        self.start_time = time.time()
        self._start_btn.config(state="disabled", bg=TEXTDIM, text="▶  RUNNING")
        self._stop_btn.config(state="normal", bg=RED)
        self._adb("start-server")
        self._sleep(1)
        for inst in self.instances:
            serial = f"127.0.0.1:{inst['port']}"
            self._adb("disconnect", serial)
            self._adb("connect", serial)
        self._sleep(2)
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        self._tick()

    def stop_monitor(self):
        self._stop.set()
        self.running = False
        self._set_status("● STOPPING...", YELLOW)
        self._log("Stopped by user.", YELLOW)
        self._start_btn.config(state="normal", bg=GREEN, text="▶  START")
        self._stop_btn.config(state="disabled", bg=TEXTDIM)
        for i in range(len(self.instances)):
            self._set_card(i, "IDLE")
        self._set_status("● IDLE", TEXTDIM)

    def _tick(self):
        if not self.running: return
        e = int(time.time() - self.start_time)
        h, r = divmod(e, 3600); m, s = divmod(r, 60)
        self._uptime_v.set(f"{h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._tick)

    def _worker(self):
        self._log("=== ROBLOX GUARDIAN STARTING ===", ACCENT)
        self._set_status("● CHECKING...", YELLOW)

        # Pre-check fast path — give ADB server time to start + connect all
        self._adb("start-server")
        self._sleep(3)
        for inst in self.instances:
            serial = f"127.0.0.1:{inst['port']}"
            self._adb("disconnect", serial)
            self._adb("connect", serial)
        self._sleep(3)  # wait for connections to stabilize

        all_up = True
        for i, inst in enumerate(self.instances):
            alive, pid = self._is_alive(inst)
            if alive:
                self._log(f"  [OK] {inst['name']} already running (PID {pid})", GREEN)
                self._set_card(i, "OK", pid)
            else:
                self._log(f"  {inst['name']} not ready.", TEXTDIM)
                all_up = False

        if all_up:
            self._log("All running — skipping boot sequence.", GREEN)
            self._flog("Monitor started (fast path)")
        else:
            self._log("Running full boot sequence...", YELLOW)
            self._log("⚠️  PLEASE WAIT — This takes 90+ seconds. Do NOT stop the script!", YELLOW)
            self._stop_btn.config(state="disabled")  # Disable stop button during boot

            # ADB restart
            self._log("[1/5] Restarting ADB...", ACCENT)
            self._adb("kill-server")
            self._sleep(1)
            result = self._adb("start-server")
            if result is False:
                self._log("  [WARN] ADB start-server command failed.", YELLOW)
            self._sleep(3)

            # Clean ADB keys
            self._log("[2/5] Cleaning ADB keys...", ACCENT)
            android_dir = Path(os.environ.get("USERPROFILE", "~")) / ".android"
            for fname in ("adbkey", "adbkey.pub"):
                p = android_dir / fname
                try: p.unlink()
                except Exception: pass
            self._sleep(5)

            if self._stop.is_set(): 
                self._stop_btn.config(state="normal", bg=RED)
                return

            # Launch instances
            self._log("[3/5] Launching MuMu instances...", ACCENT)
            for inst in self.instances:
                self._log(f"  Starting {inst['name']}...")
                result = self._mumu("control", "launch", "-v", str(inst["index"]))
                if result is False:
                    self._log(f"  [WARN] MuMu launch command failed for {inst['name']}.", YELLOW)
                self._sleep(1)

            # Wait for boot
            self._log("[4/5] Waiting 60s for instances to boot...", ACCENT)
            self._sleep(60)
            if self._stop.is_set(): 
                self._stop_btn.config(state="normal", bg=RED)
                return

            # Connect ADB + launch Roblox
            self._log("[5/5] Connecting ADB & launching Roblox...", ACCENT)
            for inst in self.instances:
                if self._stop.is_set(): 
                    self._stop_btn.config(state="normal", bg=RED)
                    return
                port = inst["port"]
                self._log(f"  Connecting {inst['name']}...")
                self._adb("connect", f"127.0.0.1:{port}")
                self._sleep(2)
                self._log(f"  Waiting for network on {inst['name']}...")
                self._wait_network(port, timeout=20)
                self._launch_roblox(inst)

            self._flog("Monitor started (full boot)")
            self._stop_btn.config(state="normal", bg=RED)  # Re-enable stop button

        self._log("=== MONITORING ACTIVE ===", GREEN)
        self._set_status("● MONITORING", GREEN)

        # First check delay
        self._log("Waiting 30s before first check...", YELLOW)
        self._sleep(30)

        # Monitor loop
        while not self._stop.is_set():
            self.checks += 1
            c = self.checks
            self._ui(lambda v=c: self._checks_v.set(str(v)))
            self._log(f"── Check #{self.checks} ──────────────")

            # Reconnect all (cheap, just ensures connection)
            for inst in self.instances:
                self._adb("connect", f"127.0.0.1:{inst['port']}")
            self._sleep(1)

            recovered = False
            for i, inst in enumerate(self.instances):
                if self._stop.is_set(): break
                # Skip instances manually disabled by user
                if inst["port"] in self._disabled:
                    self._log(f"  [SKIP] {inst['name']} disabled by user.", TEXTDIM)
                    continue
                alive, pid = self._is_alive(inst)
                if not alive:
                    self._log(f"  [FAIL] {inst['name']} NOT running!", RED)
                    self._flog(f"ERROR: {inst['name']} not running", ERROR_LOG)
                    self._set_card(i, "FAIL")
                    self._manual_shutdown(inst)
                self._log(f"  [OK] {inst['name']} (PID {pid})", GREEN)
                self._set_card(i, "OK", pid)

            if not recovered:
                self._log(f"  All {len(self.instances)} OK. Next check in {CHECK_INTERVAL}s.", GREEN)

            self._sleep(CHECK_INTERVAL)

        self._log("Monitor stopped.", YELLOW)
        self._flog("Monitor stopped by user")


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()
    root.withdraw()
    root.configure(bg=BG)

    cfg = load_config()
    if cfg:
        cfg = validate_config_paths(cfg)
    if not cfg:
        d = SetupDialog(root)
        if not d.result:
            root.destroy()
            return
        save_config(d.result)
        cfg = d.result

    picker = InstancePicker(root)
    instances = picker.result or build_instances(cfg)[:1]

    root.deiconify()
    try: root.iconbitmap(default="")
    except Exception: pass

    app = RobloxGuardianApp(root, instances, cfg)

    def on_close():
        if app._afk_timer: app._afk_timer.cancel()
        if app.running:
            app._stop.set()
            app.running = False
            if app._thread and app._thread.is_alive():
                app._thread.join(timeout=2)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()