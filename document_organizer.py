"""
Personal Documental Organizer - Python (Tkinter) DESKTOP version
Run:  python document_organizer.py
Data is saved in a SQLite database (documents.db) next to this file.
"""
import calendar
import os
import sqlite3
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents.db")
TODAY = date.today()

# ---------- colours ----------
P, P2, DARK = "#7c3aed", "#5b4fe0", "#4c1d95"
INK, MUT, LINE = "#1f1b2e", "#6b6880", "#d8d4e6"
RED, BG = "#d33333", "#ffffff"
PAGE, LAV = "#f6f4fb", "#ece6fa"

SEED = [
    {"name": "Aadhaar Card", "num": "ID:XXXX XXXX X882", "cat": "Id", "exp": None, "icon": "🪪"},
    {"name": "Vehicle Insurance", "num": "Policy No:V33r16m8", "cat": "Vehicle", "exp": "2026-10-25", "icon": "🚗"},
    {"name": "Passport", "num": "No:P1234567", "cat": "Id", "exp": "2030-02-12", "icon": "🛂"},
    {"name": "College ID", "num": "ID:C69101102", "cat": "Education", "exp": "2029-07-23", "icon": "🎓"},
    {"name": "Medical Insurance", "num": "Policy No:M2211", "cat": "Insurance", "exp": "2026-12-15", "icon": "🏥"},
    {"name": "College Certificate", "num": "CC-4471", "cat": "Education", "exp": "2027-10-15", "icon": "📜"},
]


# ---------- data helpers ----------
def _conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the table and add the sample documents on first run."""
    conn = _conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS documents (
               id       INTEGER PRIMARY KEY AUTOINCREMENT,
               name     TEXT NOT NULL,
               num      TEXT NOT NULL,
               cat      TEXT NOT NULL,
               exp      TEXT,
               icon     TEXT DEFAULT '📄',
               issue    TEXT,
               file     TEXT,
               reminder TEXT
           )"""
    )
    if conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO documents (name, num, cat, exp, icon) VALUES (?, ?, ?, ?, ?)",
            [(d["name"], d["num"], d["cat"], d["exp"], d["icon"]) for d in reversed(SEED)],
        )
    conn.commit()
    conn.close()


def load_docs():
    init_db()
    conn = _conn()
    rows = conn.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_doc(doc):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO documents (name, num, cat, exp, icon, issue, file, reminder) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc["name"], doc["num"], doc["cat"], doc["exp"], doc["icon"],
         doc.get("issue"), doc.get("file"), doc.get("reminder")),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def remove_doc(doc_id):
    conn = _conn()
    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()


def days_left(doc):
    if not doc["exp"]:
        return None
    return (date.fromisoformat(doc["exp"]) - TODAY).days


def fmt(s):
    if not s:
        return "No Expiry"
    d = date.fromisoformat(s)
    return f"{d.day} {d.strftime('%b %Y')}"


# ---------- small widgets ----------
class Btn(tk.Label):
    """Label-based button (looks the same on Windows / macOS / Linux)."""

    def __init__(self, parent, text, command=None, bg=P2, fg="white",
                 font=("Segoe UI", 11, "bold"), border=None, **kw):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, cursor="hand2",
                         pady=kw.pop("pady", 10), **kw)
        if border:
            self.config(highlightbackground=border, highlightthickness=1)
        self._cmd = command
        self.bind("<Button-1>", lambda e: self._cmd() if self._cmd else None)


class Entry(tk.Entry):
    """Entry with placeholder text."""

    def __init__(self, parent, placeholder="", password=False, **kw):
        super().__init__(parent, relief="flat", font=("Segoe UI", 11), bg="white",
                         highlightthickness=1, highlightbackground=LINE,
                         highlightcolor=P, **kw)
        self.placeholder, self.password, self._empty = placeholder, password, False
        self.bind("<FocusIn>", self._in)
        self.bind("<FocusOut>", self._out)
        self._out()

    def _in(self, _=None):
        if self._empty:
            self.delete(0, "end")
            self.config(fg=INK, show="•" if self.password else "")
            self._empty = False

    def _out(self, _=None):
        if not super().get():
            self._empty = True
            self.config(fg=MUT, show="")
            self.insert(0, self.placeholder)

    def get(self):
        return "" if self._empty else super().get()

    def set(self, text):
        self._in()
        self.delete(0, "end")
        self.insert(0, text)
        self._empty = False
        self.config(fg=INK, show="•" if self.password else "")

    def clear(self):
        self.delete(0, "end")
        self._empty = False
        self._out()


class Scroll(tk.Frame):
    """Vertically scrollable frame; put widgets in .inner"""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.canvas.pack(fill="both", expand=True)
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(win, width=e.width))
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")


# ---------- main app (desktop layout: sidebar + full-width pages) ----------
class App(tk.Tk):
    NAV = [("home", "🏠", "Home"), ("docs", "📄", "My Documents"), ("calendar", "🔔", "Calendar"),
           ("add", "＋", "Add Document"), ("profile", "👤", "Profile")]
    AUTH = ("splash", "login", "signup")
    CATS = [("Id", "🪪", "Identity", P, "white"), ("Education", "🎓", "Education", P2, "white"),
            ("Vehicle", "🚗", "Vehicle", "#ffd5d5", "#a33"), ("Finance", "🏛️", "Finance", "#6f9bff", "white"),
            ("Insurance", "🛡️", "Insurance", "#bdbdc7", "#333"), ("Others", "▦", "Others", "#e3d0ff", "#5b2da8")]

    def __init__(self):
        super().__init__()
        self.title("Personal Documental Organizer")
        self.configure(bg=PAGE)
        self.minsize(900, 600)
        try:
            self.state("zoomed")              # Windows / macOS: start maximized
        except tk.TclError:
            self.attributes("-zoomed", True)  # Linux
        self.fullscreen = False
        self.bind("<F11>", lambda e: self.set_fullscreen(not self.fullscreen))
        self.bind("<Escape>", lambda e: self.set_fullscreen(False))
        self.docs = load_docs()
        self.filter = "All"
        self.file_path = None
        self.cal_y, self.cal_m = TODAY.year, TODAY.month
        self.screens = {}

        # --- login / splash area (full window) ---
        self.auth = tk.Frame(self, bg=LAV)
        self.auth.place(relx=0, rely=0, relwidth=1, relheight=1)

        # --- main app area: sidebar + content ---
        self.shell = tk.Frame(self, bg=PAGE)
        self.shell.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.content = tk.Frame(self.shell, bg=PAGE)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        for name in self.AUTH:
            fr = tk.Frame(self.auth, bg=LAV)
            fr.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.screens[name] = fr
            getattr(self, f"build_{name}")(fr)
        for name, _, _ in self.NAV:
            fr = tk.Frame(self.content, bg=PAGE)
            fr.grid(row=0, column=0, sticky="nsew")
            self.screens[name] = fr
            getattr(self, f"build_{name}")(fr)
        self.go("splash")

    # ----- window / fullscreen -----
    def set_fullscreen(self, on):
        self.fullscreen = on
        self.attributes("-fullscreen", on)

    # ----- sidebar -----
    def build_sidebar(self):
        sb = tk.Frame(self.shell, bg=DARK, width=250)
        sb.grid(row=0, column=0, sticky="ns")
        sb.grid_propagate(False)
        sb.pack_propagate(False)
        tk.Label(sb, text="📁", font=("Segoe UI Emoji", 28), bg=DARK, fg="white").pack(pady=(28, 0))
        tk.Label(sb, text="Personal\nDocumental Organizer", font=("Segoe UI", 12, "bold"),
                 bg=DARK, fg="white").pack(pady=(4, 24))
        self.nav_btns = {}
        for name, icon, label in self.NAV:
            b = tk.Label(sb, text=f"  {icon}   {label}", anchor="w", font=("Segoe UI", 11),
                         bg=DARK, fg="white", cursor="hand2", padx=18, pady=12)
            b.pack(fill="x", padx=12, pady=2)
            b.bind("<Button-1>", lambda e, n=name: self.go(n))
            b.bind("<Enter>", lambda e, n=name: self.nav_btns[n].config(bg=P2) if self.cur != n else None)
            b.bind("<Leave>", lambda e, n=name: self.nav_btns[n].config(bg=DARK) if self.cur != n else None)
            self.nav_btns[name] = b
        out = tk.Label(sb, text="  ⏻   Log out", anchor="w", font=("Segoe UI", 11), bg=DARK, fg="#ffb3b3",
                       cursor="hand2", padx=18, pady=12)
        out.pack(side="bottom", fill="x", padx=12, pady=20)
        out.bind("<Button-1>", lambda e: self.go("login"))
        self.cur = None

    # ----- navigation -----
    def go(self, name):
        self.cur = name
        if name in self.AUTH:
            self.auth.tkraise()
        else:
            self.shell.tkraise()
            for n, b in self.nav_btns.items():
                b.config(bg=P if n == name else DARK)
        self.screens[name].tkraise()
        if name == "home":
            self.render_home()
        elif name == "docs":
            self.render_docs()
        elif name == "calendar":
            self.render_calendar()

    # ----- helpers -----
    def page(self, f, title, subtitle=""):
        """Standard page: title row on top, returns (body_frame, header_right_frame)."""
        outer = tk.Frame(f, bg=PAGE)
        outer.pack(fill="both", expand=True, padx=36, pady=28)
        h = tk.Frame(outer, bg=PAGE)
        h.pack(fill="x", pady=(0, 18))
        t = tk.Frame(h, bg=PAGE)
        t.pack(side="left")
        tk.Label(t, text=title, font=("Segoe UI", 22, "bold"), fg=P, bg=PAGE).pack(anchor="w")
        if subtitle:
            tk.Label(t, text=subtitle, font=("Segoe UI", 10), fg=MUT, bg=PAGE).pack(anchor="w")
        right = tk.Frame(h, bg=PAGE)
        right.pack(side="right")
        body = tk.Frame(outer, bg=PAGE)
        body.pack(fill="both", expand=True)
        return body, right

    def card(self, parent, bg=BG, **kw):
        return tk.Frame(parent, bg=bg, highlightbackground=LINE, highlightthickness=1, **kw)

    def auth_card(self, f, width=440):
        c = self.card(f)
        c.place(relx=0.5, rely=0.5, anchor="center", width=width)
        inner = tk.Frame(c, bg=BG)
        inner.pack(fill="both", expand=True, padx=36, pady=30)
        return inner

    # ----- 1 splash -----
    def build_splash(self, f):
        f.configure(bg="#c77dff")
        c = tk.Frame(f, bg="#c77dff")
        c.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(c, text="📁", font=("Segoe UI Emoji", 54), bg="#c77dff").pack()
        tk.Label(c, text="Personal Documental Organizer", font=("Segoe UI", 30, "bold"),
                 bg="#c77dff", fg="#2b1650").pack(pady=(6, 0))
        tk.Label(c, text="Keep your important documents safe, organized and always on time",
                 bg="#c77dff", fg="#2b1650", font=("Segoe UI", 13)).pack(pady=12)
        tk.Label(c, text="📄", font=("Segoe UI Emoji", 80), bg="#c77dff").pack(pady=10)
        Btn(c, "Get Started", lambda: self.go("signup"), width=28).pack(pady=6)
        Btn(c, "I Already Have an Account", lambda: self.go("login"), bg="#d9a8ff", fg="#2b1650",
            width=28).pack()

    # ----- 2 login -----
    def build_login(self, f):
        f = self.auth_card(f)
        tk.Label(f, text="📁", font=("Segoe UI Emoji", 36), bg=BG).pack()
        tk.Label(f, text="Personal Documental Organizer", font=("Segoe UI", 15, "bold"), bg=BG, fg=P).pack()
        tk.Label(f, text="Login to continue", bg=BG, fg=MUT).pack(pady=(4, 18))
        self.login_user = Entry(f, "Email or Phone Number")
        self.login_user.pack(fill="x", ipady=8, pady=5)
        self.login_pass = Entry(f, "Password", password=True)
        self.login_pass.pack(fill="x", ipady=8, pady=5)
        row = tk.Frame(f, bg=BG)
        row.pack(fill="x")
        tk.Checkbutton(row, text="Remember me", bg=BG, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(row, text="Forget Password?", fg=P, bg=BG, font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="right")
        Btn(f, "Login", self.do_login).pack(fill="x", pady=12)
        tk.Label(f, text="OR", bg=BG, fg=MUT, font=("Segoe UI", 9)).pack()
        Btn(f, "G   Continue with Google", bg="white", fg=INK, border=LINE).pack(fill="x", pady=4)
        Btn(f, "   Continue with Apple", bg="white", fg=INK, border=LINE).pack(fill="x", pady=4)
        r = tk.Frame(f, bg=BG)
        r.pack(pady=10)
        tk.Label(r, text="Don't have an account? ", bg=BG, font=("Segoe UI", 9)).pack(side="left")
        l = tk.Label(r, text="Sign Up", fg=P, bg=BG, font=("Segoe UI", 9, "bold"), cursor="hand2")
        l.pack(side="left")
        l.bind("<Button-1>", lambda e: self.go("signup"))
        self.login_pass.bind("<Return>", lambda e: self.do_login())

    def do_login(self):
        if not self.login_user.get() or not self.login_pass.get():
            return messagebox.showwarning("Login", "Please fill in both fields.")
        self.go("home")

    # ----- 3 sign up -----
    def build_signup(self, f):
        f = self.auth_card(f)
        tk.Label(f, text="Create Your Account", font=("Segoe UI", 16, "bold"), bg=BG, fg=P).pack()
        tk.Label(f, text="Start organizing your documents today", bg=BG, fg=MUT).pack(pady=(4, 16))
        self.su_name = Entry(f, "Full Name")
        self.su_mail = Entry(f, "Email or Phone Number")
        self.su_p1 = Entry(f, "Password (min 6 characters)", password=True)
        self.su_p2 = Entry(f, "Confirm Password", password=True)
        for e in (self.su_name, self.su_mail, self.su_p1, self.su_p2):
            e.pack(fill="x", ipady=8, pady=5)
        Btn(f, "Sign Up", self.do_signup).pack(fill="x", pady=14)
        r = tk.Frame(f, bg=BG)
        r.pack()
        tk.Label(r, text="Already have an account? ", bg=BG, font=("Segoe UI", 9)).pack(side="left")
        l = tk.Label(r, text="Login", fg=P, bg=BG, font=("Segoe UI", 9, "bold"), cursor="hand2")
        l.pack(side="left")
        l.bind("<Button-1>", lambda e: self.go("login"))

    def do_signup(self):
        if not all(e.get() for e in (self.su_name, self.su_mail, self.su_p1, self.su_p2)):
            return messagebox.showwarning("Sign up", "Please fill in all fields.")
        if len(self.su_p1.get()) < 6:
            return messagebox.showwarning("Sign up", "Password must be at least 6 characters.")
        if self.su_p1.get() != self.su_p2.get():
            return messagebox.showerror("Sign up", "Passwords do not match.")
        self.go("home")

    # ----- 4 home (dashboard) -----
    def build_home(self, f):
        body, right = self.page(f, "Hello User!", "Keep your important documents safe, organized and always on time")
        Btn(right, "＋ Add Document", lambda: self.go("add"), bg=DARK, padx=18, pady=8).pack()

        stats = tk.Frame(body, bg=PAGE)
        stats.pack(fill="x", pady=(0, 18))
        self.stat_lbls = {}
        for i, (key, label, bg) in enumerate([("total", "📋 Total Documents", "#e9e9ee"),
                                              ("soon", "⏳ Expiring in 60 days", "#ffe1e1"),
                                              ("expired", "⚠️ Expired", "#fff3a8")]):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            c = tk.Frame(stats, bg=bg)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0 if i == 2 else 8))
            tk.Label(c, text=label, bg=bg, font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(12, 0))
            self.stat_lbls[key] = tk.Label(c, text="0", bg=bg, font=("Segoe UI", 24, "bold"))
            self.stat_lbls[key].pack(anchor="w", padx=16, pady=(0, 12))

        cols = tk.Frame(body, bg=PAGE)
        cols.pack(fill="both", expand=True)
        cols.grid_columnconfigure(0, weight=3, uniform="h")
        cols.grid_columnconfigure(1, weight=2, uniform="h")
        cols.grid_rowconfigure(0, weight=1)

        left = tk.Frame(cols, bg=PAGE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        row = tk.Frame(left, bg=PAGE)
        row.pack(fill="x")
        tk.Label(row, text="Expiring Soon", font=("Segoe UI", 13, "bold"), bg=PAGE).pack(side="left")
        va = tk.Label(row, text="View All", fg=P, bg=PAGE, font=("Segoe UI", 10, "bold"), cursor="hand2")
        va.pack(side="right")
        va.bind("<Button-1>", lambda e: self.go("docs"))
        self.exp_box = tk.Frame(left, bg=PAGE)
        self.exp_box.pack(fill="x", pady=(8, 0))

        rt = tk.Frame(cols, bg=PAGE)
        rt.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        tk.Label(rt, text="Document Categories", font=("Segoe UI", 13, "bold"), bg=PAGE).pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(rt, bg=PAGE)
        grid.pack(fill="x")
        self.cat_counts = {}
        for i, (key, ic, label, bg, fg) in enumerate(self.CATS):
            grid.grid_columnconfigure(i % 3, weight=1, uniform="c")
            c = tk.Frame(grid, bg=bg, cursor="hand2")
            c.grid(row=i // 3, column=i % 3, padx=5, pady=5, sticky="nsew")
            a = tk.Label(c, text=ic, bg=bg, fg=fg, font=("Segoe UI Emoji", 22))
            b = tk.Label(c, text=label, bg=bg, fg=fg, font=("Segoe UI", 10, "bold"))
            n = tk.Label(c, text="0", bg=bg, fg=fg, font=("Segoe UI", 9))
            a.pack(pady=(14, 2))
            b.pack()
            n.pack(pady=(0, 14))
            self.cat_counts[key] = n
            for w in (c, a, b, n):
                w.bind("<Button-1>", lambda e, k=key: self.open_category(k))

    def open_category(self, key):
        self.filter = key
        self.go("docs")

    def render_home(self):
        left = [days_left(d) for d in self.docs if d["exp"]]
        self.stat_lbls["total"].config(text=str(len(self.docs)))
        self.stat_lbls["soon"].config(text=str(sum(1 for n in left if 0 <= n <= 60)))
        self.stat_lbls["expired"].config(text=str(sum(1 for n in left if n < 0)))
        for k, lbl in self.cat_counts.items():
            c = sum(1 for d in self.docs if d["cat"] == k)
            lbl.config(text=f"{c} document{'s' if c != 1 else ''}")
        for w in self.exp_box.winfo_children():
            w.destroy()
        soon = sorted((d for d in self.docs if days_left(d) is not None and 0 <= days_left(d) <= 60),
                      key=days_left)[:5]
        if not soon:
            tk.Label(self.exp_box, text="Nothing expiring soon 🎉", fg=MUT, bg=PAGE).pack(anchor="w", pady=6)
        for d in soon:
            card = tk.Frame(self.exp_box, bg="#ffe1e1", highlightbackground="#f3b3b3", highlightthickness=1)
            card.pack(fill="x", pady=4)
            tk.Label(card, text=d["icon"], font=("Segoe UI Emoji", 20), bg="#ffe1e1").pack(side="left", padx=14, pady=10)
            info = tk.Frame(card, bg="#ffe1e1")
            info.pack(side="left", pady=8)
            tk.Label(info, text=d["name"], font=("Segoe UI", 11, "bold"), bg="#ffe1e1").pack(anchor="w")
            tk.Label(info, text=f"Expires: {fmt(d['exp'])}", font=("Segoe UI", 9), bg="#ffe1e1").pack(anchor="w")
            tk.Label(card, text=f"in {days_left(d)} days", fg=RED, font=("Segoe UI", 10, "bold"),
                     bg="#ffe1e1").pack(side="right", padx=16)

    # ----- 5 my documents -----
    def build_docs(self, f):
        body, right = self.page(f, "My Documents", "Search, filter and manage all your documents")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.render_docs())
        tk.Entry(right, textvariable=self.search_var, relief="flat", font=("Segoe UI", 11), width=32,
                 highlightthickness=1, highlightbackground=LINE, highlightcolor=P).pack(ipady=7)
        chips = tk.Frame(body, bg=PAGE)
        chips.pack(fill="x", pady=(0, 12))
        self.chips = {}
        for name in ("All", "Id", "Vehicle", "Education", "Insurance", "Finance", "Others"):
            c = tk.Label(chips, text=name, font=("Segoe UI", 10), padx=14, pady=4, cursor="hand2",
                         highlightbackground=INK, highlightthickness=1)
            c.pack(side="left", padx=(0, 8))
            c.bind("<Button-1>", lambda e, n=name: self.set_filter(n))
            self.chips[name] = c
        self.doc_scroll = Scroll(body, bg=PAGE)
        self.doc_scroll.pack(fill="both", expand=True)

    def set_filter(self, n):
        self.filter = n
        self.render_docs()

    def render_docs(self):
        for n, c in self.chips.items():
            on = n == self.filter
            c.config(bg=P if on else PAGE, fg="white" if on else INK, highlightbackground=P if on else INK)
        box = self.doc_scroll.inner
        for w in box.winfo_children():
            w.destroy()
        q = self.search_var.get().lower().strip()
        items = [d for d in self.docs
                 if (self.filter == "All" or d["cat"] == self.filter) and q in (d["name"] + d["num"]).lower()]
        if not items:
            tk.Label(box, text="No documents found.\nClick Add Document to create one.", fg=MUT, bg=PAGE).pack(pady=30)
        for d in items:
            n = days_left(d)
            warn = n is not None and n <= 30
            card = self.card(box)
            card.pack(fill="x", pady=4, padx=2)
            card.grid_columnconfigure(1, weight=1)
            tk.Label(card, text=d["icon"], font=("Segoe UI Emoji", 20), bg=BG).grid(row=0, column=0, padx=16, pady=12)
            info = tk.Frame(card, bg=BG)
            info.grid(row=0, column=1, sticky="w")
            tk.Label(info, text=d["name"], font=("Segoe UI", 11, "bold"), bg=BG).pack(anchor="w")
            tk.Label(info, text=d["num"], font=("Segoe UI", 9), fg=MUT, bg=BG).pack(anchor="w")
            tk.Label(card, text=d["cat"], font=("Segoe UI", 10), fg=MUT, bg=BG, width=12).grid(row=0, column=2)
            tk.Label(card, text=f"Expiry: {fmt(d['exp'])}" if d["exp"] else "No Expiry",
                     font=("Segoe UI", 10), fg=RED if warn else MUT, bg=BG, width=20).grid(row=0, column=3)
            tk.Label(card, text="Expiring soon" if warn else "Valid", font=("Segoe UI", 9),
                     bg="#ffb199" if warn else "#d8f5df", fg="#8a2a10" if warn else "#256b3a",
                     padx=10, pady=2, width=12).grid(row=0, column=4, padx=10)
            dl = tk.Label(card, text="🗑", bg=BG, cursor="hand2", font=("Segoe UI Emoji", 13))
            dl.grid(row=0, column=5, padx=(4, 16))
            dl.bind("<Button-1>", lambda e, doc=d: self.delete_doc(doc))

    def delete_doc(self, doc):
        if messagebox.askyesno("Delete", f"Delete '{doc['name']}'?"):
            remove_doc(doc["id"])
            self.docs.remove(doc)
            self.render_docs()

    # ----- 6 calendar -----
    def build_calendar(self, f):
        body, right = self.page(f, "Calendar", "See when your documents expire")
        body.grid_columnconfigure(0, weight=3, uniform="k")
        body.grid_columnconfigure(1, weight=2, uniform="k")
        body.grid_rowconfigure(0, weight=1)
        lc = self.card(body)
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        nav = tk.Frame(lc, bg=BG)
        nav.pack(fill="x", pady=(14, 4), padx=16)
        prev = tk.Label(nav, text="‹", font=("Segoe UI", 20, "bold"), bg=BG, fg=P, cursor="hand2")
        prev.pack(side="left")
        nxt = tk.Label(nav, text="›", font=("Segoe UI", 20, "bold"), bg=BG, fg=P, cursor="hand2")
        nxt.pack(side="right")
        prev.bind("<Button-1>", lambda e: self.shift_month(-1))
        nxt.bind("<Button-1>", lambda e: self.shift_month(1))
        self.month_lbl = tk.Label(nav, font=("Segoe UI", 20, "bold"), bg=BG, fg=INK)
        self.month_lbl.pack()
        self.cal_grid = tk.Frame(lc, bg=BG)
        self.cal_grid.pack(fill="both", expand=True, padx=16, pady=(4, 16))
        rc = tk.Frame(body, bg=PAGE)
        rc.grid(row=0, column=1, sticky="nsew", padx=(14, 0))
        tk.Label(rc, text="Upcoming Expiries", font=("Segoe UI", 13, "bold"), bg=PAGE).pack(anchor="w", pady=(0, 8))
        self.cal_list = tk.Frame(rc, bg=PAGE)
        self.cal_list.pack(fill="x")

    def shift_month(self, step):
        m = self.cal_m + step
        self.cal_y += (m - 1) // 12
        self.cal_m = (m - 1) % 12 + 1
        self.render_calendar()

    def render_calendar(self):
        for w in self.cal_grid.winfo_children() + self.cal_list.winfo_children():
            w.destroy()
        y, m = self.cal_y, self.cal_m
        self.month_lbl.config(text=date(y, m, 1).strftime("%B %Y"))
        marks = {}
        for d in self.docs:
            if d["exp"]:
                e = date.fromisoformat(d["exp"])
                if (e.year, e.month) == (y, m):
                    marks.setdefault(e.day, []).append(d["name"])
        for c in range(7):
            self.cal_grid.grid_columnconfigure(c, weight=1, uniform="d")
        for c, h in enumerate(["SU", "MO", "TU", "WE", "TH", "FR", "SA"]):
            tk.Label(self.cal_grid, text=h, font=("Segoe UI", 9, "bold"), fg=MUT, bg=BG).grid(row=0, column=c, pady=4)
        for r, week in enumerate(calendar.Calendar(firstweekday=6).monthdayscalendar(y, m), start=1):
            self.cal_grid.grid_rowconfigure(r, weight=1)
            for c, day in enumerate(week):
                if not day:
                    continue
                on = day in marks
                today = (y, m, day) == (TODAY.year, TODAY.month, TODAY.day)
                tk.Label(self.cal_grid, text=str(day), bg=P if on else BG, fg="white" if on else INK,
                         font=("Segoe UI", 12, "bold" if (on or today) else "normal"),
                         highlightbackground=P2 if today else BG, highlightthickness=2 if today else 0
                         ).grid(row=r, column=c, sticky="nsew", padx=2, pady=2, ipady=8)
        up = sorted((d for d in self.docs if d["exp"] and days_left(d) >= 0), key=days_left)[:6]
        if not up:
            tk.Label(self.cal_list, text="No upcoming expiries", fg=MUT, bg=PAGE).pack(anchor="w")
        for d in up:
            n = days_left(d)
            col = "#ffc9c9" if n <= 30 else "#fff3a8" if n <= 90 else "#c9f2d6"
            ev = tk.Frame(self.cal_list, bg=col)
            ev.pack(fill="x", pady=4)
            left = tk.Frame(ev, bg=col)
            left.pack(side="left", padx=14, pady=8)
            tk.Label(left, text=fmt(d["exp"]), font=("Segoe UI", 9), bg=col).pack(anchor="w")
            tk.Label(left, text=d["name"], font=("Segoe UI", 11, "bold"), bg=col).pack(anchor="w")
            tk.Label(ev, text=f"in {n} days", fg=RED, font=("Segoe UI", 10, "bold"), bg=col).pack(side="right", padx=14)

    # ----- 7 profile -----
    def build_profile(self, f):
        body, _ = self.page(f, "Profile", "Manage your account and settings")
        c = self.card(body)
        c.pack(anchor="nw", fill="x")
        who = tk.Frame(c, bg=BG)
        who.pack(fill="x", padx=24, pady=20)
        tk.Label(who, text="🧑", font=("Segoe UI Emoji", 30), bg="#f0e6ff", width=3).pack(side="left")
        info = tk.Frame(who, bg=BG)
        info.pack(side="left", padx=16)
        tk.Label(info, text="User_123", font=("Segoe UI", 14, "bold"), bg=BG).pack(anchor="w")
        tk.Label(info, text="User@gmail.com", font=("Segoe UI", 10), fg=MUT, bg=BG).pack(anchor="w")
        for text in ("🔔  Reminder setting", "🔒  Privacy", "🔔  Notification settings",
                     "ⓘ  About App", "❔  Help & Support"):
            row = tk.Frame(c, bg=BG, highlightbackground=LINE, highlightthickness=1, cursor="hand2")
            row.pack(fill="x", padx=24, pady=5)
            tk.Label(row, text=text, bg=BG, font=("Segoe UI", 11)).pack(side="left", padx=14, pady=14)
            tk.Label(row, text="›", bg=BG, font=("Segoe UI", 14)).pack(side="right", padx=14)
        Btn(c, "⏻  Log out", lambda: self.go("login"), bg="#ffd5d5", fg="#c33").pack(fill="x", padx=24, pady=20)

    # ----- 8 add document -----
    def build_add(self, f):
        body, _ = self.page(f, "Add Document", "Save a new document and set a reminder")
        c = self.card(body)
        c.pack(anchor="nw", fill="x")
        form = tk.Frame(c, bg=BG)
        form.pack(fill="x", padx=28, pady=24)
        form.grid_columnconfigure(0, weight=1, uniform="f")
        form.grid_columnconfigure(1, weight=1, uniform="f")

        def lab(t, r, col):
            tk.Label(form, text=t, bg=BG, font=("Segoe UI", 10)).grid(row=r, column=col, sticky="w",
                                                                      padx=8, pady=(10, 2))

        lab("Document type", 0, 0)
        self.a_type = ttk.Combobox(form, state="readonly",
                                   values=["Driving Licence", "Id", "Vehicle", "Education", "Insurance", "Finance", "Others"])
        self.a_type.current(0)
        self.a_type.grid(row=1, column=0, sticky="ew", padx=8, ipady=5)
        lab("Document Name", 0, 1)
        self.a_name = Entry(form, "e.g. Driving licence")
        self.a_name.grid(row=1, column=1, sticky="ew", padx=8, ipady=6)
        lab("Document Number", 2, 0)
        self.a_num = Entry(form, "TN-XX-69101102")
        self.a_num.grid(row=3, column=0, sticky="ew", padx=8, ipady=6)
        lab("Reminder", 2, 1)
        self.a_rem = ttk.Combobox(form, state="readonly",
                                  values=["Remainder 30 days before", "Remainder 7 days before", "Remainder 60 days before"])
        self.a_rem.current(0)
        self.a_rem.grid(row=3, column=1, sticky="ew", padx=8, ipady=5)
        lab("Issue date (YYYY-MM-DD)", 4, 0)
        self.a_issue = Entry(form, "2024-01-31")
        self.a_issue.grid(row=5, column=0, sticky="ew", padx=8, ipady=6)
        lab("Expiry Date (YYYY-MM-DD)", 4, 1)
        self.a_exp = Entry(form, "2030-01-31")
        self.a_exp.grid(row=5, column=1, sticky="ew", padx=8, ipady=6)
        lab("Upload Document", 6, 0)
        self.up_lbl = tk.Label(form, text="⬆️  Click to upload or choose file  (PNG/PDF/JPG)", fg=P2, bg=BG,
                               font=("Segoe UI", 10), highlightbackground=INK, highlightthickness=1,
                               cursor="hand2", pady=18)
        self.up_lbl.grid(row=7, column=0, columnspan=2, sticky="ew", padx=8)
        self.up_lbl.bind("<Button-1>", lambda e: self.pick_file())
        Btn(form, "SAVE", self.save_doc, padx=40, pady=9).grid(row=8, column=1, sticky="e", padx=8, pady=(20, 0))

    def pick_file(self):
        p = filedialog.askopenfilename(filetypes=[("Documents", "*.png *.jpg *.jpeg *.pdf")])
        if p:
            self.file_path = p
            self.up_lbl.config(text="📎  " + os.path.basename(p))

    def save_doc(self):
        name, num, exp = self.a_name.get().strip(), self.a_num.get().strip(), self.a_exp.get().strip()
        if not name or not num or not exp:
            return messagebox.showwarning("Add Document", "Name, number and expiry date are required.")
        try:
            date.fromisoformat(exp)
            if self.a_issue.get().strip():
                date.fromisoformat(self.a_issue.get().strip())
        except ValueError:
            return messagebox.showerror("Add Document", "Dates must be in YYYY-MM-DD format.")
        t = self.a_type.get()
        cat = t if t in ("Id", "Vehicle", "Education", "Insurance", "Finance") else ("Id" if t == "Driving Licence" else "Others")
        doc = {"name": name, "num": num, "cat": cat, "exp": exp, "icon": "📄",
               "issue": self.a_issue.get().strip() or None, "file": self.file_path,
               "reminder": self.a_rem.get()}
        doc["id"] = add_doc(doc)
        self.docs.insert(0, doc)
        for e in (self.a_name, self.a_num, self.a_issue, self.a_exp):
            e.clear()
        self.file_path = None
        self.up_lbl.config(text="⬆️  Click to upload or choose file  (PNG/PDF/JPG)")
        self.filter = "All"
        self.go("docs")


if __name__ == "__main__":
    App().mainloop()
