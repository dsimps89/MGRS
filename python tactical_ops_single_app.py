"""
Tactical Operations Planner - Single File Python App
====================================================
A visually structured Tkinter desktop application converted from several small
console prototypes. This version is designed as a safe training, planning, and
record-keeping template. It avoids operational weapon-use guidance and focuses
on risk awareness, navigation estimates, checklists, and documentation.

Run:
    python tactical_ops_single_app.py

No third-party packages required.
"""

from __future__ import annotations

import json
import math
import os
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_NAME = "Tactical Operations Planner"
APP_VERSION = "1.0"
DATA_FILE = Path.home() / ".tactical_ops_planner_data.json"

# ----------------------------- Core Calculations -----------------------------

MGRS_BANDS = "CDEFGHJKLMNPQRSTUVWX"
MGRS_EASTING_SETS = ["ABCDEFGH", "JKLMNPQR", "STUVWXYZ"]
MGRS_NORTHING_SETS = ["ABCDEFGHJKLMNPQRSTUV", "FGHJKLMNPQRSTUVABCDE"]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two lat/lon points in kilometers."""
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lon = math.radians(lon2 - lon1)
    y = math.sin(d_lon) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(d_lon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def latitude_band(lat: float) -> str:
    if not -80 <= lat <= 84:
        return "Z"  # outside standard MGRS range
    index = int((lat + 80) / 8)
    return MGRS_BANDS[min(index, len(MGRS_BANDS) - 1)]


def latlon_to_utm_approx(lat: float, lon: float) -> tuple[int, str, float, float]:
    """Approximate WGS84 lat/lon to UTM. Accurate enough for planning templates, not surveying."""
    a = 6378137.0
    f = 1 / 298.257223563
    k0 = 0.9996
    e = math.sqrt(f * (2 - f))
    e_sq = e ** 2
    e_prime_sq = e_sq / (1 - e_sq)

    zone = int((lon + 180) / 6) + 1
    lon_origin = (zone - 1) * 6 - 180 + 3
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon_origin_rad = math.radians(lon_origin)

    n = a / math.sqrt(1 - e_sq * math.sin(lat_rad) ** 2)
    t = math.tan(lat_rad) ** 2
    c = e_prime_sq * math.cos(lat_rad) ** 2
    A = math.cos(lat_rad) * (lon_rad - lon_origin_rad)

    m = a * ((1 - e_sq / 4 - 3 * e_sq ** 2 / 64 - 5 * e_sq ** 3 / 256) * lat_rad
             - (3 * e_sq / 8 + 3 * e_sq ** 2 / 32 + 45 * e_sq ** 3 / 1024) * math.sin(2 * lat_rad)
             + (15 * e_sq ** 2 / 256 + 45 * e_sq ** 3 / 1024) * math.sin(4 * lat_rad)
             - (35 * e_sq ** 3 / 3072) * math.sin(6 * lat_rad))

    easting = k0 * n * (A + (1 - t + c) * A ** 3 / 6 + (5 - 18 * t + t ** 2 + 72 * c - 58 * e_prime_sq) * A ** 5 / 120) + 500000
    northing = k0 * (m + n * math.tan(lat_rad) * (A ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * A ** 4 / 24 +
                                               (61 - 58 * t + t ** 2 + 600 * c - 330 * e_prime_sq) * A ** 6 / 720))
    if lat < 0:
        northing += 10000000
    return zone, latitude_band(lat), easting, northing


def latlon_to_mgrs_approx(lat: float, lon: float, precision: int = 5) -> str:
    zone, band, easting, northing = latlon_to_utm_approx(lat, lon)
    set_col = MGRS_EASTING_SETS[(zone - 1) % 3]
    set_row = MGRS_NORTHING_SETS[(zone - 1) % 2]
    col = set_col[int(easting / 100000) - 1 if 1 <= int(easting / 100000) <= 8 else 0]
    row = set_row[int(northing / 100000) % 20]
    divisor = 10 ** (5 - precision)
    east = int((easting % 100000) / divisor)
    north = int((northing % 100000) / divisor)
    return f"{zone}{band} {col}{row} {east:0{precision}d} {north:0{precision}d}"


def estimate_position_from_landmarks(base_lat: float, base_lon: float, observations: list[tuple[float, float]]) -> tuple[float, float]:
    """Rough dead-reckoning style estimate using distance and bearing observations."""
    if not observations:
        return base_lat, base_lon
    lat_sum = 0.0
    lon_sum = 0.0
    for bearing, distance_km in observations:
        brng = math.radians(bearing)
        d = distance_km / 6371.0088
        lat1 = math.radians(base_lat)
        lon1 = math.radians(base_lon)
        lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brng))
        lon2 = lon1 + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
        lat_sum += math.degrees(lat2)
        lon_sum += math.degrees(lon2)
    return lat_sum / len(observations), lon_sum / len(observations)


def qualitative_risk(score: float) -> str:
    if score >= 80:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def safe_recommendations(risk: str) -> list[str]:
    base = [
        "Verify information from multiple sources before decisions.",
        "Confirm communication, accountability, medical, and evacuation plans.",
        "Document assumptions, unknowns, and time of last update.",
    ]
    if risk in {"Critical", "High"}:
        return [
            "Pause and elevate review to qualified leadership.",
            "Reduce exposure, simplify movement, and avoid unnecessary escalation.",
            "Prioritize deconfliction, civilian safety, and contingency planning.",
        ] + base
    if risk == "Moderate":
        return [
            "Proceed only after additional checks and updated situational information.",
            "Assign clear roles, check equipment status, and maintain fallback options.",
        ] + base
    return ["Continue routine monitoring and maintain readiness checks."] + base


# ----------------------------- Data Model -----------------------------

@dataclass
class MissionRecord:
    created: str
    title: str
    objective: str
    location: str
    risk_score: float
    risk_level: str
    summary: str


class Store:
    def __init__(self, path: Path = DATA_FILE):
        self.path = path
        self.records: list[MissionRecord] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self.records = [MissionRecord(**item) for item in payload.get("records", [])]
            except Exception:
                self.records = []

    def save(self) -> None:
        payload = {"records": [asdict(r) for r in self.records]}
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(self, record: MissionRecord) -> None:
        self.records.insert(0, record)
        self.save()


# ----------------------------- GUI Helpers -----------------------------

class ScrollFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, bg="#0f172a")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.inner = ttk.Frame(canvas, style="Panel.TFrame")
        self.inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")


def field(parent, label: str, default: str = "", width: int = 24) -> tuple[ttk.Frame, tk.StringVar, ttk.Entry]:
    frame = ttk.Frame(parent, style="Panel.TFrame")
    ttk.Label(frame, text=label, style="Muted.TLabel").pack(anchor="w")
    var = tk.StringVar(value=default)
    entry = ttk.Entry(frame, textvariable=var, width=width)
    entry.pack(fill="x", pady=(3, 0))
    return frame, var, entry


def number(value: str, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


# ----------------------------- Main Application -----------------------------

class TacticalOpsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x780")
        self.minsize(980, 680)
        self.store = Store()
        self.configure(bg="#0f172a")
        self._style()
        self._layout()

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#0f172a")
        style.configure("Panel.TFrame", background="#111827")
        style.configure("Card.TFrame", background="#1f2937", relief="flat")
        style.configure("TLabel", background="#0f172a", foreground="#e5e7eb", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#0f172a", foreground="#f8fafc", font=("Segoe UI", 24, "bold"))
        style.configure("SubTitle.TLabel", background="#0f172a", foreground="#93c5fd", font=("Segoe UI", 11))
        style.configure("CardTitle.TLabel", background="#1f2937", foreground="#f8fafc", font=("Segoe UI", 14, "bold"))
        style.configure("CardText.TLabel", background="#1f2937", foreground="#d1d5db", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#111827", foreground="#9ca3af", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=10, font=("Segoe UI", 10, "bold"), background="#2563eb", foreground="#ffffff")
        style.map("TButton", background=[("active", "#1d4ed8")])
        style.configure("TNotebook", background="#0f172a", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(18, 10), font=("Segoe UI", 10, "bold"), background="#1f2937", foreground="#d1d5db")
        style.map("TNotebook.Tab", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview", background="#111827", fieldbackground="#111827", foreground="#e5e7eb", rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#1f2937", foreground="#f8fafc")

    def _layout(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=24, pady=(18, 10))
        ttk.Label(header, text="Tactical Operations Planner", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Safe planning template • MGRS estimates • risk review • mission records", style="SubTitle.TLabel").pack(anchor="w", pady=(2, 0))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.dashboard_tab()
        self.mgrs_tab()
        self.risk_tab()
        self.checklist_tab()
        self.records_tab()
        self.about_tab()

    def card(self, parent, title: str, text: str) -> ttk.Frame:
        c = ttk.Frame(parent, style="Card.TFrame", padding=18)
        ttk.Label(c, text=title, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(c, text=text, style="CardText.TLabel", wraplength=310, justify="left").pack(anchor="w", pady=(8, 0))
        return c

    def dashboard_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="Dashboard")
        grid = ttk.Frame(tab, style="Panel.TFrame")
        grid.pack(fill="x")
        cards = [
            ("Mission Builder", "Record objective, location, risk level, notes, and decision status."),
            ("MGRS / UTM", "Convert latitude and longitude into an approximate MGRS-style coordinate."),
            ("Risk Review", "Generate a non-operational risk score using terrain, weather, distance, unit ratio, and uncertainty."),
            ("Checklists", "Use structured prompts for communications, medical, logistics, navigation, and debrief."),
        ]
        for i, (t, tx) in enumerate(cards):
            self.card(grid, t, tx).grid(row=0, column=i, padx=8, pady=8, sticky="nsew")
            grid.columnconfigure(i, weight=1)

        text = tk.Text(tab, height=18, bg="#111827", fg="#e5e7eb", insertbackground="#ffffff", relief="flat", wrap="word", font=("Consolas", 11))
        text.pack(fill="both", expand=True, pady=(16, 0))
        text.insert("end", self._dashboard_text())
        text.configure(state="disabled")

    def _dashboard_text(self) -> str:
        return (
            "SYSTEM OVERVIEW\n"
            "---------------\n"
            "This application merges the uploaded Infantry, MGRS, Military Program, and Tactical Ops Advisor prototypes into one desktop program.\n\n"
            "Design scope:\n"
            "  • Planning and training support only\n"
            "  • Navigation estimation and coordinate formatting\n"
            "  • Risk scoring and safety-focused recommendations\n"
            "  • Mission notes, checklists, and exportable records\n\n"
            "Important accuracy note:\n"
            "  The built-in MGRS function is approximate and dependency-free. For field-grade navigation, verify with approved maps, GPS, and official tools.\n"
        )

    def mgrs_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="MGRS Tools")
        form = ttk.Frame(tab, style="Panel.TFrame")
        form.pack(fill="x")
        _, self.lat_var, _ = field(form, "Latitude", "42.4048")
        _, self.lon_var, _ = field(form, "Longitude", "-82.1910")
        _, self.base_lat_var, _ = field(form, "Base latitude", "42.4048")
        _, self.base_lon_var, _ = field(form, "Base longitude", "-82.1910")
        for i, child in enumerate(form.winfo_children()):
            child.grid(row=0, column=i, padx=8, sticky="ew")
            form.columnconfigure(i, weight=1)

        obs = ttk.LabelFrame(tab, text="Landmark Observations: bearing degrees + distance km", padding=12)
        obs.pack(fill="x", pady=14)
        self.obs_vars = []
        for i in range(3):
            _, b, _ = field(obs, f"Bearing {i+1}", str(30 + i * 40))
            _, d, _ = field(obs, f"Distance {i+1} km", str(2 + i))
            self.obs_vars.append((b, d))
            obs.winfo_children()[-2].grid(row=0, column=i*2, padx=8, sticky="ew")
            obs.winfo_children()[-1].grid(row=0, column=i*2+1, padx=8, sticky="ew")
            obs.columnconfigure(i*2, weight=1)
            obs.columnconfigure(i*2+1, weight=1)

        ttk.Button(tab, text="Calculate MGRS / Estimate", command=self.calculate_mgrs).pack(anchor="w", pady=(0, 10))
        self.mgrs_output = tk.Text(tab, height=18, bg="#111827", fg="#e5e7eb", insertbackground="#ffffff", relief="flat", wrap="word", font=("Consolas", 11))
        self.mgrs_output.pack(fill="both", expand=True)

    def calculate_mgrs(self) -> None:
        lat, lon = number(self.lat_var.get(), 0), number(self.lon_var.get(), 0)
        base_lat, base_lon = number(self.base_lat_var.get(), lat), number(self.base_lon_var.get(), lon)
        observations = [(number(b.get()), number(d.get())) for b, d in self.obs_vars]
        est_lat, est_lon = estimate_position_from_landmarks(base_lat, base_lon, observations)
        dist = haversine_km(base_lat, base_lon, lat, lon)
        brg = bearing_degrees(base_lat, base_lon, lat, lon)
        out = [
            "MGRS / NAVIGATION ESTIMATE",
            "--------------------------",
            f"Input lat/lon:          {lat:.6f}, {lon:.6f}",
            f"Approx. MGRS:           {latlon_to_mgrs_approx(lat, lon)}",
            f"UTM approx:             Zone {latlon_to_utm_approx(lat, lon)[0]}{latitude_band(lat)}",
            "",
            f"Base point:             {base_lat:.6f}, {base_lon:.6f}",
            f"Distance base→input:    {dist:.2f} km",
            f"Bearing base→input:     {brg:.1f}°",
            "",
            "Observation-based estimate:",
            f"Estimated lat/lon:      {est_lat:.6f}, {est_lon:.6f}",
            f"Estimated MGRS:         {latlon_to_mgrs_approx(est_lat, est_lon)}",
            "",
            "Accuracy note: dependency-free approximation. Verify with official mapping/GPS before real-world use.",
        ]
        self.mgrs_output.delete("1.0", "end")
        self.mgrs_output.insert("end", "\n".join(out))

    def risk_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="Risk Review")
        form = ttk.Frame(tab, style="Panel.TFrame")
        form.pack(fill="x")
        labels = [
            ("Mission title", "Training Review"), ("Objective", "Reconnaissance"), ("Location", "Chatham area"),
            ("Terrain -10 to +10", "0"), ("Weather -10 to +10", "0"), ("Enemy/Threat level 0-10", "3"),
            ("Friendly count", "8"), ("Opposing/unknown count", "4"), ("Distance to concern km", "5"),
            ("Uncertainty 0-10", "4"),
        ]
        self.risk_vars = {}
        for idx, (lab, default) in enumerate(labels):
            fr, var, _ = field(form, lab, default)
            self.risk_vars[lab] = var
            fr.grid(row=idx // 5, column=idx % 5, padx=8, pady=8, sticky="ew")
            form.columnconfigure(idx % 5, weight=1)
        ttk.Button(tab, text="Generate Risk Review", command=self.generate_risk).pack(anchor="w", pady=10)
        self.risk_output = tk.Text(tab, height=20, bg="#111827", fg="#e5e7eb", insertbackground="#ffffff", relief="flat", wrap="word", font=("Consolas", 11))
        self.risk_output.pack(fill="both", expand=True)

    def generate_risk(self) -> None:
        terrain = number(self.risk_vars["Terrain -10 to +10"].get())
        weather = number(self.risk_vars["Weather -10 to +10"].get())
        threat = clamp(number(self.risk_vars["Enemy/Threat level 0-10"].get()), 0, 10)
        friendly = max(1, number(self.risk_vars["Friendly count"].get(), 1))
        opposing = max(0, number(self.risk_vars["Opposing/unknown count"].get(), 0))
        distance = max(0.1, number(self.risk_vars["Distance to concern km"].get(), 5))
        uncertainty = clamp(number(self.risk_vars["Uncertainty 0-10"].get()), 0, 10)

        terrain_penalty = (10 - clamp(terrain, -10, 10)) * 2.0
        weather_penalty = (10 - clamp(weather, -10, 10)) * 1.5
        ratio_penalty = clamp((opposing / friendly) * 20, 0, 30)
        distance_penalty = clamp((10 / distance) * 8, 0, 25)
        score = clamp(threat * 5 + uncertainty * 3 + terrain_penalty + weather_penalty + ratio_penalty + distance_penalty, 0, 100)
        level = qualitative_risk(score)
        recs = safe_recommendations(level)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        summary = f"Risk {level} ({score:.1f}/100). Main drivers: threat={threat}, uncertainty={uncertainty}, terrain={terrain}, weather={weather}."
        lines = [
            "RISK REVIEW",
            "-----------",
            f"Created:      {now}",
            f"Mission:      {self.risk_vars['Mission title'].get()}",
            f"Objective:    {self.risk_vars['Objective'].get()}",
            f"Location:     {self.risk_vars['Location'].get()}",
            "",
            f"Risk score:   {score:.1f}/100",
            f"Risk level:   {level}",
            "",
            "Inputs:",
            f"  Terrain: {terrain} | Weather: {weather} | Threat: {threat} | Uncertainty: {uncertainty}",
            f"  Friendly: {friendly:g} | Opposing/unknown: {opposing:g} | Distance: {distance:g} km",
            "",
            "Safety-focused recommendations:",
        ] + [f"  - {r}" for r in recs] + ["", "Summary:", f"  {summary}"]
        self.risk_output.delete("1.0", "end")
        self.risk_output.insert("end", "\n".join(lines))
        self.store.add(MissionRecord(now, self.risk_vars['Mission title'].get(), self.risk_vars['Objective'].get(), self.risk_vars['Location'].get(), score, level, summary))
        self.refresh_records()

    def checklist_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="Checklists")
        text = tk.Text(tab, bg="#111827", fg="#e5e7eb", insertbackground="#ffffff", relief="flat", wrap="word", font=("Consolas", 11))
        text.pack(fill="both", expand=True)
        text.insert("end", """MISSION PLANNING CHECKLIST
--------------------------
[ ] Objective written in one clear sentence
[ ] Location, time, weather, and terrain recorded
[ ] Known hazards separated from assumptions
[ ] Communications plan checked
[ ] Medical plan checked
[ ] Accountability plan checked
[ ] Navigation backup prepared
[ ] Transportation and logistics checked
[ ] Civilian/deconfliction considerations reviewed
[ ] Abort/stop criteria defined
[ ] Debrief notes captured after completion

COMMUNICATIONS
--------------
[ ] Primary contact method
[ ] Backup contact method
[ ] Check-in schedule
[ ] Lost-contact procedure

MEDICAL / SAFETY
----------------
[ ] First aid equipment location
[ ] Emergency contact route
[ ] Evacuation option
[ ] Weather exposure concerns

DEBRIEF
-------
[ ] What was planned?
[ ] What changed?
[ ] What was unknown?
[ ] What should be improved next time?
""")

    def records_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="Records")
        bar = ttk.Frame(tab, style="Panel.TFrame")
        bar.pack(fill="x", pady=(0, 10))
        ttk.Button(bar, text="Refresh", command=self.refresh_records).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Export JSON", command=self.export_records).pack(side="left")
        self.tree = ttk.Treeview(tab, columns=("created", "title", "objective", "location", "score", "level"), show="headings")
        for col, w in [("created", 150), ("title", 180), ("objective", 180), ("location", 180), ("score", 90), ("level", 100)]:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=w)
        self.tree.pack(fill="both", expand=True)
        self.refresh_records()

    def refresh_records(self) -> None:
        if not hasattr(self, "tree"):
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in self.store.records:
            self.tree.insert("", "end", values=(r.created, r.title, r.objective, r.location, f"{r.risk_score:.1f}", r.risk_level))

    def export_records(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="mission_records.json")
        if path:
            Path(path).write_text(json.dumps({"records": [asdict(r) for r in self.store.records]}, indent=2), encoding="utf-8")
            messagebox.showinfo("Export complete", f"Saved records to:\n{path}")

    def about_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=16, style="Panel.TFrame")
        self.notebook.add(tab, text="About")
        msg = tk.Text(tab, bg="#111827", fg="#e5e7eb", insertbackground="#ffffff", relief="flat", wrap="word", font=("Consolas", 11))
        msg.pack(fill="both", expand=True)
        msg.insert("end", f"""{APP_NAME} v{APP_VERSION}

Converted into one large Python program from the uploaded prototypes:
- MGRS Example Chatham
- MGRS Finder versions
- Infantry Program versions
- Military Program
- Tactical Ops Advisor

This is a visual Tkinter application with no external dependencies.

Use scope:
- Training templates
- Planning notes
- Risk awareness
- Coordinate estimates
- Record keeping

Not for:
- Official navigation without verification
- Weapon targeting
- Operational orders
- Replacing qualified judgment, lawful authority, approved maps, or official systems
""")
        msg.configure(state="disabled")


def main() -> None:
    app = TacticalOpsApp()
    app.mainloop()


if __name__ == "__main__":
    main()
