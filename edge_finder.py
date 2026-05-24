#!/usr/bin/env python3
"""
edge_finder.py — Professional Sports Betting Edge Detection System
NHL + NBA Playoff Analysis | Natural Stat Trick · Cleaning the Glass · ESPN · Kalshi
"""

# ══════════════════════════════════════════════════════
# SECTION 1 — AUTO-INSTALL
# ══════════════════════════════════════════════════════
import subprocess, sys, importlib

_PKGS = {"requests": "requests", "bs4": "beautifulsoup4", "pandas": "pandas",
         "numpy": "numpy", "scipy": "scipy", "schedule": "schedule",
         "colorama": "colorama", "sklearn": "scikit-learn"}

def _bootstrap():
    missing = [pkg for mod, pkg in _PKGS.items() if not _try_import(mod)]
    if missing:
        print(f"[setup] Installing: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet"] + missing)
        print("[setup] Done.\n")

def _try_import(mod):
    try: importlib.import_module(mod); return True
    except ImportError: return False

_bootstrap()

# ══════════════════════════════════════════════════════
# SECTION 2 — IMPORTS
# ══════════════════════════════════════════════════════
import argparse, csv, json, logging, os, pickle, re, threading, time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests
import schedule
from bs4 import BeautifulSoup
from colorama import Fore, Style, init as _cinit
from scipy import stats as scipy_stats
from scipy.stats import poisson as sp_poisson, norm as sp_norm
try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    _SKLEARN = True
except ImportError:
    _SKLEARN = False

_cinit(autoreset=True)

# ══════════════════════════════════════════════════════
# SECTION 3 — CONFIG
# ══════════════════════════════════════════════════════
DEFAULT_BANKROLL = 100.0
CACHE_DIR = Path(".edge_cache")
CACHE_DIR.mkdir(exist_ok=True)

TRACKER_FILE   = Path("bet_tracker.csv")
PRICE_HIST     = CACHE_DIR / "kalshi_prices.json"
CALIBRATION    = CACHE_DIR / "calibration.json"
LINE_HIST      = CACHE_DIR / "line_history.json"
DAILY_LOG_DIR  = Path("daily_log")
DAILY_LOG_DIR.mkdir(exist_ok=True)
LOG_FILE       = Path("edge_finder.log")

CACHE_TTL = {"nhl_teams": 3600, "nhl_goalies": 3600,
             "nba_teams": 3600, "injuries": 900, "kalshi": 180}

W = 53  # Report column width

# Base home-court/ice advantage (applied before team-specific adjustments)
# NHL: 57% home win in playoffs (user-specified)
# NBA: 54% home win in playoffs (user-specified)
# NHL goals per game from 3-season API pull (262 games)
NHL_HOME_BASE  = 0.57
NBA_HOME_BASE  = 0.54
NHL_GOALS_BASE = 6.07

# Minimum edge thresholds by bet type — different standards for home vs away ML
_MIN_EDGE_HOME_ML   = 0.07   # 7%
_MIN_EDGE_AWAY_ML   = 0.12   # 12% — must clear a higher bar to bet against home advantage
_MIN_EDGE_TOTAL     = 0.07   # 7%

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def _season() -> str:
    n = datetime.now()
    y = n.year
    return f"{y}{y+1}" if n.month >= 10 else f"{y-1}{y}"

SEASON = _season()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)
log = logging.getLogger("edge")

# ══════════════════════════════════════════════════════
# SECTION 4 — DATA MODELS
# ══════════════════════════════════════════════════════
@dataclass
class NHLTeamStats:
    team: str
    xgf_60:       float = 0.0
    xga_60:       float = 0.0
    xg_pct:       float = 50.0
    hdcf_pct:     float = 50.0
    hdca_pct:     float = 50.0
    scf_pct:      float = 50.0
    zone_entry:   float = 50.0
    zone_exit:    float = 50.0
    pp_pct:       float = 20.0
    pk_pct:       float = 80.0
    pp_xgf:       float = 0.0
    pts_pct:      float = 0.5   # regular-season points percentage (0.0–1.0)
    rest_days:    int   = 2
    last_played:  str   = ""
    is_home:      bool  = False
    series_wins:  int   = 0
    series_losses:int   = 0

@dataclass
class GoalieStats:
    name:         str
    team:         str
    gsax:         float = 0.0
    hd_sv_pct:    float = 0.82
    sv_pct:       float = 0.909
    toi_last14:   float = 0.0
    games_last14: int   = 0
    home_sv_pct:  float = 0.0
    away_sv_pct:  float = 0.0

@dataclass
class NBATeamStats:
    team:         str
    off_rtg:      float = 110.0
    def_rtg:      float = 110.0
    net_rtg:      float = 0.0
    ts_pct:       float = 0.56
    opp_ts_pct:   float = 0.56
    pace:         float = 98.0
    reb_off:      float = 25.0
    reb_def:      float = 75.0
    ftr:          float = 0.25
    opp_ftr:      float = 0.25
    rest_days:    int   = 2
    last_played:  str   = ""
    is_home:      bool  = False
    series_wins:  int   = 0
    series_losses:int   = 0
    prior_ot_game:     bool = False
    prior_blowout_loss:bool = False
    prior_ot_win:      bool = False

@dataclass
class InjuryReport:
    player:           str
    team:             str
    sport:            str   # "NHL" | "NBA"
    status:           str   # "OUT" | "DOUBTFUL" | "QUESTIONABLE"
    injury:           str
    bpm_impact:       float = 0.0
    win_prob_impact:  float = 0.0
    player_ppg:       float = 0.0    # points per game (or goals for NHL)
    total_ppg_impact: float = 0.0    # expected score adjustment for totals

@dataclass
class KalshiMarket:
    ticker:      str
    title:       str
    sport:       str
    home_team:   str       # full name / abbreviation
    away_team:   str
    home_abbr:   str       # 3-letter Kalshi abbreviation
    away_abbr:   str
    market_type: str       # "ML" | "TOTAL" | "SPREAD" | "PROP"
    yes_price:   float     # 0-1 scale (0.54 = 54 cents = 54%)
    yes_side:    str       # "HOME"|"AWAY" for ML, "OVER" for TOTAL, "HOME_COVER" for SPREAD
    total_line:  Optional[float] = None
    spread_line: Optional[float] = None  # e.g. -1.5 (puck line) or -5.5 (ATS)
    spread_team: str = ""                # which team's perspective the spread is for
    prop_player: str = ""                # player abbr for PROP markets, e.g. "WEMB"
    prop_player_full: str = ""           # resolved full name, e.g. "Victor Wembanyama"
    prop_type:   str = ""                # "PTS" | "REB" | "AST" | "GOALS"
    volume:      float = 0.0
    game_time:   Optional[datetime] = None

@dataclass
class LiveGame:
    game_id:     str
    home_abbr:   str
    away_abbr:   str
    sport:       str          # "NBA" | "NHL"
    home_score:  int = 0
    away_score:  int = 0
    period:      int = 1      # Q or Period number
    clock:       str = ""     # "8:42" remaining in period
    status:      str = "pre"  # "pre" | "in" | "post"
    pct_elapsed: float = 0.0  # 0.0-1.0 fraction of game played

@dataclass
class BetRecommendation:
    game:           str
    sport:          str
    market_type:    str
    model_prob:     float
    kalshi_price:   float
    edge:           float
    ev_per_dollar:  float
    kelly_fraction: float
    bet_size:       float
    category:       str   # STRONG_BET | BET | MARGINAL | SKIP
    bias_notes:     List[str] = field(default_factory=list)
    mv_1h:          float = 0.0
    mv_2h:          float = 0.0
    sharp_signal:   str   = "flat"
    move_class:     str   = "flat"   # "PUBLIC", "SHARP", "STEAM", "flat"
    open_move:      float = 0.0      # cents moved since open today
    move_30m:       float = 0.0      # cents moved in last 30 min
    move_10m:       float = 0.0      # cents moved in last 10 min
    injury_flags:   List[str] = field(default_factory=list)
    confidence:     str   = "MEDIUM"  # "HIGH" | "MEDIUM" | "LOW"
    risk_note:      str   = ""
    bet_side:       str   = ""        # "HOME" | "AWAY" | "TOTAL"
    goalie_warning: str   = ""        # non-empty = starting goalie unconfirmed
    factor_breakdown: dict = field(default_factory=dict)
    timestamp:      str   = field(default_factory=lambda: datetime.now().isoformat())

# ══════════════════════════════════════════════════════
# SECTION 5 — CACHE
# ══════════════════════════════════════════════════════
class Cache:
    def get(self, key: str, ttl: int):
        p = CACHE_DIR / f"{key}.pkl"
        if not p.exists(): return None
        if time.time() - p.stat().st_mtime > ttl: return None
        try:
            with open(p, "rb") as f: return pickle.load(f)
        except Exception: return None

    def set(self, key: str, data):
        try:
            with open(CACHE_DIR / f"{key}.pkl", "wb") as f: pickle.dump(data, f)
        except Exception as e: log.warning(f"cache write {key}: {e}")

    def stale(self, key: str):
        p = CACHE_DIR / f"{key}.pkl"
        if not p.exists(): return None
        try:
            with open(p, "rb") as f: d = pickle.load(f)
            age = (time.time() - p.stat().st_mtime) / 60
            log.warning(f"stale cache {key} ({age:.0f} min old)")
            return d
        except Exception: return None

_cache = Cache()

# ══════════════════════════════════════════════════════
# SECTION 6 — UTILITIES
# ══════════════════════════════════════════════════════
def _sf(vals, i, default=0.0) -> float:
    try:
        s = str(vals[i]).replace("%","").replace(",","").strip()
        return float(s) if s not in ("", "-", "N/A") else default
    except Exception: return default

def _fuzzy(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b: return False          # empty string would match everything
    return a == b or a in b or b in a or bool(set(a.split()) & set(b.split()))

def _fuzzy_player(a: str, b: str) -> bool:
    """Stricter player-name match requiring last-name agreement.
    Prevents 'Jalen Smith' (OUT) from falsely matching 'Jalen Brunson'."""
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b: return False
    if a == b: return True
    ap, bp = a.split(), b.split()
    if not ap or not bp: return False
    return ap[-1] == bp[-1]  # last name must match

def _find_nhl(teams: Dict[str, NHLTeamStats], name: str) -> NHLTeamStats:
    for k, v in teams.items():
        if _fuzzy(k, name): return v
    return NHLTeamStats(team=name)

def _find_nba(teams: Dict[str, NBATeamStats], name: str) -> NBATeamStats:
    for k, v in teams.items():
        if _fuzzy(k, name): return v
    return NBATeamStats(team=name)

def _find_goalie(goalies: Dict[str, GoalieStats], team: str) -> Optional[GoalieStats]:
    for g in goalies.values():
        if _fuzzy(g.team, team): return g
    return None

def _parse_nst_table(table) -> Tuple[List[str], List[List[str]]]:
    """Return (headers, rows) from a Natural Stat Trick DataTable."""
    thead = table.find("thead")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")] if thead else []
    rows = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cols: rows.append(cols)
    return headers, rows

def _col(headers: List[str], *candidates: str) -> int:
    for c in candidates:
        for i, h in enumerate(headers):
            if c.lower() == h.lower(): return i
    return -1

# ══════════════════════════════════════════════════════
# SECTION 7 — NATURAL STAT TRICK SCRAPER
# ══════════════════════════════════════════════════════
class NSTScraper:
    BASE = "https://www.naturalstattrick.com"

    def _get(self, url: str, retries=3) -> Optional[BeautifulSoup]:
        for n in range(retries):
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                r.raise_for_status()
                return BeautifulSoup(r.text, "html.parser")
            except Exception as e:
                log.warning(f"NST attempt {n+1}: {e}")
                if n < retries - 1: time.sleep(2 ** n)
        return None

    def team_stats(self) -> Dict[str, NHLTeamStats]:
        cached = _cache.get("nhl_teams", CACHE_TTL["nhl_teams"])
        if cached: return cached

        url = (f"{self.BASE}/teamtable.php?fromseason={SEASON}&thruseason={SEASON}"
               f"&stype=3&sit=5v5&score=all&rate=y&team=all&loc=B&gpf=410&gpt=&fd=&td=")
        soup = self._get(url)
        if soup is None:
            return _cache.stale("nhl_teams") or {}

        teams = {}
        try:
            table = soup.find("table", id="teams") or soup.find("table")
            if not table: raise ValueError("no table")
            hdrs, rows = _parse_nst_table(table)

            # Map columns by header name
            ci = {
                "team":     _col(hdrs, "Team"),
                "xgf60":    _col(hdrs, "xGF/60"),
                "xga60":    _col(hdrs, "xGA/60"),
                "xgpct":    _col(hdrs, "xGF%"),
                "hdcf_pct": _col(hdrs, "HDCF%"),
                "scf_pct":  _col(hdrs, "SCF%"),
            }

            for row in rows:
                if len(row) < 5: continue
                name = row[ci["team"]] if ci["team"] >= 0 else row[1]
                if not name or name.isdigit(): continue
                s = NHLTeamStats(team=name)
                s.xgf_60   = _sf(row, ci["xgf60"])   if ci["xgf60"]   >= 0 else 0.0
                s.xga_60   = _sf(row, ci["xga60"])   if ci["xga60"]   >= 0 else 0.0
                s.xg_pct   = _sf(row, ci["xgpct"])   if ci["xgpct"]   >= 0 else 50.0
                s.hdcf_pct = _sf(row, ci["hdcf_pct"])if ci["hdcf_pct"]>= 0 else 50.0
                s.scf_pct  = _sf(row, ci["scf_pct"]) if ci["scf_pct"] >= 0 else 50.0
                teams[name] = s
        except Exception as e:
            log.error(f"NST team parse: {e}")

        if teams: _cache.set("nhl_teams", teams)
        return teams or _cache.stale("nhl_teams") or {}

    def goalie_stats(self) -> Dict[str, GoalieStats]:
        cached = _cache.get("nhl_goalies", CACHE_TTL["nhl_goalies"])
        if cached: return cached

        url = (f"{self.BASE}/playerreport.php?fromseason={SEASON}&thruseason={SEASON}"
               f"&stype=3&sit=all&score=all&stdoi=g&rate=n&team=all&pos=G"
               f"&loc=B&toi=0&gpfilt=GP&fd=&td=&tgp=410&lines=single&draftteam=ALL")
        soup = self._get(url)
        if soup is None:
            return _cache.stale("nhl_goalies") or {}

        goalies = {}
        try:
            table = soup.find("table", id="players") or soup.find("table")
            if not table: raise ValueError("no table")
            hdrs, rows = _parse_nst_table(table)

            ci = {
                "name":  _col(hdrs, "Player"),
                "team":  _col(hdrs, "Team"),
                "toi":   _col(hdrs, "TOI"),
                "gsax":  _col(hdrs, "GSAx", "Goals Saved Above Expected"),
                "svpct": _col(hdrs, "SV%"),
                "hdsvp": _col(hdrs, "HDSV%", "HD SV%"),
            }

            for row in rows:
                if len(row) < 4: continue
                name = row[ci["name"]] if ci["name"] >= 0 else row[1]
                team = row[ci["team"]] if ci["team"] >= 0 else ""
                if not name: continue
                g = GoalieStats(name=name, team=team)
                g.gsax      = _sf(row, ci["gsax"])  if ci["gsax"]  >= 0 else 0.0
                g.sv_pct    = _sf(row, ci["svpct"]) if ci["svpct"] >= 0 else 0.909
                g.hd_sv_pct = _sf(row, ci["hdsvp"]) if ci["hdsvp"] >= 0 else 0.82
                if g.sv_pct > 1: g.sv_pct /= 100
                if g.hd_sv_pct > 1: g.hd_sv_pct /= 100
                goalies[name] = g
        except Exception as e:
            log.error(f"NST goalie parse: {e}")

        goalies = self._enrich_fatigue(goalies)
        if goalies: _cache.set("nhl_goalies", goalies)
        return goalies or _cache.stale("nhl_goalies") or {}

    def _enrich_fatigue(self, goalies: Dict[str, GoalieStats]) -> Dict[str, GoalieStats]:
        fd = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        url = (f"{self.BASE}/playerreport.php?fromseason={SEASON}&thruseason={SEASON}"
               f"&stype=3&sit=all&score=all&stdoi=g&rate=n&team=all&pos=G"
               f"&loc=B&toi=0&gpfilt=GP&fd={fd}&td=&tgp=410&lines=single&draftteam=ALL")
        soup = self._get(url)
        if not soup: return goalies
        try:
            table = soup.find("table", id="players") or soup.find("table")
            if not table: return goalies
            hdrs, rows = _parse_nst_table(table)
            ci_name = _col(hdrs, "Player")
            ci_toi  = _col(hdrs, "TOI")
            ci_gp   = _col(hdrs, "GP")
            for row in rows:
                name = row[ci_name] if ci_name >= 0 else (row[1] if len(row) > 1 else "")
                if name in goalies:
                    goalies[name].toi_last14   = _sf(row, ci_toi) if ci_toi >= 0 else 0.0
                    goalies[name].games_last14 = int(_sf(row, ci_gp)) if ci_gp >= 0 else 0
        except Exception as e:
            log.debug(f"fatigue enrich: {e}")
        return goalies

    def pp_pk_stats(self) -> Dict[str, dict]:
        url = (f"{self.BASE}/teamtable.php?fromseason={SEASON}&thruseason={SEASON}"
               f"&stype=3&sit=pp&score=all&rate=y&team=all&loc=B&gpf=410&gpt=&fd=&td=")
        soup = self._get(url)
        if not soup: return {}
        result = {}
        try:
            table = soup.find("table", id="teams") or soup.find("table")
            if not table: return {}
            hdrs, rows = _parse_nst_table(table)
            ci_team  = _col(hdrs, "Team")
            ci_xgf60 = _col(hdrs, "xGF/60")
            ci_gf    = _col(hdrs, "GF%", "GF %")
            for row in rows:
                name = row[ci_team] if ci_team >= 0 else (row[1] if len(row) > 1 else "")
                if not name: continue
                result[name] = {
                    "pp_xgf": _sf(row, ci_xgf60) if ci_xgf60 >= 0 else 0.0,
                    "pp_pct": _sf(row, ci_gf)    if ci_gf    >= 0 else 20.0,
                }
        except Exception as e:
            log.debug(f"PP/PK parse: {e}")
        return result

# ══════════════════════════════════════════════════════
# SECTION 8 — NBA STATS SCRAPER (multi-source)
# ══════════════════════════════════════════════════════
# Hardcoded 2025-26 playoff series stats (as of May 23 2026)
# These are used only when all live sources fail.
# Source: current series box scores — update if series evolves significantly.
_NBA_HARDCODED: Dict[str, dict] = {
    "Knicks":    {"off_rtg": 118.2, "def_rtg": 108.4, "net_rtg":  9.8, "pace": 96.1, "ts_pct": 0.572},
    "Cavaliers": {"off_rtg": 113.8, "def_rtg": 107.2, "net_rtg":  6.6, "pace": 94.3, "ts_pct": 0.562},
    "Thunder":   {"off_rtg": 119.5, "def_rtg": 108.6, "net_rtg": 10.9, "pace": 99.2, "ts_pct": 0.581},
    "Spurs":     {"off_rtg": 110.4, "def_rtg": 114.1, "net_rtg": -3.7, "pace": 97.8, "ts_pct": 0.543},
}

# Current playoff series records: "AWAY@HOME": (away_wins, home_wins)
# Update after each game.
_SERIES_STATE: Dict[str, Tuple[int, int]] = {
    "NYK@CLE": (2, 0),  # Knicks lead 2-0
    "OKC@SAS": (3, 0),  # Thunder lead 3-0
    "MTL@CAR": (0, 1),  # Hurricanes lead 1-0 (Game 2 at CAR)
    "VGK@COL": (0, 1),  # Avalanche lead 1-0 (Game 2 at COL)
    "COL@VGK": (1, 1),  # Series tied 1-1 (Game 3 at VGK) — update after Game 2 result
}

class CTGScraper:
    """
    NBA team stats — tries sources in order:
      1. Cleaning the Glass (paid, best)
      2. ESPN team stats API (avgPoints → off_rtg, series cross-ref for def_rtg)
      3. Stale cache
      4. Hardcoded current-series fallback (marked FALLBACK DATA)
    """
    CTG = "https://cleaningtheglass.com"

    # ESPN team IDs — active playoff teams 2025-26
    _ESPN_IDS: Dict[str, str] = {
        "Knicks": "18", "Cavaliers": "5",
        "Thunder": "25", "Spurs": "24",
        "Celtics": "2",  "Heat": "14",
        "Pacers": "11",  "Bucks": "15",
        "Nuggets": "7",  "Timberwolves": "23",
        "Warriors": "9", "Lakers": "13",
    }

    # Active series opponent pairs — used to cross-reference def_rtg
    _SERIES: List[Tuple[str, str]] = [
        ("Knicks", "Cavaliers"),
        ("Thunder", "Spurs"),
    ]

    def team_stats(self) -> Dict[str, NBATeamStats]:
        cached = _cache.get("nba_teams", CACHE_TTL["nba_teams"])
        if cached: return cached

        teams = self._try_ctg()
        if not teams:
            teams = self._try_espn()
        if not teams:
            stale = _cache.stale("nba_teams")
            if stale:
                log.warning("NBA stats: using stale cache")
                return stale
        if not teams:
            teams = self._hardcoded_fallback()

        if teams:
            _cache.set("nba_teams", teams)
        return teams

    # ── Tier 1: Cleaning the Glass ───────────────────────
    def _try_ctg(self) -> Dict[str, NBATeamStats]:
        teams: Dict[str, NBATeamStats] = {}
        try:
            url = f"{self.CTG}/stats/league/summary?season=2025-26&seasontype=Playoffs"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code in (401, 403):
                log.warning("CTG %d — subscription required", r.status_code)
                return {}
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            table = soup.find("table")
            if not table: return {}
            hdrs, rows = _parse_nst_table(table)
            ci = {
                "team":    _col(hdrs, "Team"),
                "off_rtg": _col(hdrs, "ORtg", "Off Rtg", "Offensive Rating"),
                "def_rtg": _col(hdrs, "DRtg", "Def Rtg", "Defensive Rating"),
                "pace":    _col(hdrs, "Pace"),
                "ts":      _col(hdrs, "TS%", "TS %"),
            }
            for row in rows:
                name = row[ci["team"]] if ci["team"] >= 0 else (row[0] if row else "")
                if not name: continue
                s = NBATeamStats(team=name)
                s.off_rtg = _sf(row, ci["off_rtg"]) if ci["off_rtg"] >= 0 else 110.0
                s.def_rtg = _sf(row, ci["def_rtg"]) if ci["def_rtg"] >= 0 else 110.0
                s.net_rtg = s.off_rtg - s.def_rtg
                s.pace    = _sf(row, ci["pace"])    if ci["pace"]    >= 0 else 98.0
                s.ts_pct  = _sf(row, ci["ts"])      if ci["ts"]      >= 0 else 0.56
                if s.ts_pct > 1: s.ts_pct /= 100
                teams[name] = s
            if teams: log.info(f"CTG: {len(teams)} teams")
        except Exception as e:
            log.warning(f"CTG scrape failed: {e}")
        return teams

    # ── Tier 2: ESPN team stats ──────────────────────────
    def _try_espn(self) -> Dict[str, NBATeamStats]:
        """
        Fetch avgPoints from ESPN; combine with hardcoded def_rtg + pace for
        teams where we have reliable data.

        Why this hybrid: ESPN exposes PPG (live, accurate) but not defensive
        rating or pace. The model needs off_rtg*pace = expected_pts_per_game.
        Using hardcoded pace to back-calculate off_rtg preserves ESPN's live
        scoring while keeping defensive/pace inputs accurate.
        """
        ppg: Dict[str, float] = {}
        for name, eid in self._ESPN_IDS.items():
            try:
                url = (f"https://site.api.espn.com/apis/site/v2/sports/basketball"
                       f"/nba/teams/{eid}/statistics")
                r = requests.get(url, headers=HEADERS, timeout=8)
                if r.status_code != 200: continue
                stats = r.json().get("results", {}).get("stats", {})
                for cat in stats.get("categories", []):
                    for s in cat.get("stats", []):
                        if s.get("name") == "avgPoints":
                            ppg[name] = float(s["value"])
                            break
            except Exception as e:
                log.debug(f"ESPN stats {name}: {e}")

        if not ppg:
            return {}

        teams: Dict[str, NBATeamStats] = {}
        for name, p in ppg.items():
            hc = _NBA_HARDCODED.get(name, {})
            pace = hc.get("pace", 95.0)    # hardcoded pace; default 95 for playoffs
            s = NBATeamStats(team=name)
            # off_rtg derived from live ESPN PPG + hardcoded pace so model_pts = ppg
            s.off_rtg = (p * 100.0) / pace
            s.pace    = pace
            # def_rtg from hardcoded when available; never cross-reference opponents
            # (cross-referencing confuses scoring with defensive efficiency)
            s.def_rtg = hc.get("def_rtg", 112.0)
            s.ts_pct  = hc.get("ts_pct",  0.56)
            s.net_rtg = s.off_rtg - s.def_rtg
            teams[name] = s
            src = "ESPN+hardcoded" if hc else "ESPN+default"
            log.info(f"NBA stats [{src}] {name}: off_rtg={s.off_rtg:.1f} "
                     f"def_rtg={s.def_rtg:.1f} pace={s.pace:.1f} (ppg={p:.1f})")

        return teams

    # ── Tier 3: Hardcoded fallback ───────────────────────
    def _hardcoded_fallback(self) -> Dict[str, NBATeamStats]:
        """Last resort: user-provided current series stats. Printed with warning."""
        teams: Dict[str, NBATeamStats] = {}
        for name, d in _NBA_HARDCODED.items():
            s = NBATeamStats(team=name)
            s.off_rtg = d["off_rtg"]
            s.def_rtg = d["def_rtg"]
            s.net_rtg = d["net_rtg"]
            s.pace    = d["pace"]
            s.ts_pct  = d.get("ts_pct", 0.56)
            teams[name] = s
        print(Fore.YELLOW + Style.BRIGHT +
              "  ⚠ NBA STATS: using hardcoded fallback — verify manually" +
              Style.RESET_ALL)
        log.warning("NBA stats: hardcoded fallback active")
        return teams

# ══════════════════════════════════════════════════════
# SECTION 9 — INJURY REPORTER (ESPN)
# ══════════════════════════════════════════════════════
# Player PPG values (used for injury win-prob impact calculation)
_STAR_PPG = {
    # NBA — points per game (2024-25 playoffs)
    "Nikola Jokic": 29.6, "Luka Doncic": 28.7, "Giannis Antetokounmpo": 30.4,
    "Joel Embiid": 24.6, "Stephen Curry": 26.4, "LeBron James": 23.7,
    "Kevin Durant": 26.9, "Jayson Tatum": 26.9, "Anthony Davis": 26.2,
    "Kawhi Leonard": 23.7, "Damian Lillard": 24.8, "Devin Booker": 25.8,
    "Jalen Williams": 24.3, "Dylan Harper": 8.5, "De'Aaron Fox": 25.6,
    "Shai Gilgeous-Alexander": 32.7, "Chet Holmgren": 14.5,
    "Victor Wembanyama": 22.2,   # 2024-25 playoffs
    "Karl-Anthony Towns": 21.8, "Donovan Mitchell": 26.2,
    "Evan Mobley": 18.6, "Tyrese Haliburton": 20.1, "Pascal Siakam": 21.0,
    "Paolo Banchero": 24.6, "Franz Wagner": 23.1, "Jaren Jackson Jr.": 23.6,
    "Zion Williamson": 22.9, "CJ McCollum": 20.9,
    # Current playoff active rosters (2025 playoffs)
    "Jalen Brunson": 26.6,      # NYK PG, series vs CLE
    "OG Anunoby": 14.5,         # NYK SF
    "Josh Hart": 11.5,          # NYK SF/SG — rebounding specialist
    "Mikal Bridges": 13.8,      # NYK SG/SF
    "Jarrett Allen": 14.2,      # CLE C
    "Darius Garland": 21.7,     # CLE PG
    "Max Strus": 11.0,          # CLE SG
    "Isaac Okoro": 9.5,         # CLE SF
    "Devin Vassell": 19.5,      # SAS SF, series vs OKC
    "Stephon Castle": 11.2,     # SAS PG (rookie)
    "Julian Champagnie": 8.5,   # SAS SF
    "Tre Jones": 8.0,           # SAS PG
    "Luguentz Dort": 11.5,      # OKC SG (3&D)
    "Isaiah Hartenstein": 11.8, # OKC C
    "Cason Wallace": 9.5,       # OKC SG (sophomore)
    "Alex Caruso": 8.2,         # OKC SG (veteran)
    "Aaron Wiggins": 8.5,       # OKC SG
    # Colorado / Vegas NHL stars (VGK @ COL)
    "Nathan MacKinnon": 1.63, "Cale Makar": 1.22, "Mikko Rantanen": 1.30,
    "Jack Eichel": 0.95, "Mark Stone": 0.78, "William Karlsson": 0.62,
    # NHL — points per game (goals + assists proxy)
    "Connor McDavid": 1.82, "David Pastrnak": 1.10,
    "Auston Matthews": 1.18, "Leon Draisaitl": 1.43,
    "Sidney Crosby": 1.03, "Alex Ovechkin": 0.75, "Erik Karlsson": 0.85,
    "Artemi Panarin": 1.05, "Matthew Tkachuk": 1.12,
    "Sebastian Aho": 0.90, "Andrei Svechnikov": 0.82,
}

# Team PPG (approximate 2024-25 regular season)
_TEAM_PPG = {
    # NBA
    "Thunder": 119.5, "Spurs": 113.2, "Cavaliers": 117.4, "Knicks": 115.6,
    "Celtics": 122.3, "Heat": 110.8, "Pacers": 121.7, "Bucks": 116.4,
    "Nuggets": 116.1, "Timberwolves": 112.3, "Warriors": 115.7, "Lakers": 113.8,
    "Suns": 113.4, "Kings": 116.2, "Mavericks": 117.8, "Rockets": 113.1,
    "Nets": 109.4, "Grizzlies": 114.7, "Pelicans": 109.9, "Magic": 109.0,
    "Hawks": 116.0, "Wizards": 105.3, "76ers": 112.4, "Clippers": 112.8,
    "Jazz": 111.5, "Blazers": 107.4, "Pistons": 111.9, "Hornets": 107.6,
    "Bulls": 110.0, "Raptors": 106.7,
    # NHL (goals per game × 2 for both teams context; actual goals per game)
    "Avalanche": 3.42, "Oilers": 3.38, "Panthers": 3.23, "Rangers": 3.15,
    "Hurricanes": 3.05, "Lightning": 3.10, "Golden Knights": 3.18,
    "Bruins": 3.02, "Maple Leafs": 3.19, "Flames": 2.95, "Jets": 3.22,
    "Wild": 2.88, "Canucks": 3.01, "Ducks": 2.71, "Sharks": 2.60,
    "Blues": 2.85, "Predators": 2.79, "Blue Jackets": 2.68, "Sabres": 2.77,
    "Senators": 2.89, "Flyers": 2.83, "Penguins": 2.90, "Capitals": 2.96,
    "Islanders": 2.72, "Devils": 2.93, "Canadiens": 2.78,
    "Kraken": 2.82, "Stars": 3.07, "Coyotes": 2.56,
}

class InjuryReporter:
    ESPN     = "https://site.api.espn.com/apis/site/v2/sports"
    NBA_INJ  = "https://www.nba.com/players/injuries"

    def fetch(self) -> List[InjuryReport]:
        cached = _cache.get("injuries_both", CACHE_TTL["injuries"])
        if cached: return cached
        reports = []
        reports.extend(self._espn_nba())
        reports.extend(self._espn_nhl())
        reports.extend(self._nba_injury_page())
        # Deduplicate by player name
        seen = set()
        deduped = []
        for r in reports:
            key = (r.player.lower(), r.sport)
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        if deduped:
            _cache.set("injuries_both", deduped)
        return deduped

    def _calc_impact(self, player: str, team: str, status: str, sport: str) -> InjuryReport:
        ppg = _STAR_PPG.get(player, 8.0)
        # Lookup team PPG — try fuzzy match
        team_ppg = 0.0
        for t_name, t_ppg in _TEAM_PPG.items():
            if _fuzzy(team, t_name):
                team_ppg = t_ppg
                break
        if team_ppg == 0.0:
            team_ppg = 113.0 if sport == "NBA" else 3.0
        mult = {"OUT": 0.30, "DOUBTFUL": 0.22, "QUESTIONABLE": 0.15}.get(status, 0.0)
        # win_prob_impact: negative = hurts injured team
        win_impact = -(ppg / team_ppg) * mult
        # total impact: OUT player → subtract PPG×0.7 from expected total
        total_impact = ppg * 0.7 if status == "OUT" else ppg * 0.4 if status == "DOUBTFUL" else ppg * 0.2
        return InjuryReport(
            player=player, team=team, sport=sport, status=status,
            injury="", bpm_impact=ppg,
            win_prob_impact=win_impact,
            player_ppg=ppg, total_ppg_impact=total_impact,
        )

    def _espn_nba(self) -> List[InjuryReport]:
        return self._espn_fetch("basketball", "nba", "NBA")

    def _espn_nhl(self) -> List[InjuryReport]:
        return self._espn_fetch("icehockey", "nhl", "NHL")

    def _espn_fetch(self, sport: str, league: str, sport_label: str) -> List[InjuryReport]:
        out = []
        try:
            r = requests.get(f"{self.ESPN}/{sport}/{league}/injuries",
                             headers=HEADERS, timeout=12)
            r.raise_for_status()
            for entry in r.json().get("injuries", []):
                team = entry.get("team", {}).get("displayName", "")
                for inj in entry.get("injuries", []):
                    player = inj.get("athlete", {}).get("displayName", "")
                    status = inj.get("status", "").upper()
                    if status not in ("OUT", "DOUBTFUL", "QUESTIONABLE"): continue
                    rep = self._calc_impact(player, team, status, sport_label)
                    rep.injury = inj.get("type", {}).get("abbreviation", "")
                    out.append(rep)
        except Exception as e:
            log.warning(f"ESPN {league} injuries: {e}")
        return out

    def _nba_injury_page(self) -> List[InjuryReport]:
        """Scrape NBA official injury report (JSON embedded in page)."""
        out = []
        try:
            r = requests.get(
                "https://cdn.nba.com/static/json/staticData/rotowire/InjuryReport_V2.json",
                headers={**HEADERS, "Referer": "https://www.nba.com/"},
                timeout=15)
            r.raise_for_status()
            data = r.json()
            # Format: list of {FirstName, LastName, Team, Status, Reason}
            for item in data if isinstance(data, list) else data.get("InjuryList", []):
                first = item.get("FirstName", "")
                last  = item.get("LastName", "")
                player = f"{first} {last}".strip()
                team   = item.get("Team", "")
                status = item.get("CurrentStatus", item.get("Status", "")).upper()
                if not player or status not in ("OUT", "DOUBTFUL", "QUESTIONABLE"):
                    continue
                rep = self._calc_impact(player, team, status, "NBA")
                rep.injury = item.get("Reason", "")
                out.append(rep)
        except Exception as e:
            log.debug(f"NBA injury JSON: {e}")
        return out

    def injury_edge_flags(self, injuries: List[InjuryReport], team_name: str) -> List[str]:
        """Return formatted INJURY EDGE strings for a team."""
        flags = []
        for inj in injuries:
            if not _fuzzy(inj.team, team_name): continue
            if inj.status not in ("OUT", "DOUBTFUL", "QUESTIONABLE"): continue
            pct = abs(inj.win_prob_impact) * 100
            flags.append(
                f"INJURY EDGE: {inj.player} {inj.status} → "
                f"{team_name.split()[-1]} -{pct:.1f}% win prob | "
                f"Market price may not reflect this yet"
            )
        return flags

# ══════════════════════════════════════════════════════
# SECTION 9b — LIVE SCORE FETCHER (ESPN)
# ══════════════════════════════════════════════════════
class LiveScoreFetcher:
    ESPN = "https://site.api.espn.com/apis/site/v2/sports"

    def fetch(self) -> Dict[str, LiveGame]:
        games: Dict[str, LiveGame] = {}
        for sport, league, periods, period_mins in [
            ("basketball", "nba", 4, 12),
            ("hockey",     "nhl", 3, 20),
        ]:
            try:
                r = requests.get(f"{self.ESPN}/{sport}/{league}/scoreboard",
                                 headers=HEADERS, timeout=10)
                r.raise_for_status()
                for ev in r.json().get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    status_type = comp.get("status", {}).get("type", {})
                    state = status_type.get("state", "pre")   # pre/in/post

                    competitors = comp.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})

                    home_abbr = home.get("team", {}).get("abbreviation", "")
                    away_abbr = away.get("team", {}).get("abbreviation", "")
                    home_score = int(home.get("score", 0) or 0)
                    away_score = int(away.get("score", 0) or 0)

                    # Period and clock
                    period = comp.get("status", {}).get("period", 1) or 1
                    clock  = comp.get("status", {}).get("displayClock", "") or ""

                    # Fraction of game elapsed
                    total_periods = periods
                    if state == "post":
                        pct = 1.0
                    elif state == "pre":
                        pct = 0.0
                    else:
                        mins_done = (period - 1) * period_mins
                        # Parse clock "MM:SS"
                        try:
                            parts = clock.split(":")
                            secs_left = int(parts[0]) * 60 + int(parts[1])
                            mins_done += (period_mins - secs_left / 60)
                        except Exception:
                            mins_done += period_mins / 2
                        pct = min(1.0, mins_done / (total_periods * period_mins))

                    key = f"{away_abbr}@{home_abbr}"
                    games[key] = LiveGame(
                        game_id=ev.get("id", key),
                        home_abbr=home_abbr, away_abbr=away_abbr,
                        sport=league.upper(),
                        home_score=home_score, away_score=away_score,
                        period=period, clock=clock,
                        status=state, pct_elapsed=pct,
                    )
            except Exception as e:
                log.warning(f"LiveScoreFetcher {league}: {e}")
        return games

    def live_win_prob(self, game: LiveGame, base_home_prob: float) -> float:
        """
        Adjust win probability based on current score and time elapsed.
        Uses log5 / momentum model:
          - Score differential pulls probability toward 0 or 1
          - More time elapsed = larger pull
        """
        if game.status == "post":
            return 1.0 if game.home_score > game.away_score else 0.0
        if game.status == "pre" or game.pct_elapsed < 0.01:
            return base_home_prob

        diff = game.home_score - game.away_score  # positive = home leading
        # Each goal/point is worth more as time runs out
        sport = game.sport
        if sport == "NHL":
            # ~2.5 goals per 60min in regulation; at 50% elapsed, 1 goal = ~+15% swing
            per_unit = 0.15 / (1 - game.pct_elapsed + 0.1)
            per_unit = min(per_unit, 0.45)
            adj = diff * per_unit
        else:
            # NBA: ~1 pt = ~1% early, grows as time runs out
            per_unit = 0.01 / (1 - game.pct_elapsed + 0.05)
            per_unit = min(per_unit, 0.04)
            adj = diff * per_unit

        p = base_home_prob + adj
        return float(np.clip(p, 0.02, 0.98))

# ══════════════════════════════════════════════════════
# SECTION 9b2 — REST DAY FETCHER (ESPN)
# ══════════════════════════════════════════════════════
class RestDayFetcher:
    """Looks back up to 10 days on ESPN scoreboard to find each team's last game date."""
    ESPN = "https://site.api.espn.com/apis/site/v2/sports"

    def fetch(self) -> Dict[str, Tuple[int, str]]:
        """Returns {team_abbr_upper: (rest_days, 'May 21')} for all recently active teams."""
        result: Dict[str, Tuple[int, str]] = {}
        today = datetime.now().date()
        for sport, league in [("basketball", "nba"), ("hockey", "nhl")]:
            for days_ago in range(1, 11):
                d = today - timedelta(days=days_ago)
                date_str = d.strftime("%Y%m%d")
                try:
                    r = requests.get(
                        f"{self.ESPN}/{sport}/{league}/scoreboard",
                        params={"dates": date_str},
                        headers=HEADERS, timeout=10)
                    r.raise_for_status()
                    for ev in r.json().get("events", []):
                        comp = ev.get("competitions", [{}])[0]
                        state = comp.get("status", {}).get("type", {}).get("state", "")
                        if state not in ("post", "in"):
                            continue
                        for competitor in comp.get("competitors", []):
                            abbr = competitor.get("team", {}).get("abbreviation", "").upper()
                            if abbr and abbr not in result:
                                played_str = d.strftime("%b") + f" {d.day}"
                                result[abbr] = (days_ago, played_str)
                except Exception as e:
                    log.debug(f"RestDayFetcher {league} {date_str}: {e}")
        return result

class NHLStandingsFetcher:
    """Pulls current regular-season points% from the NHL API for all 32 teams."""
    URL = "https://api-web.nhle.com/v1/standings/now"

    def fetch(self) -> Dict[str, float]:
        """Returns {ABBR: points_pct} e.g. {'VGK': 0.579, 'COL': 0.738}"""
        try:
            r = requests.get(self.URL, headers=HEADERS, timeout=10, allow_redirects=True)
            r.raise_for_status()
            result: Dict[str, float] = {}
            for entry in r.json().get("standings", []):
                abbr = entry.get("teamAbbrev", {}).get("default", "")
                pct  = float(entry.get("pointPctg", 0.5))
                if abbr:
                    result[abbr.upper()] = round(pct, 4)
            log.info(f"NHL standings: {len(result)} teams fetched")
            return result
        except Exception as e:
            log.warning(f"NHLStandingsFetcher failed: {e}")
            return {}

# ══════════════════════════════════════════════════════
# SECTION 9c — HISTORICAL BASE RATES
# ══════════════════════════════════════════════════════
_HIST_RATES_FILE = CACHE_DIR / "hist_rates.json"

# Hard-coded empirical rates derived from 3 years of playoffs
# (scraped on demand and cached; these are the fallback defaults)
# Defaults seeded from 3 seasons of real playoff data (2022-25)
# Marked with † where confirmed by API; unmarked = literature estimate
_DEFAULT_HIST = {
    "nhl_home_win_pct":              0.515,   # † 135/262 games
    "nhl_home_win_rest_plus1":       0.535,   # estimated (no rest data in API)
    "nhl_home_win_rest_plus2":       0.555,   # estimated
    "nhl_under_after_ot":            0.600,   # estimated (literature)
    "nhl_under_high_combined_gsax":  0.640,   # estimated
    "nhl_series_leader_win_pct":     0.590,   # estimated
    "nhl_avg_goals":                 6.07,    # † 262 games
    "nhl_under_5_5":                 0.431,   # † games with ≤5 goals
    "nhl_under_6_5":                 0.565,   # † games with ≤6 goals
    "nba_home_win_pct":              0.584,   # † 146/250 games
    "nba_home_win_rest_plus1":       0.600,   # estimated
    "nba_home_win_rest_plus2":       0.615,   # estimated
    "nba_under_after_ot":            0.580,   # estimated
    "nba_series_leader_win_pct":     0.600,   # estimated
    "nba_avg_total":                 216.0,   # † 250 games median=216
    "nba_under_215":                 0.456,   # † games finishing under 215
    "nba_under_218":                 0.552,   # † games finishing under 218
    "nba_under_220":                 0.588,   # † games finishing under 220
}

class HistoricalRates:
    """Scrapes basketball-reference / hockey-reference for real playoff rates."""

    def rates(self) -> dict:
        if _HIST_RATES_FILE.exists():
            try:
                d = json.loads(_HIST_RATES_FILE.read_text())
                if d.get("scraped_at", ""):
                    age_days = (datetime.now() - datetime.fromisoformat(d["scraped_at"])).days
                    if age_days < 30:
                        return d
            except Exception:
                pass
        scraped = self._scrape()
        rates = {**_DEFAULT_HIST, **scraped, "scraped_at": datetime.now().isoformat()}
        try: _HIST_RATES_FILE.write_text(json.dumps(rates, indent=2))
        except Exception: pass
        return rates

    def _scrape(self) -> dict:
        result = {}
        result.update(self._bref_nba())
        result.update(self._href_nhl())
        return result

    def _bref_nba(self) -> dict:
        """Pull from NBA Stats API game logs to calculate real playoff rates."""
        out = {}
        home_wins = home_total = 0
        rest_bins = {"0":[],"1":[],"2+":[], "vs_0":[],"vs_1":[],"vs_2+":[]}
        ot_games_idx = []
        under_after_ot = total_after_ot = 0

        nba_headers = {**HEADERS,
                       "Referer": "https://www.nba.com/",
                       "x-nba-stats-origin": "stats",
                       "x-nba-stats-token": "true"}

        for season in ["2024-25", "2023-24", "2022-23"]:
            try:
                url = (f"https://stats.nba.com/stats/leaguegamelog"
                       f"?Season={season}&SeasonType=Playoffs&PlayerOrTeam=T"
                       f"&Counter=1000&Direction=DESC&Sorter=DATE")
                r = requests.get(url, headers=nba_headers, timeout=25)
                if r.status_code != 200: continue
                data = r.json()
                rs   = data.get("resultSets", [{}])[0]
                hdrs = rs.get("headers", [])
                rows = rs.get("rowSet", [])
                if not hdrs: continue

                d_rows = [dict(zip(hdrs, row)) for row in rows]
                # Pair home/away by game_id
                by_game: Dict[str, list] = {}
                for d in d_rows:
                    gid = d.get("GAME_ID", "")
                    by_game.setdefault(gid, []).append(d)

                for gid, pair in by_game.items():
                    if len(pair) != 2: continue
                    home_team = next((p for p in pair if "@" not in p.get("MATCHUP","")), None)
                    away_team = next((p for p in pair if "@" in p.get("MATCHUP","")), None)
                    if not home_team or not away_team: continue

                    home_pts = int(home_team.get("PTS", 0) or 0)
                    away_pts = int(away_team.get("PTS", 0) or 0)
                    home_win = home_team.get("WL","") == "W"
                    total    = home_pts + away_pts

                    home_total += 1
                    if home_win: home_wins += 1

                log.info(f"NBA bref {season}: {len(by_game)} games parsed")
            except Exception as e:
                log.debug(f"NBA stats API {season}: {e}")

        if home_total >= 10:
            out["nba_home_win_pct"] = round(home_wins / home_total, 3)
            log.info(f"NBA historical home win pct: {out['nba_home_win_pct']:.3f} ({home_wins}/{home_total})")
        return out

    def _href_nhl(self) -> dict:
        """Pull from NHL open API for playoff game rates."""
        out = {}
        home_wins = home_total = 0
        goals_list = []

        for season_code in [20242025, 20232024, 20222023]:
            try:
                url = (f"https://api.nhle.com/stats/rest/en/game"
                       f"?cayenneExp=gameType=3%20and%20season={season_code}"
                       f"&limit=500&start=0")
                r = requests.get(url, headers=HEADERS, timeout=25)
                if r.status_code != 200: continue
                data = r.json()
                games = data.get("data", [])
                for g in games:
                    hs  = int(g.get("homeScore", g.get("homeTeamScore", 0)) or 0)
                    as_ = int(g.get("visitingScore", g.get("visitingTeamScore", 0)) or 0)
                    if hs == 0 and as_ == 0: continue   # not played yet
                    home_total += 1
                    if hs > as_: home_wins += 1
                    goals_list.append(hs + as_)
                log.info(f"NHL API {season_code}: {len(games)} games")
            except Exception as e:
                log.debug(f"NHL API {season_code}: {e}")

        if home_total >= 10:
            out["nhl_home_win_pct"] = round(home_wins / home_total, 3)
            log.info(f"NHL historical home win pct: {out['nhl_home_win_pct']:.3f}")
        if goals_list:
            import statistics
            med = statistics.median(goals_list)
            under_pct = sum(1 for g in goals_list if g <= med) / len(goals_list)
            out["nhl_under_overall"] = round(under_pct, 3)
            out["nhl_avg_goals"] = round(sum(goals_list)/len(goals_list), 2)
        return out

    def coeff_comparison(self, rates: dict) -> str:
        """Print table of old hardcoded vs new historical coefficient values."""
        # OLD = original hardcoded assumptions; NEW = from API game logs
        rows = [
            ("NHL home win base",      0.570,  rates.get("nhl_home_win_pct",      0.515)),
            ("NHL home win +1 rest",   0.595,  rates.get("nhl_home_win_rest_plus1",0.535)),
            ("NHL home win +2 rest",   0.615,  rates.get("nhl_home_win_rest_plus2",0.555)),
            ("NHL under after OT",     0.620,  rates.get("nhl_under_after_ot",     0.600)),
            ("NHL series leader win",  0.600,  rates.get("nhl_series_leader_win_pct",0.590)),
            ("NHL avg goals/game",     5.50,   rates.get("nhl_avg_goals",          6.07)),
            ("NHL P(≤5 goals)",        0.387,  rates.get("nhl_under_5_5",          0.431)),
            ("NHL P(≤6 goals)",        0.500,  rates.get("nhl_under_6_5",          0.565)),
            ("NBA home win base",      0.540,  rates.get("nba_home_win_pct",       0.584)),
            ("NBA home win +1 rest",   0.558,  rates.get("nba_home_win_rest_plus1",0.600)),
            ("NBA home win +2 rest",   0.575,  rates.get("nba_home_win_rest_plus2",0.615)),
            ("NBA avg total pts",      213.0,  rates.get("nba_avg_total",          216.0)),
            ("NBA P(under 215)",       0.450,  rates.get("nba_under_215",          0.456)),
            ("NBA P(under 218)",       0.500,  rates.get("nba_under_218",          0.552)),
            ("NBA under after OT",     0.610,  rates.get("nba_under_after_ot",     0.580)),
            ("NBA series leader win",  0.580,  rates.get("nba_series_leader_win_pct",0.600)),
        ]
        lines = [
            "",
            Fore.WHITE + Style.BRIGHT + "═" * 60,
            "  COEFFICIENT COMPARISON  (OLD assumed → NEW historical)".center(60),
            "  " + "─" * 58,
            f"  {'Coefficient':<32} {'OLD':>8} {'NEW':>8} {'Δ':>8}",
            "  " + "─" * 58,
        ]
        for name, old, new in rows:
            delta = new - old
            col = Fore.GREEN if abs(delta) > 0.005 else Style.RESET_ALL
            lines.append(col + f"  {name:<32} {old:>8.3f} {new:>8.3f} {delta:>+8.3f}" + Style.RESET_ALL)
        lines.append(Fore.WHITE + Style.BRIGHT + "═" * 60)
        return "\n".join(lines)

# ══════════════════════════════════════════════════════
# SECTION 10 — KALSHI API CLIENT
# ══════════════════════════════════════════════════════

# Kalshi uses 3-letter abbreviations in their ticker format.
# Ticker structure:
#   ML:    KXNBAGAME-26MAY22OKCSAS-SAS   (away=OKC, home=SAS, YES=SAS wins)
#   TOTAL: KXNBATOTAL-26MAY22OKCSAS-218  (away=OKC, home=SAS, YES=over 218 pts)
_ABBR = {
    # NBA
    "OKC":"Thunder",    "SAS":"Spurs",      "NYK":"Knicks",
    "CLE":"Cavaliers",  "BOS":"Celtics",    "MIA":"Heat",
    "PHI":"76ers",      "MIL":"Bucks",      "IND":"Pacers",
    "ATL":"Hawks",      "CHA":"Hornets",    "DET":"Pistons",
    "TOR":"Maple Leafs","GSW":"Warriors",   "LAL":"Lakers",
    "LAC":"Clippers",   "PHX":"Suns",       "SAC":"Kings",
    "DEN":"Nuggets",    "MIN":"Timberwolves","POR":"Blazers",
    "UTA":"Jazz",       "MEM":"Grizzlies",  "DAL":"Mavericks",
    "HOU":"Rockets",    "NOP":"Pelicans",   "ORL":"Magic",
    "WAS":"Wizards",    "CHI":"Bulls",      "BKN":"Nets",
    # NHL (overrides for shared abbrevs like TOR, MIN, DAL, DET, PHI)
    "CAR":"Hurricanes", "MTL":"Canadiens",  "COL":"Avalanche",
    "VGK":"Golden Knights","TBL":"Lightning","FLA":"Panthers",
    "EDM":"Oilers",     "CGY":"Flames",     "VAN":"Canucks",
    "SEA":"Kraken",     "ANA":"Ducks",      "LAK":"Kings",
    "SJS":"Sharks",     "STL":"Blues",      "NSH":"Predators",
    "WPG":"Jets",       "CBJ":"Blue Jackets","OTT":"Senators",
    "NYR":"Rangers",    "NYI":"Islanders",  "NJD":"Devils",
    "WSH":"Capitals",   "PIT":"Penguins",   "BUF":"Sabres",
}

# Kalshi player abbreviation → full name (for prop market parsing)
_PROP_PLAYER_MAP = {
    "WEMB":    "Victor Wembanyama",
    "SGA":     "Shai Gilgeous-Alexander",
    "JWILL":   "Jalen Williams",
    "JALEN":   "Jalen Williams",
    "DFOX":    "De'Aaron Fox",
    "FOX":     "De'Aaron Fox",
    "CHET":    "Chet Holmgren",
    "HOLMGR":  "Chet Holmgren",
    "DHARP":   "Dylan Harper",
    "HARPER":  "Dylan Harper",
    "JOKIC":   "Nikola Jokic",
    "LUKA":    "Luka Doncic",
    "TATUM":   "Jayson Tatum",
    "CURRY":   "Stephen Curry",
    "DURANT":  "Kevin Durant",
    "GIANNIS": "Giannis Antetokounmpo",
    "LEBRON":  "LeBron James",
    "BOOKER":  "Devin Booker",
    "MDAV":    "Anthony Davis",
    "MITCH":   "Donovan Mitchell",
    "MOBLEY":  "Evan Mobley",
    "MCDAVID": "Connor McDavid",
    "MACKINN": "Nathan MacKinnon",
    "MAKAR":   "Cale Makar",
}

class KalshiClient:
    # Correct base URL (api.kalshi.com returns empty responses)
    BASE = "https://api.elections.kalshi.com/trade-api/v2"

    # Series to fetch: moneyline + totals + spreads + player props
    _SERIES = [
        "KXNBAGAME",    "KXNHLGAME",      # moneylines
        "KXNBATOTAL",   "KXNHLTOTAL",     # game totals
        "KXNBAATS",     "KXNHLPUCKLINE",  # spreads / puck lines
        "KXNBASPREAD",  "KXNHLSPREAD",    # alternate spread series names
        "KXNBAPTS",     "KXNBAREBS",      # player props (points, rebounds)
        "KXNBAAST",     "KXNHLGOALS",     # player props (assists, goals)
    ]

    def __init__(self, api_key: str = ""):
        self.key = api_key or os.getenv("KALSHI_API_KEY", "")
        self.sess = requests.Session()
        if self.key:
            self.sess.headers["Authorization"] = f"Bearer {self.key}"
        self.sess.headers.update(HEADERS)

    # ── low-level GET with retry ─────────────────────────
    def _get(self, ep: str, params: dict = None, retries=3) -> Optional[dict]:
        for n in range(retries):
            try:
                r = self.sess.get(f"{self.BASE}{ep}", params=params, timeout=15)
                if r.status_code == 401:
                    log.warning("Kalshi 401 — set KALSHI_API_KEY"); return None
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return r.json()
            except Exception as e:
                log.warning(f"Kalshi {ep} attempt {n+1}: {e}")
                if n < retries - 1: time.sleep(2 ** n)
        log.error(f"Kalshi {ep} failed after {retries} retries")
        return None

    # ── main entry point ─────────────────────────────────
    def markets(self) -> List[KalshiMarket]:
        cached = _cache.get("kalshi_markets", CACHE_TTL["kalshi"])
        if cached: return cached

        raw_mkts: List[dict] = []
        for series in self._SERIES:
            # Paginate through all open markets for this series
            cursor = None
            for _ in range(10):  # max 10 pages
                params = {"status": "open", "series_ticker": series, "limit": 200}
                if cursor: params["cursor"] = cursor
                data = self._get("/markets", params)
                if not data: break
                raw_mkts.extend(data.get("markets", []))
                cursor = data.get("cursor")
                if not cursor: break

        result = self._build_markets(raw_mkts)
        self._record_history(result)
        if result: _cache.set("kalshi_markets", result)
        return result

    # ── convert raw market dicts → KalshiMarket objects ─
    def _build_markets(self, raw: List[dict]) -> List[KalshiMarket]:
        # Primary filter: only games scheduled for TODAY.
        # Use ESPN scoreboard as the authoritative source; fall back to ticker-date-only.
        today_local = datetime.now().date()
        today_games = self._espn_today_games()   # e.g. {"NYK@CLE", "MTL@CAR"}
        if today_games:
            log.info(f"ESPN today filter: {today_games}")
        else:
            log.warning("ESPN today games returned empty — falling back to ticker-date filter only")

        ml_mkts:    List[KalshiMarket] = []
        spread_mkts: List[KalshiMarket] = []
        prop_mkts:  List[KalshiMarket] = []
        total_groups:  Dict[str, List[dict]] = {}
        spread_groups: Dict[str, List[dict]] = {}  # key: "{event_part}-{win_team}"

        for m in raw:
            tk = m.get("ticker", "").upper()
            if not tk: continue

            # ── Date filter: skip any game not scheduled for today ──────────
            ticker_date = self._ticker_date(tk)
            if ticker_date is not None and ticker_date != today_local:
                log.debug(f"skip {tk}: date {ticker_date} ≠ today {today_local}")
                continue

            # ── ESPN whitelist: if we have today's games, reject unknown matchups ──
            if today_games:
                parts_tk = tk.split("-")
                if len(parts_tk) >= 2:
                    ep = parts_tk[1]  # event part e.g. "26MAY23NYKCLE"
                    if len(ep) >= 6:
                        away_ab = ep[-6:-3]
                        home_ab = ep[-3:]
                        matchup = f"{away_ab}@{home_ab}"
                        if matchup not in today_games:
                            log.debug(f"skip {tk}: matchup {matchup} not in ESPN today")
                            continue

            # Route by series type
            if any(s in tk for s in ("TOTAL",)):
                ev = m.get("event_ticker", m.get("ticker","").rsplit("-", 1)[0])
                total_groups.setdefault(ev, []).append(m)
            elif any(s in tk for s in ("ATS", "PUCKLINE", "SPREAD")):
                # Group by event+winteam; pick the 1-2 lines closest to 0.50 per team
                sp_parts = tk.split("-")
                if len(sp_parts) >= 3 and len(sp_parts[-1]) >= 4:
                    grp_key = f"{sp_parts[-2]}-{sp_parts[-1][:3]}"
                else:
                    grp_key = tk
                spread_groups.setdefault(grp_key, []).append(m)
            elif any(s in tk for s in ("PTS", "REBS", "AST", "GOALS", "ASSISTS", "REBOUNDS")):
                pass  # props disabled — focus on ML / spread / total only
            else:
                # Moneyline
                parsed = self._parse_ml(m)
                if parsed: ml_mkts.append(parsed)

        # For each game's totals, keep only lines closest to 0.50
        total_mkts: List[KalshiMarket] = []
        for ev_tk, group in total_groups.items():
            candidates = sorted(group,
                key=lambda m: abs((self._price(m) or 0.5) - 0.50))
            for mkt_raw in candidates[:2]:
                best = self._best_total(ev_tk, [mkt_raw])
                if best: total_mkts.append(best)

        # For each team per game, keep the 1-2 spread lines closest to 0.50
        for grp_key, group in spread_groups.items():
            candidates = sorted(group,
                key=lambda m: abs((self._price(m) or 0.5) - 0.50))
            for mkt_raw in candidates[:2]:
                parsed = self._parse_spread(mkt_raw)
                if parsed: spread_mkts.append(parsed)

        pass
        return ml_mkts + total_mkts + spread_mkts + prop_mkts

    # ── parse a moneyline market ─────────────────────────
    def _parse_ml(self, m: dict) -> Optional[KalshiMarket]:
        try:
            ticker = m.get("ticker", "")
            # e.g. KXNBAGAME-26MAY22OKCSAS-SAS
            #      KXNHLGAME-26MAY25CARMTL-MTL
            parts = ticker.split("-")
            if len(parts) < 3: return None

            event_part = parts[-2]           # e.g. "26MAY22OKCSAS" or "26MAY25CARMTL"
            bet_abbr   = parts[-1]           # e.g. "SAS" or "MTL" (YES = this team wins)

            # Extract 3+3 team abbrs from end of event_part
            away_abbr = event_part[-6:-3]
            home_abbr = event_part[-3:]

            if len(away_abbr) != 3 or len(home_abbr) != 3: return None

            sport = "NBA" if "NBA" in ticker.upper() else "NHL"
            price = self._price(m)
            if price is None: return None

            yes_side = "HOME" if bet_abbr == home_abbr else "AWAY"
            title = m.get("title", f"{away_abbr} @ {home_abbr}")

            gt = self._game_time(m)
            return KalshiMarket(
                ticker=ticker, title=title, sport=sport,
                home_team=_ABBR.get(home_abbr, home_abbr),
                away_team=_ABBR.get(away_abbr, away_abbr),
                home_abbr=home_abbr, away_abbr=away_abbr,
                market_type="ML", yes_price=price, yes_side=yes_side,
                volume=float(m.get("volume_fp", 0) or 0),
                game_time=gt,
            )
        except Exception as e:
            log.debug(f"parse_ml {m.get('ticker')}: {e}")
            return None

    # ── parse a spread / puck-line market ───────────────
    def _parse_spread(self, m: dict) -> Optional[KalshiMarket]:
        """
        Actual Kalshi format (confirmed via API probe):
          KXNBASPREAD-26MAY22OKCSAS-OKC5   YES = OKC wins by 5.5+ pts
          KXNBASPREAD-26MAY22OKCSAS-SAS3   YES = SAS wins by 3.5+ pts
          KXNHLSPREAD-26MAY22VGKCOL-COL1   YES = COL wins by 1.5+ goals
          KXNHLSPREAD-26MAY22VGKCOL-VGK2   YES = VGK wins by 2.5+ goals

        Format: {SERIES}-{DATE+AWAY+HOME}-{WINTEAM3}{INTEGER}
        actual_line = INTEGER + 0.5  (e.g. 5 → 5.5 points)

        spread_line sign convention fed to the models:
          NBA NBAModel.spread() computes P(home_margin > spread_line)
            HOME_COVER: spread_line = +actual_line  (home wins by X+)
            AWAY_COVER: spread_line = -actual_line  (away wins by X+, home_margin < -X)
          NHL NHLModel.puck_line() uses negative=home-fav, positive=home-dog
            HOME_COVER: spread_line = -actual_line  (home fav, must win by X+)
            AWAY_COVER: spread_line = +actual_line  (home dog, away wins by X+)
        """
        try:
            ticker = m.get("ticker", "")
            parts = ticker.split("-")
            if len(parts) < 3: return None

            price = self._price(m)
            if price is None: return None

            sport = "NBA" if "NBA" in ticker.upper() else "NHL"

            # Last part: 3-char team + integer margin, e.g. "OKC5", "SAS14", "COL1"
            last_part = parts[-1].upper()
            if len(last_part) < 4: return None
            win_team = last_part[:3]
            try:
                margin_n = int(last_part[3:])
            except ValueError:
                return None
            actual_line = float(margin_n) + 0.5  # e.g. 5 → 5.5

            # Event part: e.g. "26MAY22OKCSAS" → away=OKC, home=SAS
            event_part = parts[-2].upper()
            if len(event_part) < 6: return None
            away_abbr = event_part[-6:-3]
            home_abbr = event_part[-3:]
            if len(away_abbr) != 3 or len(home_abbr) != 3: return None

            # Validate win_team matches one of the two teams
            if win_team not in (away_abbr, home_abbr):
                log.debug(f"spread skip: {win_team} not in {away_abbr}@{home_abbr} ({ticker})")
                return None

            is_home_win = (win_team == home_abbr)
            yes_side = "HOME_COVER" if is_home_win else "AWAY_COVER"

            if sport == "NBA":
                spread_line = actual_line if is_home_win else -actual_line
            else:  # NHL
                spread_line = -actual_line if is_home_win else actual_line

            title = m.get("title",
                f"{away_abbr} @ {home_abbr} — {win_team} wins by {actual_line:.1f}+")
            gt = self._game_time(m)

            return KalshiMarket(
                ticker=ticker, title=title, sport=sport,
                home_team=_ABBR.get(home_abbr, home_abbr),
                away_team=_ABBR.get(away_abbr, away_abbr),
                home_abbr=home_abbr, away_abbr=away_abbr,
                market_type="SPREAD", yes_price=price, yes_side=yes_side,
                spread_line=spread_line, spread_team=win_team,
                volume=float(m.get("volume_fp", 0) or 0),
                game_time=gt,
            )
        except Exception as e:
            log.debug(f"parse_spread {m.get('ticker')}: {e}")
            return None

    # ── parse a player prop market ───────────────────────
    def _parse_prop(self, m: dict) -> Optional[KalshiMarket]:
        """
        Expected Kalshi prop ticker formats:
          KXNBAPTS-26MAY22OKCSAS-SASVWEMBANYAMA1-22.5
          KXNBAAST-26MAY22NYKCLE-NYKJBRUNSON11-5.5
        Player slug format: {TEAM}{INITIAL}{LASTNAME}{NUMBER}, e.g. SASVWEMBANYAMA1
        """
        try:
            ticker = m.get("ticker", "")
            parts = ticker.split("-")
            if len(parts) < 4: return None

            price = self._price(m)
            if price is None: return None

            sport = "NBA" if "NBA" in ticker.upper() else "NHL"

            # Last part = prop line
            try:
                prop_line = float(parts[-1])
            except ValueError:
                return None

            # Second-to-last = player slug (e.g. "SASVWEMBANYAMA1")
            player_abbr = parts[-2]

            # Third-to-last = game event (e.g. "26MAY22OKCSAS")
            event_part = parts[-3] if len(parts) >= 4 else ""
            away_abbr = event_part[-6:-3] if len(event_part) >= 6 else "UNK"
            home_abbr = event_part[-3:]    if len(event_part) >= 3 else "UNK"

            # Resolve player full name — must be a known player to proceed
            player_full = self._resolve_player(player_abbr)
            if not player_full:
                log.debug(f"prop skip: unknown player {player_abbr}")
                return None   # Only model known stars; skip bench/role players

            # Sanity: player's team prefix (first 3 chars) should match one of the game teams.
            # This prevents cross-game contamination where a NYK player shows up in OKC@SAS.
            player_team = player_abbr[:3].upper()
            # OKC sometimes encoded as "UKC" by Kalshi
            _OKC_ALIASES = {"UKC", "OKC"}
            if player_team not in (away_abbr, home_abbr):
                # Allow OKC/UKC aliases
                if not (player_team in _OKC_ALIASES and (away_abbr in _OKC_ALIASES or home_abbr in _OKC_ALIASES)):
                    log.debug(f"prop skip: {player_abbr} team {player_team} not in {away_abbr}@{home_abbr}")
                    return None

            # Determine prop type from series name
            tk_upper = ticker.upper()
            if "PTS" in tk_upper or "POINTS" in tk_upper:
                prop_type = "PTS"
            elif "REB" in tk_upper or "REBOUNDS" in tk_upper:
                prop_type = "REB"
            elif "AST" in tk_upper or "ASSISTS" in tk_upper:
                prop_type = "AST"
            elif "GOALS" in tk_upper:
                prop_type = "GOALS"
            else:
                prop_type = "PTS"

            title = m.get("title", f"{player_full} {prop_type} O{prop_line}")
            gt = self._game_time(m)

            return KalshiMarket(
                ticker=ticker, title=title, sport=sport,
                home_team=_ABBR.get(home_abbr, home_abbr),
                away_team=_ABBR.get(away_abbr, away_abbr),
                home_abbr=home_abbr, away_abbr=away_abbr,
                market_type="PROP", yes_price=price, yes_side="OVER",
                total_line=prop_line,
                prop_player=player_abbr, prop_player_full=player_full,
                prop_type=prop_type,
                volume=float(m.get("volume_fp", 0) or 0),
                game_time=gt,
            )
        except Exception as e:
            log.debug(f"parse_prop {m.get('ticker')}: {e}")
            return None

    def _resolve_player(self, slug: str) -> str:
        """
        Resolve a Kalshi player slug to a full name in _STAR_PPG.
        Slug format: {TEAM}{INITIAL}{LASTNAME}{NUMBER}, e.g. SASVWEMBANYAMA1
        Returns full name if found, empty string if unknown.
        """
        upper = slug.upper()

        # 1. Direct abbreviation match (short codes like WEMB, SGA)
        if upper in _PROP_PLAYER_MAP:
            return _PROP_PLAYER_MAP[upper]

        # 2. Extract last name from slug: strip 3-char team prefix + initial + trailing digits
        body = re.sub(r'^\w{3}', '', upper)   # remove team prefix (e.g. "NYK", "SAS", "UKC")
        body = re.sub(r'\d+$', '', body)       # remove jersey number
        if body:
            body = body[1:]                    # remove first initial

        # body ≈ LASTNAME (e.g. "WEMBANYAMA", "BRUNSON", "MITCHELL")
        # Strip hyphens for compound last names (e.g. "GILGEOUS-ALEXANDER" → "GILGEOUSALEXANDER")
        body_clean = body.replace("-", "").replace("'", "")

        for full_name in _STAR_PPG:
            last = full_name.split()[-1].upper()
            last_clean = last.replace("-", "").replace("'", "")
            # Exact match required — substring would let "HART" match "HARTENSTEIN"
            if last_clean and last_clean == body_clean:
                return full_name

        # 3. Check _PROP_PLAYER_MAP keys (some use partial name like "WEMB")
        for abbr in _PROP_PLAYER_MAP:
            if abbr in upper:
                return _PROP_PLAYER_MAP[abbr]

        return ""   # unknown player — skip this prop

    # ── discover available sport-related series ──────────
    def discover_sports_series(self) -> List[str]:
        """Probe Kalshi series endpoint for NBA/NHL-related series tickers."""
        found = []
        data = self._get("/series", params={"limit": 200})
        if not data: return found
        for s in data.get("series", []):
            tk = s.get("ticker", "")
            if any(x in tk.upper() for x in ("NBA", "NHL", "KXNBA", "KXNHL")):
                found.append(tk)
        log.info(f"Discovered {len(found)} sport series: {found}")
        return found

    # ── pick best total line for a game ──────────────────
    def _best_total(self, event_ticker: str, raw_group: List[dict]) -> Optional[KalshiMarket]:
        try:
            event_parts = event_ticker.split("-")
            team_part   = event_parts[-1]
            away_abbr   = team_part[-6:-3]
            home_abbr   = team_part[-3:]
            sport       = "NBA" if "NBA" in event_ticker.upper() else "NHL"

            valid_lo, valid_hi = (195.0, 230.0) if sport == "NBA" else (5.0, 7.0)

            best_m, best_dist = None, 1.0
            for m in raw_group:
                p = self._price(m)
                if p is None: continue
                tk_tmp = m.get("ticker", "")
                try:
                    ln_tmp = float(tk_tmp.rsplit("-", 1)[-1])
                except ValueError:
                    continue
                if not (valid_lo <= ln_tmp <= valid_hi):
                    continue
                dist = abs(p - 0.50)
                if dist < best_dist:
                    best_dist, best_m = dist, m

            if best_m is None: return None

            tk = best_m.get("ticker", "")
            line_str = tk.rsplit("-", 1)[-1]
            try:
                total_line = float(line_str)
            except ValueError:
                return None

            price = self._price(best_m)
            gt    = self._game_time(best_m)
            title = best_m.get("title", f"{away_abbr} @ {home_abbr} Total")

            return KalshiMarket(
                ticker=tk, title=title, sport=sport,
                home_team=_ABBR.get(home_abbr, home_abbr),
                away_team=_ABBR.get(away_abbr, away_abbr),
                home_abbr=home_abbr, away_abbr=away_abbr,
                market_type="TOTAL", yes_price=price, yes_side="OVER",
                total_line=total_line, game_time=gt,
            )
        except Exception as e:
            log.debug(f"best_total {event_ticker}: {e}")
            return None

    # ── helpers ──────────────────────────────────────────
    def _price(self, m: dict) -> Optional[float]:
        for field in ("yes_ask_dollars", "yes_bid_dollars", "last_price_dollars"):
            v = m.get(field)
            if v is not None:
                try:
                    p = float(v)
                    if 0.01 <= p <= 0.99: return p
                except (ValueError, TypeError): pass
        return None

    def _game_time(self, m: dict) -> Optional[datetime]:
        from datetime import timezone
        v = m.get("expected_expiration_time")
        if v:
            try: return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception: pass

        # Ticker format: KXNBASPREAD-26MAY24OKCSAS-OKC5
        # Event part starts with YYMMM DD, e.g. "26MAY24" = year 2026, May, day 24
        tk = m.get("ticker", "")
        parts = tk.split("-")
        if len(parts) >= 2:
            match = re.match(r'^(\d{2})([A-Za-z]{3})(\d{2})', parts[1])
            if match:
                yr_prefix, mon, day = match.groups()   # "26"=2026, "MAY", "24"=day
                try:
                    dt = datetime.strptime(f"{day}{mon.upper()}20{yr_prefix}", "%d%b%Y")
                    return dt.replace(hour=23, tzinfo=timezone.utc)
                except Exception: pass
        return None

    def _ticker_date(self, tk: str) -> Optional["date"]:
        """Return the local calendar date embedded in a Kalshi ticker, or None."""
        from datetime import date as _date
        parts = tk.split("-")
        if len(parts) >= 2:
            match = re.match(r'^(\d{2})([A-Za-z]{3})(\d{2})', parts[1])
            if match:
                yr_prefix, mon, day = match.groups()
                try:
                    return datetime.strptime(f"{day}{mon.upper()}20{yr_prefix}", "%d%b%Y").date()
                except Exception: pass
        return None

    # ESPN uses shorter abbreviations for some teams; map them to Kalshi's 3-letter codes
    _ESPN_TO_KALSHI: Dict[str, str] = {
        "NY":  "NYK",   # Knicks
        "GS":  "GSW",   # Warriors
        "SA":  "SAS",   # Spurs
        "NO":  "NOP",   # Pelicans
        "NOR": "NOP",
        "TB":  "TBL",   # Lightning
        "NJ":  "NJD",   # Devils
    }

    def _espn_today_games(self) -> set:
        """Returns set of 'AWAY@HOME' (uppercase Kalshi abbrs) for today's non-final games."""
        today_str = datetime.now().strftime("%Y%m%d")
        result: set = set()
        for sport, league in [("basketball", "nba"), ("hockey", "nhl")]:
            try:
                r = requests.get(
                    f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard",
                    params={"dates": today_str},
                    headers=HEADERS, timeout=10)
                r.raise_for_status()
                for ev in r.json().get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    state = comp.get("status", {}).get("type", {}).get("state", "pre")
                    if state == "post":
                        continue  # already finished
                    competitors = comp.get("competitors", [])
                    home = next((c for c in competitors if c.get("homeAway") == "home"), {})
                    away = next((c for c in competitors if c.get("homeAway") == "away"), {})
                    h = home.get("team", {}).get("abbreviation", "").upper()
                    a = away.get("team", {}).get("abbreviation", "").upper()
                    # Normalize ESPN abbrs to Kalshi's 3-letter codes
                    h = self._ESPN_TO_KALSHI.get(h, h)
                    a = self._ESPN_TO_KALSHI.get(a, a)
                    if h and a:
                        result.add(f"{a}@{h}")
                        log.info(f"ESPN today: {a}@{h} ({league}, {state})")
            except Exception as e:
                log.warning(f"ESPN today games {league}: {e}")
        return result

    def _record_history(self, mkts: List[KalshiMarket]) -> None:
        hist = {}
        if LINE_HIST.exists():
            try: hist = json.loads(LINE_HIST.read_text())
            except Exception: pass
        # Also keep backward-compatible PRICE_HIST
        old_hist = {}
        if PRICE_HIST.exists():
            try: old_hist = json.loads(PRICE_HIST.read_text())
            except Exception: pass

        now    = datetime.now().isoformat()
        today  = datetime.now().strftime("%Y-%m-%d")
        cutoff = (datetime.now() - timedelta(hours=48)).isoformat()

        for mkt in mkts:
            bucket = hist.setdefault(mkt.ticker, [])
            bucket.append({"t": now, "p": mkt.yes_price})
            # Prune old entries
            hist[mkt.ticker] = [e for e in bucket if e["t"] > cutoff]

            # Same for PRICE_HIST (backward compat)
            old_bucket = old_hist.setdefault(mkt.ticker, [])
            old_bucket.append({"t": now, "p": mkt.yes_price})
            old_hist[mkt.ticker] = [e for e in old_bucket if e["t"] > cutoff]

        try:
            LINE_HIST.write_text(json.dumps(hist))
            PRICE_HIST.write_text(json.dumps(old_hist))
        except Exception: pass

    def movement(self, ticker: str) -> Tuple[float, float]:
        """Returns (delta_1h_cents, delta_2h_cents). Positive = price moved up."""
        if not LINE_HIST.exists() and not PRICE_HIST.exists(): return 0.0, 0.0
        hist_file = LINE_HIST if LINE_HIST.exists() else PRICE_HIST
        try:
            hist = json.loads(hist_file.read_text()).get(ticker, [])
            if len(hist) < 2: return 0.0, 0.0
            cur = hist[-1]["p"]
            now = datetime.now()
            p1h = p2h = cur
            for e in reversed(hist[:-1]):
                age = (now - datetime.fromisoformat(e["t"])).total_seconds() / 3600
                if age <= 1.0: p1h = e["p"]
                if age <= 2.0: p2h = e["p"]
                if age > 2.0:  break
            return (cur - p1h) * 100, (cur - p2h) * 100
        except Exception: return 0.0, 0.0

    def movement_detail(self, ticker: str) -> dict:
        """Returns detailed movement: 1h, 2h, 30m, 10m, since_open, move_class."""
        result = {"mv1h": 0.0, "mv2h": 0.0, "mv30m": 0.0, "mv10m": 0.0,
                  "open_delta": 0.0, "move_class": "flat"}
        hist_file = LINE_HIST if LINE_HIST.exists() else (PRICE_HIST if PRICE_HIST.exists() else None)
        if not hist_file: return result
        try:
            hist = json.loads(hist_file.read_text()).get(ticker, [])
            if len(hist) < 2: return result
            cur = hist[-1]["p"]
            now = datetime.now()
            today_start = now.replace(hour=6, minute=0, second=0, microsecond=0).isoformat()

            p1h = p2h = p30m = p10m = p_open = cur
            for e in reversed(hist[:-1]):
                age_secs = (now - datetime.fromisoformat(e["t"])).total_seconds()
                age_h = age_secs / 3600
                if age_secs <= 600:  p10m  = e["p"]   # last 10 min
                if age_secs <= 1800: p30m  = e["p"]   # last 30 min
                if age_h    <= 1.0:  p1h   = e["p"]   # last 1 hr
                if age_h    <= 2.0:  p2h   = e["p"]   # last 2 hr
                if e["t"] >= today_start: p_open = e["p"]  # first price today

            result["mv1h"]      = (cur - p1h)   * 100
            result["mv2h"]      = (cur - p2h)   * 100
            result["mv30m"]     = (cur - p30m)  * 100
            result["mv10m"]     = (cur - p10m)  * 100
            result["open_delta"]= (cur - p_open)* 100

            # Classify movement
            mv10  = abs(result["mv10m"])
            mv30  = abs(result["mv30m"])
            mv2h  = abs(result["mv2h"])
            if mv10 >= 5.0:
                result["move_class"] = "STEAM"
            elif mv30 >= 3.0:
                result["move_class"] = "SHARP"
            elif mv2h >= 3.0:
                result["move_class"] = "PUBLIC"
            else:
                result["move_class"] = "flat"
        except Exception as e:
            log.debug(f"movement_detail {ticker}: {e}")
        return result

# ══════════════════════════════════════════════════════
# SECTION 10b — POLYMARKET CLIENT
# ══════════════════════════════════════════════════════
class PolymarketClient:
    BASE = "https://gamma-api.polymarket.com"

    def _get(self, ep: str, params: dict = None) -> Optional[dict]:
        try:
            r = requests.get(f"{self.BASE}{ep}", params=params, timeout=12)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log.debug(f"Polymarket {ep}: {e}")
            return None

    def nba_nhl_markets(self) -> Dict[str, float]:
        """Returns {search_key: yes_price} for NBA/NHL markets."""
        prices: Dict[str, float] = {}
        for query in ["NBA playoff", "NHL playoff", "NBA 2026", "NHL 2026"]:
            data = self._get("/markets", params={"search": query, "active": True, "limit": 50})
            if not data: continue
            for mkt in (data if isinstance(data, list) else data.get("markets", [])):
                q = mkt.get("question", "") or mkt.get("title", "")
                # Only moneyline / winner markets
                if not any(w in q.lower() for w in ["win", "winner", "beat", "advance"]): continue
                # Get best ask price for YES
                price = None
                for outcome in mkt.get("outcomes", []):
                    if "yes" in str(outcome).lower() or outcome == mkt.get("outcomes", [""])[0]:
                        try: price = float(mkt.get("outcomePrices", ["0"])[0])
                        except Exception: pass
                if price and 0.01 < price < 0.99:
                    key = q.lower()[:80]
                    prices[key] = price
        return prices

    def find_match(self, home: str, away: str, prices: Dict[str, float]) -> Optional[float]:
        """Fuzzy-search Polymarket prices dict for a specific game."""
        home_l, away_l = home.lower(), away.lower()
        for key, price in prices.items():
            if _fuzzy(home_l, key) or _fuzzy(away_l, key):
                return price
        return None

# ══════════════════════════════════════════════════════
# SECTION 10c — SERIES CONTEXT + GOALIE CHECKER
# ══════════════════════════════════════════════════════
def _series_context(home_wins: int, home_losses: int,
                    away_wins: int, notes: List[str]) -> float:
    """
    Returns signed adjustment to HOME win probability based on series state.
    Positive = home team more likely to win tonight.
    """
    game_num = home_wins + home_losses + 1   # games played + 1
    adj = 0.0

    if game_num == 2:
        if away_wins == 1 and home_wins == 0:
            # Away team won Game 1 on the road — home bounces back 61% historically
            # vs base 54-57%, so add ~+6%
            adj += 0.06
            notes.append("G2 home bounce-back (away won G1): +6% (hist. 61%)")
        # home won G1 → no extra boost, base already captures home advantage

    elif game_num == 3:
        if home_wins == 1 and away_wins == 1:
            # Series tied 1-1, now at THIS home team's arena — hist. home wins G3 64%
            adj += 0.10
            notes.append("G3 tied series at home arena: +10% (hist. 64%)")
        elif away_wins == 2 and home_wins == 0:
            # Away leads 2-0 but THIS team is now home (back against wall) — wins 58%
            adj += 0.04
            notes.append("G3 0-2 series desperation at home: +4% (hist. 58%)")

    elif game_num >= 5:
        if home_losses == 3:
            # Elimination game at home — massive psychological boost
            adj += 0.05
            notes.append("Elimination game at home: +5%")
        elif away_wins == home_wins + 1:
            # Away has series lead coming into this game
            adj -= 0.02
            notes.append(f"Away leads series {away_wins}-{home_wins}: -2%")

    return adj


class GoalieChecker:
    """Checks ESPN NHL news for morning skate / goalie confirmation status."""
    ESPN_NEWS = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/news"
    _UNCERTAIN = ["unconfirmed", "morning skate", "decision", "day-to-day",
                  "not named", "starter unknown", "tbd", "to be determined",
                  "questionable", "undecided"]

    def check(self, home_team: str, away_team: str) -> str:
        """Returns warning string if either goalie is unconfirmed, else ''."""
        try:
            r = requests.get(self.ESPN_NEWS, headers=HEADERS, timeout=10)
            r.raise_for_status()
            articles = r.json().get("articles", [])
            warnings = []
            for art in articles[:20]:
                text = (art.get("headline","") + " " + art.get("description","")).lower()
                if not any(w in text for w in self._UNCERTAIN): continue
                # Is this article about one of tonight's teams?
                for team in (home_team, away_team):
                    if _fuzzy(team.lower(), text):
                        warnings.append(f"Goalie unconfirmed ({team}) — wait for morning skate")
                        break
            return warnings[0] if warnings else ""
        except Exception as e:
            log.debug(f"GoalieChecker: {e}")
            return ""


# ══════════════════════════════════════════════════════
# SECTION 11 — NHL PROBABILITY MODEL
# ══════════════════════════════════════════════════════
class NHLModel:
    def moneyline(self, home: NHLTeamStats, away: NHLTeamStats,
                  hg: Optional[GoalieStats], ag: Optional[GoalieStats],
                  injuries: List[InjuryReport], notes: List[str]) -> float:
        p = NHL_HOME_BASE

        # Points% quality adjustment (every 10pp = +3%; cap ±12%)
        if home.pts_pct != 0.5 or away.pts_pct != 0.5:
            pts_diff = home.pts_pct - away.pts_pct
            pts_adj  = float(np.clip(pts_diff * 0.3, -0.12, 0.12))
            p       += pts_adj
            if abs(pts_adj) > 0.005:
                notes.append(f"Quality ({home.pts_pct:.3f} vs {away.pts_pct:.3f}): {pts_adj*100:+.1f}%")

        # xG% differential (every 5% = +3.5%)
        xg_diff = home.xg_pct - away.xg_pct
        adj = (xg_diff / 5.0) * 0.035
        p += adj
        if abs(adj) > 0.01: notes.append(f"xG% edge {xg_diff:+.1f}%→{adj*100:+.1f}%")

        # Goalie GSAx (every 1.0 = +4%)
        if hg and ag:
            gdiff = hg.gsax - ag.gsax
            adj   = (gdiff / 1.0) * 0.04
            p    += adj
            if abs(adj) > 0.01: notes.append(f"GSAx edge {gdiff:+.2f}→{adj*100:+.1f}%")
            # Home/away goalie split
            if hg.home_sv_pct and hg.away_sv_pct:
                split = hg.home_sv_pct - hg.sv_pct
                p += split * 0.5

        # Rest days (every day = +2.5%, cap ±8%)
        rd = home.rest_days - away.rest_days
        radj = float(np.clip(rd * 0.025, -0.08, 0.08))
        p += radj
        if abs(radj) > 0.01: notes.append(f"Rest {home.rest_days}v{away.rest_days}d:{radj*100:+.1f}%")

        # Back-to-back (-10%)
        if home.rest_days == 0: p -= 0.10; notes.append("Home B2B: -10%")
        if away.rest_days == 0: p += 0.10; notes.append("Away B2B: +10%")

        # Series context (game-specific historical rates)
        p += _series_context(home.series_wins, home.series_losses, away.series_wins, notes)

        # Power play differential (every 5% = +2%)
        pp_diff = home.pp_pct - away.pp_pct
        pp_adj  = (pp_diff / 5.0) * 0.02
        p += pp_adj
        if abs(pp_adj) > 0.005: notes.append(f"PP edge {pp_diff:+.1f}%:{pp_adj*100:+.1f}%")

        # Elimination game
        if away.series_losses == 3: p -= 0.03; notes.append("Elimination (away): -3%")

        # Injuries
        for inj in injuries:
            if inj.sport != "NHL" or inj.status not in ("OUT","DOUBTFUL"): continue
            if _fuzzy(inj.team, home.team):
                p += inj.win_prob_impact
                notes.append(f"Injury {inj.player}({inj.status}):{inj.win_prob_impact*100:+.1f}%")
            elif _fuzzy(inj.team, away.team):
                p -= inj.win_prob_impact

        return float(np.clip(p, 0.05, 0.95))

    def total(self, home: NHLTeamStats, away: NHLTeamStats,
              hg: Optional[GoalieStats], ag: Optional[GoalieStats],
              line: float, game_num: int, notes: List[str]) -> Tuple[float, float, dict]:
        # ── Poisson lambda for each team ─────────────────
        BASE_GOALS = NHL_GOALS_BASE / 2.05   # per team ≈ 2.96

        xg_home = 1.0 + (home.xg_pct - 50.0) / 200.0
        xg_away = 1.0 + (away.xg_pct - 50.0) / 200.0

        gf_home = max(0.6, 1.0 - (hg.gsax / 20.0)) if hg else 1.0
        gf_away = max(0.6, 1.0 - (ag.gsax / 20.0)) if ag else 1.0

        rf_home = 0.88 if home.rest_days == 0 else 1.0
        rf_away = 0.88 if away.rest_days == 0 else 1.0

        gn_adj = 0.90 if game_num in (1, 2) else 1.0
        HOME_ADV = 1.05

        lam_home = BASE_GOALS * xg_home * gf_away * rf_home * HOME_ADV * gn_adj
        lam_away = BASE_GOALS * xg_away * gf_home * rf_away * gn_adj
        lam_total = lam_home + lam_away

        notes.append(f"λ={lam_total:.2f} (home {lam_home:.2f} + away {lam_away:.2f})")

        n = int(line)
        p_over = float(1.0 - sp_poisson.cdf(n, lam_total))

        breakdown = {
            "sport": "NHL",
            "base_home_lam": round(BASE_GOALS * HOME_ADV, 3),
            "base_away_lam": round(BASE_GOALS, 3),
            "xg_factor_home": round(xg_home, 3),
            "xg_factor_away": round(xg_away, 3),
            "goalie_factor_home": round(gf_home, 3),
            "goalie_factor_away": round(gf_away, 3),
            "home_gsax": round(hg.gsax, 2) if hg else 0.0,
            "away_gsax": round(ag.gsax, 2) if ag else 0.0,
            "rest_factor_home": rf_home,
            "rest_factor_away": rf_away,
            "game_num": game_num,
            "game_num_adj": gn_adj,
            "lam_home": round(lam_home, 2),
            "lam_away": round(lam_away, 2),
            "lam_total": round(lam_total, 2),
            "line": line,
            "gap": round(lam_total - line, 2),
            "home_rest": home.rest_days,
            "away_rest": away.rest_days,
            "home_last_played": home.last_played,
            "away_last_played": away.last_played,
        }
        return float(np.clip(p_over, 0.03, 0.97)), lam_total, breakdown

    def puck_line(self, home: NHLTeamStats, away: NHLTeamStats,
                  hg: Optional[GoalieStats], ag: Optional[GoalieStats],
                  spread: float, notes: List[str]) -> float:
        """
        P(home team covers spread) using joint Poisson simulation.
        spread = home team's line, e.g. -1.5 means home must win by 2+.
        """
        BASE_GOALS = NHL_GOALS_BASE / 2.05

        xg_home = 1.0 + (home.xg_pct - 50.0) / 200.0
        xg_away = 1.0 + (away.xg_pct - 50.0) / 200.0
        gf_home = max(0.6, 1.0 - (hg.gsax / 20.0)) if hg else 1.0
        gf_away = max(0.6, 1.0 - (ag.gsax / 20.0)) if ag else 1.0
        rf_home = 0.88 if home.rest_days == 0 else 1.0
        rf_away = 0.88 if away.rest_days == 0 else 1.0

        lam_home = BASE_GOALS * xg_home * gf_away * rf_home * 1.05
        lam_away = BASE_GOALS * xg_away * gf_home * rf_away

        notes.append(f"Puck line λ: home {lam_home:.2f} away {lam_away:.2f} spread {spread:+.1f}")

        # Joint Poisson: iterate over plausible goal counts (0-14)
        p_cover = 0.0
        for h in range(0, 15):
            ph = float(sp_poisson.pmf(h, lam_home))
            if spread <= -1.0:
                # Home must win by ceil(abs(spread)) goals
                min_margin = int(abs(spread) - 0.01) + 1  # -1.5 → must win by 2
                # P(away ≤ h - min_margin)
                if h >= min_margin:
                    p_cover += ph * float(sp_poisson.cdf(h - min_margin, lam_away))
            else:
                # Home +spread: covers if home wins OR loses by less than spread
                # e.g. +1.5: home covers if home_score - away_score > -1.5 → home ≥ away - 1
                max_loss = int(abs(spread) - 0.01)  # +1.5 → can lose by 1
                # P(away ≤ h + max_loss)
                p_cover += ph * float(sp_poisson.cdf(h + max_loss, lam_away))

        return float(np.clip(p_cover, 0.03, 0.97))

# ══════════════════════════════════════════════════════
# SECTION 12 — NBA PROBABILITY MODEL
# ══════════════════════════════════════════════════════
class NBAModel:
    def moneyline(self, home: NBATeamStats, away: NBATeamStats,
                  injuries: List[InjuryReport], notes: List[str]) -> float:
        p = NBA_HOME_BASE

        # Net rating (every 5 pts = +6%)
        ndiff = home.net_rtg - away.net_rtg
        adj   = (ndiff / 5.0) * 0.06
        p    += adj
        if abs(adj) > 0.01: notes.append(f"Net RTG {ndiff:+.1f}:{adj*100:+.1f}%")

        # Defensive rating (lower = better)
        def_diff = away.def_rtg - home.def_rtg
        p += (def_diff / 5.0) * 0.025

        # Rest (every extra day = +1.8%)
        rd   = home.rest_days - away.rest_days
        radj = rd * 0.018
        p   += radj
        if abs(radj) > 0.01: notes.append(f"Rest {home.rest_days}v{away.rest_days}d:{radj*100:+.1f}%")

        # Series context (game-specific historical rates)
        p += _series_context(home.series_wins, home.series_losses, away.series_wins, notes)

        # Game-state psychology
        if home.prior_blowout_loss:  p -= 0.04; notes.append("Home blowout loss: -4%")
        if away.prior_blowout_loss:  p += 0.04
        if home.prior_ot_win:        p -= 0.02; notes.append("Home OT fatigue: -2%")
        if away.prior_ot_win:        p += 0.02

        # Injuries
        for inj in injuries:
            if inj.sport != "NBA" or inj.status not in ("OUT","DOUBTFUL"): continue
            if _fuzzy(inj.team, home.team):
                p += inj.win_prob_impact
                notes.append(f"Injury {inj.player}({inj.status}):{inj.win_prob_impact*100:+.1f}%")
            elif _fuzzy(inj.team, away.team):
                p -= inj.win_prob_impact

        return float(np.clip(p, 0.05, 0.95))

    def total(self, home: NBATeamStats, away: NBATeamStats,
              line: float, injuries: List[InjuryReport], notes: List[str]) -> Tuple[float, float, dict]:
        home_pts = (home.off_rtg / 100) * home.pace
        away_pts = (away.off_rtg / 100) * away.pace
        exp = home_pts + away_pts
        base_combined = exp
        if exp < 170 or exp > 260:
            exp = 216.0
            base_combined = 216.0

        exp -= 10
        notes.append("Playoff defense: -10 pts")

        ot_adj = 0
        if home.prior_ot_game or away.prior_ot_game:
            ot_adj = -6; exp += ot_adj; notes.append("Prior OT fatigue: -6 pts")

        tired = sum(1 for t in [home, away] if t.rest_days == 0)
        b2b_adj = -5 * tired
        if tired:
            exp += b2b_adj; notes.append(f"{tired} B2B: {b2b_adj} pts")

        avg_def = (home.def_rtg + away.def_rtg) / 2
        def_adj = -(avg_def - 110) * 0.5
        exp += def_adj

        # Series-context adjustments to total (conditional on series state)
        desperation_adj = conservative_adj = must_win_def_adj = 0
        away_leads_2_0 = (away.series_wins == 2 and away.series_losses == 0
                          and home.series_wins == 0 and home.series_losses == 2)
        if away_leads_2_0:
            desperation_adj = -3   # home team down 0-2: defense tightens ~3 pts (not elimination, but urgent)
            conservative_adj = -3  # away team milks clock, avoids risk up 2-0
            must_win_def_adj = -3  # must-win games historically run 6-10 pts under pace
            exp += desperation_adj + conservative_adj + must_win_def_adj

        inj_adj = 0.0
        for inj in injuries:
            if inj.sport != "NBA" or inj.status not in ("OUT", "DOUBTFUL"): continue
            if inj.team and (_fuzzy(inj.team, home.team) or _fuzzy(inj.team, away.team)):
                inj_adj -= abs(inj.bpm_impact) * 0.3
                exp += inj_adj

        STD = 12.0
        p_over = float(1 - sp_norm.cdf(line, exp, STD))

        breakdown = {
            "sport": "NBA",
            "base_home_pts": round(home_pts, 1),
            "base_away_pts": round(away_pts, 1),
            "base_combined": round(base_combined, 1),
            "playoff_adj": -10,
            "ot_adj": ot_adj,
            "b2b_adj": b2b_adj,
            "def_adj": round(def_adj, 1),
            "desperation_adj": desperation_adj,
            "conservative_adj": conservative_adj,
            "must_win_def_adj": must_win_def_adj,
            "inj_adj": round(inj_adj, 1),
            "exp": round(exp, 1),
            "line": line,
            "gap": round(exp - line, 1),
            "home_off_rtg": home.off_rtg,
            "away_off_rtg": away.off_rtg,
            "home_def_rtg": home.def_rtg,
            "away_def_rtg": away.def_rtg,
            "home_rest": home.rest_days,
            "away_rest": away.rest_days,
            "home_last_played": home.last_played,
            "away_last_played": away.last_played,
        }
        return float(np.clip(p_over, 0.03, 0.97)), exp, breakdown

    def spread(self, home: NBATeamStats, away: NBATeamStats,
               spread_line: float, injuries: List[InjuryReport],
               notes: List[str]) -> float:
        """
        P(home team covers ATS spread) using normal distribution.
        spread_line is from home's perspective: -5.5 = home favored by 5.5.
        Returns P(home covers), i.e. P(home_score - away_score > spread_line).
        """
        # Predicted margin: net rating diff / 3 + home advantage
        net_diff = home.net_rtg - away.net_rtg
        predicted_margin = net_diff / 3.0 + 3.5

        # Rest adjustment
        rd = home.rest_days - away.rest_days
        predicted_margin += rd * 0.8

        # Back-to-back
        if home.rest_days == 0:  predicted_margin -= 4.0
        if away.rest_days == 0:  predicted_margin += 4.0

        # Series context (same adjustments scale to margin)
        series_adj = 0.0
        dummy_notes: List[str] = []
        series_adj = _series_context(home.series_wins, home.series_losses,
                                     away.series_wins, dummy_notes)
        predicted_margin += series_adj * 10  # convert prob to points roughly

        # Injury adjustment to margin
        for inj in injuries:
            if inj.sport != "NBA" or inj.status not in ("OUT", "DOUBTFUL"): continue
            if _fuzzy(inj.team, home.team):
                predicted_margin += inj.win_prob_impact * 15
            elif _fuzzy(inj.team, away.team):
                predicted_margin -= inj.win_prob_impact * 15

        notes.append(f"Predicted margin: home {predicted_margin:+.1f} vs spread {spread_line:+.1f}")

        STD = 11.0  # historical ATS std dev in playoffs
        # P(actual margin > spread_line) = P(home wins by more than spread asks)
        p_cover = float(1 - sp_norm.cdf(spread_line, predicted_margin, STD))
        return float(np.clip(p_cover, 0.03, 0.97))


# ══════════════════════════════════════════════════════
# SECTION 12b — PLAYER PROP MODEL
# ══════════════════════════════════════════════════════
class PlayerPropModel:
    """Projects player prop probabilities using playoff-adjusted PPG."""

    # Defensive matchup rating: multiplier to apply based on opp def quality
    # Lower net_rtg_allowed → better defense → lower scoring allowed
    _DEF_ADJ_SCALE = 0.015  # per net rtg point above/below 0

    def over_prob(self, player_full: str, prop_type: str, line: float,
                  opp_team: NBATeamStats, injuries: List[InjuryReport],
                  notes: List[str]) -> float:
        """P(player goes over prop line) for PTS/REB/AST."""
        base = _STAR_PPG.get(player_full, 15.0)

        # Injury status: if the player themselves is injured, skip
        for inj in injuries:
            if _fuzzy_player(inj.player, player_full):
                if inj.status in ("OUT", "DOUBTFUL"):
                    notes.append(f"{player_full} is {inj.status} — prop unreliable")
                    return 0.10  # almost certainly doesn't go over

        # Scale base for non-PTS prop types
        if prop_type == "REB":
            base = base * 0.35      # rebounders score ~35% of their PPG in reb
        elif prop_type == "AST":
            base = base * 0.22      # rough assist/PPG ratio for playmakers
        elif prop_type == "GOALS":
            base = base * 0.45      # goals ≈ 45% of points for NHL

        # Defensive matchup: opponent's net rating affects scoring
        opp_def = opp_team.def_rtg if opp_team else 110.0
        def_adj = -(opp_def - 110.0) * self._DEF_ADJ_SCALE
        base += def_adj * base

        # Playoff intensity: stars average ~5% below regular season
        base *= 0.95

        # Wembanyama-specific: if SAS facing OKC, OKC has top defense
        if "wembanyama" in player_full.lower():
            if opp_team and opp_team.def_rtg < 108:
                base *= 0.93  # elite defense penalty
                notes.append(f"Elite defense penalty: base →{base:.1f}")

        notes.append(f"Projected {prop_type}: {base:.1f} vs line {line:.1f}")

        # Stat-specific std devs (historical playoff variance)
        if prop_type in ("AST", "ASSISTS"):
            std = max(base * 0.45, 1.2)   # assists: ~45% CV
        elif prop_type in ("REB", "REBOUNDS"):
            std = max(base * 0.40, 1.5)   # rebounds: ~40% CV
        elif prop_type == "GOALS":
            std = max(base * 0.50, 0.3)   # NHL goals: high variance
        else:
            std = max(base * 0.28, 2.5)   # PTS: ~28% CV, floor 2.5

        p_over = float(1 - sp_norm.cdf(line, base, std))
        return float(np.clip(p_over, 0.03, 0.97))

    def wembanyama_points(self, line: float, opp: NBATeamStats,
                          fox_out: bool, harper_out: bool,
                          injuries: List[InjuryReport],
                          notes: List[str]) -> float:
        """Specific Wembanyama model with fox/harper usage adjustments."""
        base = 22.2  # 2024-25 playoff average

        # Usage bump: if Fox or Harper is out, Wemby gets more touches
        if fox_out:
            base += 3.5; notes.append("De'Aaron Fox out → Wemby usage +3.5 pts")
        if harper_out:
            base += 2.0; notes.append("Dylan Harper out → Wemby usage +2.0 pts")

        # Fox and Harper are guards — Wemby scores more if they're healthy (floor spacing)
        # If both healthy, no adjustment needed

        # OKC elite defense (if applicable)
        if opp and opp.def_rtg < 108:
            base *= 0.93
            notes.append(f"OKC elite defense ({opp.def_rtg:.0f} DRtg): base →{base:.1f}")

        notes.append(f"Wemby projected: {base:.1f} pts vs line {line:.1f}")

        std = base * 0.28
        p_over = float(1 - sp_norm.cdf(line, base, std))
        return float(np.clip(p_over, 0.03, 0.97))


# ══════════════════════════════════════════════════════
# SECTION 13 — EDGE DETECTION ENGINE
# ══════════════════════════════════════════════════════
class EdgeDetector:
    def __init__(self, bankroll: float):
        self.bankroll = bankroll

    def evaluate(self, model_prob: float, kalshi_price: float,
                 game: str, sport: str, mtype: str,
                 notes: List[str], mv1: float, mv2: float,
                 move_detail: dict = None,
                 injury_flags: List[str] = None) -> BetRecommendation:

        edge = model_prob - kalshi_price

        # Kelly: b = (1/price - 1), kelly = (p*b - (1-p)) / b
        kelly = 0.0
        if 0 < kalshi_price < 1:
            b = (1.0 / kalshi_price) - 1
            if b > 0:
                kelly = max(0.0, (model_prob * b - (1 - model_prob)) / b)

        # EV per $1 staked
        profit_win = (1.0 - kalshi_price) / kalshi_price
        ev = model_prob * profit_win - (1 - model_prob)

        md = move_detail or {}
        move_class = md.get("move_class", "flat")
        mv30m      = md.get("mv30m", 0.0)
        mv10m      = md.get("mv10m", 0.0)
        open_delta = md.get("open_delta", 0.0)

        # Determine if movement is WITH or AGAINST model
        # edge > 0 means we like YES side; positive movement = YES price rising
        move_with_model = (edge > 0 and mv1 > 0) or (edge < 0 and mv1 < 0)

        # Category
        if edge >= 0.12:
            cat      = "STRONG_BET"
            bet_size = round(kelly * self.bankroll, 2)
        elif edge >= 0.07:
            cat      = "BET"
            bet_size = round((kelly / 2) * self.bankroll, 2)
        elif edge >= 0.05:
            cat      = "MARGINAL"
            bet_size = 0.0
        else:
            cat      = "SKIP"
            bet_size = 0.0

        # Cap at 25% of bankroll
        bet_size = min(bet_size, self.bankroll * 0.25)

        # Sharp signal classification (1h movement)
        if mv1 >= 5.0:
            sharp = "agrees"
        elif mv1 <= -5.0:
            sharp = "override"
        elif mv1 >= 3.0:
            sharp = "agrees"
        elif mv1 <= -3.0:
            sharp = "disagrees"
        else:
            sharp = "flat"

        # Steam = 5¢ in 10 min
        if move_class == "STEAM" and not move_with_model:
            cat = "SKIP"; bet_size = 0.0; sharp = "override"
            notes.insert(0, "STEAM AGAINST MODEL — skipping")
        elif move_class == "STEAM" and move_with_model:
            if cat in ("BET", "MARGINAL"):
                cat = "STRONG_BET"
                bet_size = round(kelly * self.bankroll, 2)
            notes.insert(0, f"STEAM WITH MODEL +{mv10m:.1f}¢ in 10min")
        elif move_class == "SHARP":
            if not move_with_model:
                # Sharp money against = downgrade
                if cat == "STRONG_BET": cat = "BET"; bet_size = round((kelly/2)*self.bankroll, 2)
                notes.insert(0, f"SHARP MONEY AGAINST MODEL +{abs(mv30m):.1f}¢ in 30min")
                sharp = "disagrees"
            else:
                # Sharp with model = upgrade
                if cat == "BET":
                    cat = "STRONG_BET"; bet_size = round(kelly * self.bankroll, 2)
                notes.insert(0, f"SHARP MONEY agrees +{mv30m:.1f}¢ in 30min")
                sharp = "agrees"

        # 5¢ against = SKIP override
        if sharp == "override":
            cat = "SKIP"; bet_size = 0.0

        # Confidence level — LOW only when movement is actively AGAINST the model
        if move_class in ("STEAM", "SHARP") and move_with_model and edge >= 0.10:
            confidence = "HIGH"
        elif move_class in ("STEAM", "SHARP") and not move_with_model:
            confidence = "LOW"   # active contra-movement
        elif sharp == "disagrees":
            confidence = "LOW"   # explicit sharp disagreement
        else:
            confidence = "MEDIUM"  # flat movement or no data = normal confidence

        # Risk note for injuries
        risk_note = ""
        if injury_flags:
            first_flag = injury_flags[0]
            # Extract player name from flag
            if "QUESTIONABLE" in first_flag or "DOUBTFUL" in first_flag:
                risk_note = first_flag.split("→")[0].replace("INJURY EDGE: ", "").strip()
                risk_note = f"If {risk_note.split(' ')[0]} {risk_note.split(' ')[1]} plays, this edge shrinks"

        return BetRecommendation(
            game=game, sport=sport, market_type=mtype,
            model_prob=model_prob, kalshi_price=kalshi_price,
            edge=edge, ev_per_dollar=ev,
            kelly_fraction=kelly, bet_size=bet_size,
            category=cat, bias_notes=notes,
            mv_1h=mv1, mv_2h=mv2, sharp_signal=sharp,
            move_class=move_class, open_move=open_delta,
            move_30m=mv30m, move_10m=mv10m,
            injury_flags=injury_flags or [],
            confidence=confidence, risk_note=risk_note,
        )

# ══════════════════════════════════════════════════════
# SECTION 14 — OUTPUT FORMATTER
# ══════════════════════════════════════════════════════
def _bar(c="═"): return c * W
def _fld(label, val): return f"  {label:<22}{val}"

_CAT_COLOR = {
    "STRONG_BET": Fore.GREEN + Style.BRIGHT,
    "BET":        Fore.CYAN,
    "MARGINAL":   Fore.YELLOW,
    "SKIP":       Fore.RED,
    "LIVE-SKIP":  Fore.CYAN + Style.BRIGHT,
    "DATA_ERROR": Fore.YELLOW + Style.BRIGHT,
}
_CAT_ICON = {"STRONG_BET":"▲▲","BET":"▲","MARGINAL":"◆","SKIP":"✕","LIVE-SKIP":"⏸","DATA_ERROR":"⚠"}
_CAT_ORDER = {"STRONG_BET":0,"BET":1,"MARGINAL":2,"SKIP":3}

def print_report(recs: List[BetRecommendation], hist_rates: dict = None,
                 coeff_table: bool = False) -> None:
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # ── Apply display filters ────────────────────────────
    def _show(r: BetRecommendation) -> bool:
        if r.category in ("DATA_ERROR", "SKIP"):  return False
        if r.sharp_signal == "override":          return False
        # Props can legitimately have higher edges (less efficient market)
        _max_edge = 0.35 if r.market_type.startswith("PROP") else 0.25
        if r.edge > _max_edge:                    return False

        # Spreads: same thresholds as ML (home 7%, away 12%); props 10%
        is_spread = r.market_type.startswith(("ATS", "PL"))
        is_prop   = r.market_type.startswith("PROP")

        if is_prop:
            if r.edge < 0.10:                     return False
        elif is_spread:
            min_spread = _MIN_EDGE_AWAY_ML if r.bet_side == "AWAY" else _MIN_EDGE_HOME_ML
            if r.edge < min_spread:               return False
        elif r.bet_side == "AWAY":
            if r.edge < _MIN_EDGE_AWAY_ML:        return False   # 12% away ML min
        elif r.bet_side == "HOME":
            if r.edge < _MIN_EDGE_HOME_ML:        return False   # 7% home ML min
        else:
            if r.edge < _MIN_EDGE_TOTAL:          return False   # 7% total min

        # Total line range filter
        if r.market_type.startswith(("OVER", "UNDER")):
            try:
                line = float(r.market_type.split()[-1])
                if r.sport == "NHL" and not (5.0 <= line <= 7.0):
                    return False
                if r.sport == "NBA" and not (195.0 <= line <= 230.0):
                    return False
            except (ValueError, IndexError):
                pass
        return True

    all_filtered = [r for r in sorted(recs, key=lambda r: -r.edge) if _show(r)]
    # Cap props at 5 (quality over quantity — prop model has higher uncertainty)
    prop_count = 0
    visible = []
    for r in all_filtered:
        if r.market_type.startswith("PROP"):
            if prop_count >= 5: continue
            prop_count += 1
        visible.append(r)

    bar_heavy = "═" * W
    bar_light = "─" * (W - 2)

    print(Fore.WHITE + Style.BRIGHT + bar_heavy)
    print(Fore.WHITE + Style.BRIGHT + f"  EDGE REPORT — {ts}".center(W))
    print(Fore.WHITE + Style.BRIGHT + bar_heavy)

    if not visible:
        # Show LIVE-SKIP games if any
        live_skip = [r for r in recs if r.category == "LIVE-SKIP" and r.edge >= 0.07]
        if live_skip:
            print(Fore.CYAN + "\n  LIVE GAMES (in-progress — not betting):")
            for r in live_skip:
                print(Fore.CYAN + f"    ⏸ {r.game} — {r.market_type}  edge={r.edge*100:.1f}%")
        print(Fore.YELLOW + "\n  No actionable edges right now.\n")
        print(Fore.WHITE + Style.BRIGHT + bar_heavy)
        print()
        return

    print()
    for rec in visible:
        col   = _CAT_COLOR.get(rec.category, Fore.WHITE)
        icon  = _CAT_ICON.get(rec.category, "◆")
        label = rec.category.replace("_", " ")

        print(col + Style.BRIGHT + "  " + "═" * (W - 2))
        print(col + Style.BRIGHT + f"  {label} {icon}")
        # Game line
        game_parts = rec.game.split("(")
        game_short = game_parts[0].strip()
        game_full  = game_parts[1].rstrip(")") if len(game_parts) > 1 else ""
        side_tag = f"  [{rec.bet_side}]" if rec.bet_side in ("HOME","AWAY") else ""
        print(col + Style.BRIGHT + f"  Game: {game_short}{side_tag}")
        if game_full:
            print(Style.RESET_ALL + f"  ({game_full})")
        print(Style.RESET_ALL + f"  Market: {rec.market_type}")
        if rec.goalie_warning:
            print(Fore.YELLOW + f"  ⚠ {rec.goalie_warning}")
        print("  " + "─" * (W - 2))
        print(_fld("Model probability:", f"{rec.model_prob*100:.1f}%"))
        print(_fld("Kalshi price:", f"${rec.kalshi_price:.2f} ({rec.kalshi_price*100:.0f}%)"))
        print(Fore.GREEN + _fld("Edge:", f"+{rec.edge*100:.1f}%") + Style.RESET_ALL)
        print(_fld("EV per dollar:", f"+${rec.ev_per_dollar:.3f}"))
        if rec.bet_size > 0:
            sz = "full Kelly" if rec.category == "STRONG_BET" else "half Kelly"
            print(Fore.WHITE + Style.BRIGHT + _fld("Bet size:", f"${rec.bet_size:.2f} ({sz})"))
        # Why this edge exists
        if rec.bias_notes or rec.injury_flags:
            print("  " + "─" * (W - 2))
            print(Style.DIM + "  Why this edge exists:")
            for note in rec.bias_notes[:5]:
                print(Style.RESET_ALL + f"  - {note}")
            for flag in rec.injury_flags[:2]:
                print(Fore.RED + Style.BRIGHT + f"  - {flag}" + Style.RESET_ALL)
        # Factor breakdown — only for BET / STRONG_BET on totals
        if rec.category in ("BET", "STRONG_BET") and rec.factor_breakdown:
            bd = rec.factor_breakdown
            sport = bd.get("sport", "")
            print("  " + "─" * (W - 2))
            print(Style.DIM + "  FACTOR BREAKDOWN:")
            if sport == "NHL":
                print(Style.RESET_ALL + f"  Base rate (home goals):       {bd['base_home_lam']:.2f}g")
                print(f"  Base rate (away goals):       {bd['base_away_lam']:.2f}g")
                if bd.get("home_gsax") or bd.get("away_gsax"):
                    print(f"  Goalie adj (home GSAx {bd.get('home_gsax',0):+.2f}):  ×{bd['goalie_factor_away']:.3f}")
                    print(f"  Goalie adj (away GSAx {bd.get('away_gsax',0):+.2f}):  ×{bd['goalie_factor_home']:.3f}")
                if bd.get("rest_factor_home", 1.0) != 1.0:
                    print(f"  Home B2B rest factor:         ×{bd['rest_factor_home']:.2f}")
                if bd.get("rest_factor_away", 1.0) != 1.0:
                    print(f"  Away B2B rest factor:         ×{bd['rest_factor_away']:.2f}")
                if bd.get("game_num_adj", 1.0) != 1.0:
                    print(f"  Game {bd.get('game_num',1)} feeling-out factor:   ×{bd['game_num_adj']:.2f}")
                print(f"  {'─'*33}")
                print(Fore.CYAN + f"  Model expected total:         {bd['lam_total']:.1f}g")
                print(f"  Line:                         {bd['line']:.1f}g")
                gap = bd.get("gap", 0)
                direction = "under" if gap < 0 else "over"
                print(Fore.GREEN + Style.BRIGHT + f"  Gap:                          {abs(gap):.1f}g {direction}" + Style.RESET_ALL)
                ha, aa = bd.get("home_abbr","HOME"), bd.get("away_abbr","AWAY")
                h_lp = bd.get("home_last_played","")
                a_lp = bd.get("away_last_played","")
                h_rd, a_rd = bd.get("home_rest", 2), bd.get("away_rest", 2)
                print(Style.DIM + "  Rest check:")
                h_src = h_lp if h_lp else "(default)"
                a_src = a_lp if a_lp else "(default)"
                print(Style.RESET_ALL + f"    {ha} last played: {h_src} ({h_rd}d rest)")
                print(f"    {aa} last played: {a_src} ({a_rd}d rest)")
                rd_diff = h_rd - a_rd
                if rd_diff == 0:
                    print(Style.DIM + "    Rest differential: 0 — no edge")
                else:
                    favored = ha if rd_diff > 0 else aa
                    print(Fore.YELLOW + f"    Rest edge: {favored} +{abs(rd_diff)}d advantage" + Style.RESET_ALL)
            elif sport == "NBA":
                print(Style.RESET_ALL + f"  Base combined scoring:        {bd['base_combined']:.0f} pts")
                print(f"  Playoff defense:              {bd['playoff_adj']:+.0f} pts")
                if bd.get("ot_adj"):
                    print(f"  Prior OT fatigue:             {bd['ot_adj']:+.0f} pts")
                if bd.get("b2b_adj"):
                    print(f"  B2B adjustment:               {bd['b2b_adj']:+.0f} pts")
                if bd.get("def_adj"):
                    print(f"  Defense adj (avg DRtg {(bd.get('home_def_rtg',110)+bd.get('away_def_rtg',110))/2:.0f}): {bd['def_adj']:+.0f} pts")
                if bd.get("desperation_adj"):
                    print(f"  Home desperation (0-2 down):  {bd['desperation_adj']:+.0f} pts")
                if bd.get("conservative_adj"):
                    print(f"  Away conservative (2-0 lead): {bd['conservative_adj']:+.0f} pts")
                if bd.get("must_win_def_adj"):
                    print(f"  Must-win defensive spike:     {bd['must_win_def_adj']:+.0f} pts")
                if bd.get("inj_adj"):
                    print(f"  Injury adjustment:            {bd['inj_adj']:+.0f} pts")
                print(f"  {'─'*33}")
                print(Fore.CYAN + f"  Model expected total:         {bd['exp']:.0f} pts")
                print(f"  Line:                         {bd['line']:.0f} pts")
                gap = bd.get("gap", 0)
                direction = "under" if gap < 0 else "over"
                print(Fore.GREEN + Style.BRIGHT + f"  Gap:                          {abs(gap):.0f} pts {direction}" + Style.RESET_ALL)
                ha, aa = bd.get("home_abbr","HOME"), bd.get("away_abbr","AWAY")
                h_lp = bd.get("home_last_played","")
                a_lp = bd.get("away_last_played","")
                h_rd, a_rd = bd.get("home_rest", 2), bd.get("away_rest", 2)
                print(Style.DIM + "  Rest check:")
                h_src = h_lp if h_lp else "(default)"
                a_src = a_lp if a_lp else "(default)"
                print(Style.RESET_ALL + f"    {ha} last played: {h_src} ({h_rd}d rest)")
                print(f"    {aa} last played: {a_src} ({a_rd}d rest)")
                rd_diff = h_rd - a_rd
                if rd_diff == 0:
                    print(Style.DIM + "    Rest differential: 0 — no edge")
                else:
                    favored = ha if rd_diff > 0 else aa
                    print(Fore.YELLOW + f"    Rest edge: {favored} +{abs(rd_diff)}d advantage" + Style.RESET_ALL)
        # Line movement
        print("  " + "─" * (W - 2))
        mv_class = rec.move_class
        mv30_str = f"{rec.move_30m:+.1f}¢" if abs(rec.move_30m) >= 0.5 else ""
        mv10_str = f"{rec.move_10m:+.1f}¢" if abs(rec.move_10m) >= 0.5 else ""
        if mv_class == "STEAM":
            mv_label = f"STEAM {mv10_str} in 10min"
        elif mv_class == "SHARP":
            mv_label = f"SHARP MONEY {mv30_str} in 30min"
            mv_label += " agrees" if rec.sharp_signal == "agrees" else " disagrees"
        elif mv_class == "PUBLIC":
            mv_label = f"PUBLIC MONEY {rec.move_30m:+.1f}¢ (slow drift)"
        elif abs(rec.mv_1h) >= 0.5:
            mv_label = f"{rec.mv_1h:+.1f}¢ last hr"
        else:
            mv_label = "flat"
        print(_fld("Line movement:", mv_label))
        # Confidence
        conf_col = Fore.GREEN if rec.confidence == "HIGH" else (Fore.YELLOW if rec.confidence == "MEDIUM" else Fore.RED)
        print(conf_col + _fld("Confidence:", rec.confidence) + Style.RESET_ALL)
        if rec.risk_note:
            print(_fld("Risk note:", rec.risk_note))

    # LIVE-SKIP section
    live_skip = [r for r in recs if r.category == "LIVE-SKIP" and r.edge >= 0.07]
    if live_skip:
        print()
        print(Fore.CYAN + "  LIVE GAMES (in-progress — monitoring only):")
        for r in live_skip:
            flag = r.injury_flags[0][:50] if r.injury_flags else ""
            print(Fore.CYAN + f"    ⏸ {r.game} — {r.market_type}  edge={r.edge*100:.1f}%  {flag}")

    # DATA_ERROR summary
    errors = [r for r in recs if r.category == "DATA_ERROR"]
    if errors:
        print()
        print(Fore.YELLOW + "  DATA ERRORS (verify before acting):")
        for r in errors:
            print(Fore.YELLOW + f"    ⚠ {r.game} — {r.market_type}  edge={r.edge*100:.0f}%")

    print(Style.RESET_ALL)
    print(Fore.WHITE + Style.BRIGHT + "═" * W)
    print()

# ══════════════════════════════════════════════════════
# SECTION 15 — CALIBRATION TRACKER
# ══════════════════════════════════════════════════════
class Calibration:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if CALIBRATION.exists():
            try: return json.loads(CALIBRATION.read_text())
            except Exception: pass
        return {"bets": []}

    def _save(self):
        try: CALIBRATION.write_text(json.dumps(self.data, indent=2))
        except Exception as e: log.error(f"calibration save: {e}")

    def record(self, rec: BetRecommendation):
        entry = {
            "ts": rec.timestamp, "game": rec.game, "sport": rec.sport,
            "market_type": rec.market_type, "model_prob": rec.model_prob,
            "rec_price": rec.kalshi_price, "kalshi_price": rec.kalshi_price,
            "edge": rec.edge, "bet_size": rec.bet_size, "category": rec.category,
            "ticker": getattr(rec, 'ticker', ''),
            "outcome": None, "pnl": None,
            "clv": None, "closing_price": None, "clv_pct": None,
        }
        self.data["bets"].append(entry)
        self._save()
        self._csv(entry)

    def update_closing_price(self, ticker: str, closing_price: float) -> None:
        """Call after game closes to record CLV = closing_price - recommendation_price."""
        for bet in self.data["bets"]:
            if bet.get("ticker") == ticker and bet.get("clv") is None:
                rec_p = bet.get("rec_price", bet.get("kalshi_price", closing_price))
                clv = closing_price - rec_p
                bet["clv"]           = clv
                bet["closing_price"] = closing_price
                bet["clv_pct"]       = clv * 100
                self._save()
                break

    def _csv(self, entry: dict):
        exists = TRACKER_FILE.exists()
        try:
            with open(TRACKER_FILE, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(entry.keys()))
                if not exists: w.writeheader()
                w.writerow(entry)
        except Exception as e: log.error(f"csv write: {e}")

    def brier_score(self) -> float:
        resolved = [b for b in self.data["bets"] if b.get("outcome") is not None]
        if not resolved: return float("nan")
        return float(np.mean([(b["model_prob"] - b["outcome"])**2 for b in resolved]))

    def weekly_summary(self) -> str:
        cutoff  = (datetime.now() - timedelta(days=7)).isoformat()
        recent  = [b for b in self.data["bets"] if b.get("ts","") > cutoff]
        resolved= [b for b in recent if b.get("outcome") is not None]
        wins    = sum(1 for b in resolved if b.get("outcome") == 1)
        wagered = sum(b.get("bet_size",0) or 0 for b in resolved)
        pnl     = sum(b.get("pnl",0) or 0 for b in resolved)
        roi     = (pnl / wagered * 100) if wagered > 0 else 0.0
        wr      = f"{wins}/{len(resolved)} ({100*wins/len(resolved):.1f}%)" if resolved else "0/0"
        bs      = f"{self.brier_score():.4f}"

        # CLV analysis
        clv_bets = [b for b in recent if b.get("clv") is not None]
        avg_clv  = (sum(b["clv"] for b in clv_bets) / len(clv_bets)) if clv_bets else None
        clv_by_sport = {}
        clv_by_type  = {}
        for b in clv_bets:
            sp = b.get("sport","?")
            mt = "TOTAL" if b.get("market_type","").startswith(("OVER","UNDER")) else "ML"
            clv_by_sport.setdefault(sp,  []).append(b["clv"])
            clv_by_type.setdefault(mt,   []).append(b["clv"])

        lines = [
            "", Fore.WHITE + Style.BRIGHT + _bar(),
            f"  WEEKLY SUMMARY — {datetime.now().strftime('%Y-%m-%d')}".center(W),
            "  " + "─" * (W-2),
            _fld("Bets placed:", str(len(recent))),
            _fld("Resolved:", str(len(resolved))),
            _fld("Win rate:", wr),
            _fld("ROI:", f"{roi:+.1f}%"),
            _fld("Brier score:", bs),
        ]

        if avg_clv is not None:
            lines.append("  " + "─" * (W-2))
            lines.append(f"  CLOSING LINE VALUE (CLV)".center(W))
            clv_pct = avg_clv * 100
            lines.append(_fld("Avg CLV:", f"{clv_pct:+.2f}¢"))
            for sp, vals in clv_by_sport.items():
                avg = sum(vals)/len(vals)*100
                lines.append(_fld(f"  {sp}:", f"{avg:+.2f}¢ ({len(vals)} bets)"))
            for mt, vals in clv_by_type.items():
                avg = sum(vals)/len(vals)*100
                lines.append(_fld(f"  {mt}:", f"{avg:+.2f}¢ ({len(vals)} bets)"))
            if avg_clv < 0:
                lines.append(Fore.RED + "  WARNING: Model may be finding false edges — review coefficients")
            else:
                lines.append(Fore.GREEN + f"  Model confirmed: beating closing line by {clv_pct:+.2f}¢ on average")

        lines += [Fore.WHITE + Style.BRIGHT + _bar(), Style.RESET_ALL]
        return "\n".join(lines)

# ══════════════════════════════════════════════════════
# SECTION 15b — MODEL TRAINER (Logistic Regression)
# ══════════════════════════════════════════════════════
class ModelTrainer:
    """Retrains model weights from bet_tracker.csv using logistic regression."""
    MODEL_FILE = CACHE_DIR / "trained_model.json"

    def should_retrain(self) -> bool:
        if not self.MODEL_FILE.exists(): return True
        age_days = (datetime.now() - datetime.fromtimestamp(
            self.MODEL_FILE.stat().st_mtime)).days
        return age_days >= 30

    def train(self) -> Optional[dict]:
        if not _SKLEARN: return None
        if not TRACKER_FILE.exists(): return None
        try:
            import csv as _csv
            rows = []
            with open(TRACKER_FILE) as f:
                reader = _csv.DictReader(f)
                for row in reader:
                    if row.get("outcome") not in ("0","1"): continue
                    rows.append(row)
            if len(rows) < 20:
                return None

            features = ["model_prob", "kalshi_price", "edge"]
            X = np.array([[float(r.get(f,0) or 0) for f in features] for r in rows])
            y = np.array([int(r["outcome"]) for r in rows])

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = LogisticRegression(max_iter=1000, random_state=42)
            model.fit(X_scaled, y)

            importance = dict(zip(features, model.coef_[0].tolist()))
            result = {
                "n_bets": len(rows),
                "accuracy": float(model.score(X_scaled, y)),
                "feature_importance": importance,
                "trained_at": datetime.now().isoformat(),
            }
            self.MODEL_FILE.write_text(json.dumps(result, indent=2))
            return result
        except Exception as e:
            log.warning(f"ModelTrainer.train: {e}")
            return None

    def report(self) -> str:
        if not self.MODEL_FILE.exists(): return ""
        try:
            d = json.loads(self.MODEL_FILE.read_text())
            lines = [
                f"\n  MODEL TRAINING ({d.get('trained_at','')[:10]})",
                f"  Trained on {d['n_bets']} bets — accuracy {d['accuracy']*100:.1f}%",
                "  Feature importance:",
            ]
            for k, v in d.get("feature_importance",{}).items():
                lines.append(f"    {k:<20s} {v:+.4f}")
            return "\n".join(lines)
        except Exception:
            return ""

# ══════════════════════════════════════════════════════
# SECTION 16 — MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════
class EdgeFinder:
    def __init__(self, bankroll: float = DEFAULT_BANKROLL, kalshi_key: str = ""):
        self.bankroll   = bankroll
        self.nst        = NSTScraper()
        self.ctg        = CTGScraper()
        self.inj_rep    = InjuryReporter()
        self.kalshi     = KalshiClient(kalshi_key)
        self.nhl_model  = NHLModel()
        self.nba_model  = NBAModel()
        self.prop_model = PlayerPropModel()
        self.detector   = EdgeDetector(bankroll)
        self.cal        = Calibration()
        self.live       = LiveScoreFetcher()
        self.rest_fetcher     = RestDayFetcher()
        self.nhl_standings    = NHLStandingsFetcher()
        self.hist       = HistoricalRates()
        self.polymarket = PolymarketClient()
        self.trainer    = ModelTrainer()
        self.goalies    = GoalieChecker()
        self._prev_cats: Dict[str, str] = {}
        self._lock      = threading.Lock()
        self._hist_rates = self.hist.rates()

    # ── fetch all sources concurrently ──────────────────
    def _fetch_all(self) -> dict:
        results: dict = {}

        def run(key, fn):
            try: results[key] = fn()
            except Exception as e:
                log.error(f"fetch {key}: {e}")
                results[key] = {} if key.endswith("_teams") or key.endswith("_goalies") else []

        workers = [
            threading.Thread(target=run, args=("nhl_teams",   self.nst.team_stats),            daemon=True),
            threading.Thread(target=run, args=("nhl_goalies", self.nst.goalie_stats),          daemon=True),
            threading.Thread(target=run, args=("nba_teams",   self.ctg.team_stats),            daemon=True),
            threading.Thread(target=run, args=("injuries",    self.inj_rep.fetch),             daemon=True),
            threading.Thread(target=run, args=("kalshi",      self.kalshi.markets),            daemon=True),
            threading.Thread(target=run, args=("live",        self.live.fetch),                daemon=True),
            threading.Thread(target=run, args=("rest",        self.rest_fetcher.fetch),        daemon=True),
            threading.Thread(target=run, args=("nhl_pts",    self.nhl_standings.fetch),       daemon=True),
            threading.Thread(target=run, args=("polymarket",  self.polymarket.nba_nhl_markets),daemon=True),
        ]
        for w in workers: w.start()
        for w in workers: w.join(timeout=45)
        return results

    # ── analyze one Kalshi market ────────────────────────
    def _analyze(self, mkt: KalshiMarket,
                 nhl_teams, nhl_goalies, nba_teams,
                 injuries: List[InjuryReport],
                 live_games: Dict[str, LiveGame],
                 poly_prices: Dict[str, float]) -> Optional[BetRecommendation]:

        move_detail = self.kalshi.movement_detail(mkt.ticker)
        mv1 = move_detail["mv1h"]
        mv2 = move_detail["mv2h"]
        notes: List[str] = []
        model_prob: Optional[float] = None
        price = mkt.yes_price
        label = mkt.market_type
        bet_side = "TOTAL"   # overridden below for ML bets
        goalie_warning = ""
        breakdown: dict = {}

        # ── Live game check ──────────────────────────────
        game_key = f"{mkt.away_abbr}@{mkt.home_abbr}"
        live_g = live_games.get(game_key) or live_games.get(f"{mkt.home_abbr}@{mkt.away_abbr}")
        is_live = live_g and live_g.status == "in"
        is_post = live_g and live_g.status == "post"

        if is_post:
            return None   # game over

        # is_live: model still runs; category overridden to LIVE-SKIP below

        _rest    = getattr(self, '_rest_data', {})
        _nhl_pts = getattr(self, '_nhl_pts', {})

        def _nhl(abbr, full):
            s = _find_nhl(nhl_teams, abbr) if nhl_teams else NHLTeamStats(team=abbr)
            if s.team == abbr: s = _find_nhl(nhl_teams, full)
            rd = _rest.get(abbr.upper())
            if rd: s.rest_days, s.last_played = rd
            if abbr.upper() in _nhl_pts:
                s.pts_pct = _nhl_pts[abbr.upper()]
            return s

        def _nba(abbr, full):
            s = _find_nba(nba_teams, abbr) if nba_teams else NBATeamStats(team=abbr)
            if s.team == abbr: s = _find_nba(nba_teams, full)
            rd = _rest.get(abbr.upper())
            if rd: s.rest_days, s.last_played = rd
            return s

        def _apply_series_state(home_s, away_s,
                                home_abbr: str, away_abbr: str) -> None:
            """Populate series_wins/losses on either NHL or NBA team stats objects."""
            key = f"{away_abbr}@{home_abbr}"
            state = _SERIES_STATE.get(key)
            if state:
                aw, hw = state
                away_s.series_wins   = aw; away_s.series_losses  = hw
                home_s.series_wins   = hw; home_s.series_losses   = aw

        if mkt.sport == "NHL":
            hs  = _nhl(mkt.home_abbr, mkt.home_team)
            aws = _nhl(mkt.away_abbr, mkt.away_team)
            hg  = _find_goalie(nhl_goalies, mkt.home_abbr) or _find_goalie(nhl_goalies, mkt.home_team)
            ag  = _find_goalie(nhl_goalies, mkt.away_abbr) or _find_goalie(nhl_goalies, mkt.away_team)
            hs.is_home, aws.is_home = True, False
            _apply_series_state(hs, aws, mkt.home_abbr, mkt.away_abbr)
            nhl_game_num = hs.series_wins + hs.series_losses + 1

            if mkt.market_type == "ML":
                goalie_warning = self.goalies.check(mkt.home_team, mkt.away_team)
                home_win = self.nhl_model.moneyline(hs, aws, hg, ag, injuries, notes)
                if is_live and live_g:
                    home_win = self.live.live_win_prob(live_g, home_win)
                    notes.insert(0, f"LIVE P{live_g.period} {live_g.clock}  {live_g.away_score}-{live_g.home_score}")
                if mkt.yes_side == "HOME":
                    model_prob = home_win; label = f"ML — {mkt.home_abbr} wins"
                    bet_side = "HOME"
                    notes.insert(0, f"HOME: {mkt.home_abbr} (base {NHL_HOME_BASE*100:.0f}%)")
                else:
                    model_prob = 1.0 - home_win; label = f"ML — {mkt.away_abbr} wins"
                    bet_side = "AWAY"
                    notes.insert(0, f"AWAY: {mkt.away_abbr} (home base {NHL_HOME_BASE*100:.0f}% applied)")

            elif mkt.market_type == "TOTAL" and mkt.total_line:
                over_p, lam, breakdown = self.nhl_model.total(hs, aws, hg, ag, mkt.total_line, nhl_game_num, notes)
                if over_p >= price:
                    model_prob = over_p; label = f"OVER {int(mkt.total_line)}"
                else:
                    model_prob = 1.0 - over_p; price = 1.0 - price
                    label = f"UNDER {int(mkt.total_line)}"
                breakdown["home_abbr"] = mkt.home_abbr
                breakdown["away_abbr"] = mkt.away_abbr

        elif mkt.sport == "NBA":
            hs  = _nba(mkt.home_abbr, mkt.home_team)
            aws = _nba(mkt.away_abbr, mkt.away_team)
            hs.is_home, aws.is_home = True, False
            _apply_series_state(hs, aws, mkt.home_abbr, mkt.away_abbr)

            if mkt.market_type == "ML":
                home_win = self.nba_model.moneyline(hs, aws, injuries, notes)
                if is_live and live_g:
                    home_win = self.live.live_win_prob(live_g, home_win)
                    notes.insert(0, f"LIVE Q{live_g.period} {live_g.clock}  {live_g.away_score}-{live_g.home_score}")
                if mkt.yes_side == "HOME":
                    model_prob = home_win; label = f"ML — {mkt.home_abbr} wins"
                    bet_side = "HOME"
                    notes.insert(0, f"HOME: {mkt.home_abbr} (base {NBA_HOME_BASE*100:.0f}%)")
                else:
                    model_prob = 1.0 - home_win; label = f"ML — {mkt.away_abbr} wins"
                    bet_side = "AWAY"
                    notes.insert(0, f"AWAY: {mkt.away_abbr} (home base {NBA_HOME_BASE*100:.0f}% applied)")

            elif mkt.market_type == "TOTAL" and mkt.total_line:
                over_p, exp, breakdown = self.nba_model.total(hs, aws, mkt.total_line, injuries, notes)
                notes.insert(0, f"Expected {exp:.0f} pts vs line {mkt.total_line:.0f}")
                if over_p >= price:
                    model_prob = over_p; label = f"OVER {int(mkt.total_line)}"
                else:
                    model_prob = 1.0 - over_p; price = 1.0 - price
                    label = f"UNDER {int(mkt.total_line)}"
                breakdown["home_abbr"] = mkt.home_abbr
                breakdown["away_abbr"] = mkt.away_abbr

            elif mkt.market_type == "SPREAD" and mkt.spread_line is not None:
                cover_p = self.nba_model.spread(hs, aws, mkt.spread_line, injuries, notes)
                win_margin = abs(mkt.spread_line)
                if mkt.yes_side == "HOME_COVER":
                    label = f"ATS — {mkt.home_abbr} wins by {win_margin:.1f}+"
                    model_prob = cover_p; bet_side = "HOME"
                else:
                    label = f"ATS — {mkt.away_abbr} wins by {win_margin:.1f}+"
                    model_prob = 1.0 - cover_p; bet_side = "AWAY"

            elif mkt.market_type == "PROP" and mkt.total_line and mkt.prop_player_full:
                # Wembanyama gets a tailored model; others get the generic one
                fox_out    = any(_fuzzy_player(i.player, "De'Aaron Fox")    and i.status in ("OUT","DOUBTFUL") for i in injuries)
                harper_out = any(_fuzzy_player(i.player, "Dylan Harper")    and i.status in ("OUT","DOUBTFUL") for i in injuries)
                if "wembanyama" in mkt.prop_player_full.lower() and mkt.prop_type == "PTS":
                    model_prob = self.prop_model.wembanyama_points(
                        mkt.total_line, aws, fox_out, harper_out, injuries, notes)
                else:
                    model_prob = self.prop_model.over_prob(
                        mkt.prop_player_full, mkt.prop_type, mkt.total_line,
                        aws, injuries, notes)
                label = f"PROP {mkt.prop_player_full} O{mkt.total_line:.1f} {mkt.prop_type}"
                if model_prob < price:
                    model_prob = 1.0 - model_prob; price = 1.0 - price
                    label = label.replace(" O", " U")

        # NHL SPREAD (puck line) block
        if mkt.sport == "NHL" and mkt.market_type == "SPREAD" and mkt.spread_line is not None:
            hs  = _nhl(mkt.home_abbr, mkt.home_team)
            aws = _nhl(mkt.away_abbr, mkt.away_team)
            hg  = _find_goalie(nhl_goalies, mkt.home_abbr) or _find_goalie(nhl_goalies, mkt.home_team)
            ag  = _find_goalie(nhl_goalies, mkt.away_abbr) or _find_goalie(nhl_goalies, mkt.away_team)
            hs.is_home, aws.is_home = True, False
            cover_p = self.nhl_model.puck_line(hs, aws, hg, ag, mkt.spread_line, notes)
            win_margin = abs(mkt.spread_line)
            if mkt.yes_side == "HOME_COVER":
                label = f"PL — {mkt.home_abbr} wins by {win_margin:.1f}+"
                model_prob = cover_p; bet_side = "HOME"
            else:
                label = f"PL — {mkt.away_abbr} wins by {win_margin:.1f}+"
                model_prob = 1.0 - cover_p; bet_side = "AWAY"

        if model_prob is None:
            return None

        # Collect injury flags for the teams in this game
        inj_flags = []
        for inj in injuries:
            if _fuzzy(inj.team, mkt.home_team) or _fuzzy(inj.team, mkt.away_team):
                pct = abs(inj.win_prob_impact) * 100
                inj_flags.append(
                    f"INJURY EDGE: {inj.player} {inj.status} → "
                    f"{inj.team.split()[-1] if inj.team else '?'} -{pct:.1f}% win prob | "
                    f"Market price may not reflect this yet"
                )

        game_str = f"{mkt.away_abbr} @ {mkt.home_abbr}  ({mkt.away_team} @ {mkt.home_team})"
        rec = self.detector.evaluate(
            model_prob=model_prob, kalshi_price=price,
            game=game_str, sport=mkt.sport, mtype=label,
            notes=notes, mv1=mv1, mv2=mv2,
            move_detail=move_detail,
            injury_flags=inj_flags,
        )
        rec.bet_side = bet_side
        rec.goalie_warning = goalie_warning
        rec.factor_breakdown = breakdown

        # ── Away ML threshold: require 12% edge minimum ──
        if bet_side == "AWAY" and mkt.market_type == "ML":
            if rec.edge < _MIN_EDGE_AWAY_ML and rec.category not in ("LIVE-SKIP", "DATA_ERROR"):
                rec.category = "SKIP"
                rec.bet_size  = 0.0
                rec.bias_notes.insert(0,
                    f"AWAY ML below 12% threshold (edge {rec.edge*100:.1f}%) — skip")

        # ── Goalie unconfirmed: block STRONG BET, reduce confidence ──
        if goalie_warning:
            rec.goalie_warning = goalie_warning
            rec.bias_notes.append(goalie_warning)
            if rec.category == "STRONG_BET":
                rec.category = "BET"   # downgrade until goalies confirmed
                rec.bet_size = round((rec.kelly_fraction / 2) * self.bankroll, 2)
            if rec.confidence == "HIGH":
                rec.confidence = "MEDIUM"
            elif rec.confidence == "MEDIUM":
                rec.confidence = "LOW"

        # ── Live game override ────────────────────────────
        if is_live:
            rec.category = "LIVE-SKIP"
            rec.bet_size  = 0.0

        # ── Data error flag ──────────────────────────────
        # Props are less reliable → higher threshold before flagging as DATA_ERROR
        _data_err_thresh = 0.35 if mkt.market_type == "PROP" else 0.25
        if rec.edge > _data_err_thresh:
            rec.category = "DATA_ERROR"
            rec.bet_size  = 0.0
            rec.bias_notes.insert(0, "DATA ERROR — VERIFY MANUALLY")

        # ── Polymarket comparison ────────────────────────
        poly_p = self.polymarket.find_match(mkt.home_team, mkt.away_team, poly_prices)
        if poly_p is not None:
            rec.bias_notes.append(f"Polymarket: ${poly_p:.2f} vs Kalshi ${mkt.yes_price:.2f}")
            if abs(poly_p - price) >= 0.03:
                cheaper = "Polymarket" if poly_p < price else "Kalshi"
                rec.bias_notes.append(f"Arb: bet {cheaper} (cheaper by {abs(poly_p-price)*100:.1f}¢)")

        return rec

    # ── main run ─────────────────────────────────────────
    def run(self) -> List[BetRecommendation]:
        ts = datetime.now().strftime("%H:%M:%S")
        print(Fore.CYAN + f"[{ts}] Fetching data…", flush=True)
        data = self._fetch_all()

        mkts        = data.get("kalshi", [])
        nhl_teams   = data.get("nhl_teams", {})
        nhl_goalies = data.get("nhl_goalies", {})
        nba_teams   = data.get("nba_teams", {})
        injuries    = data.get("injuries", [])
        live_games  = data.get("live", {})
        poly_prices = data.get("polymarket", {})
        self._rest_data    = data.get("rest", {})
        self._nhl_pts      = data.get("nhl_pts", {})

        if not mkts:
            print(Fore.YELLOW + "  [!] No Kalshi markets — check KALSHI_API_KEY.")

        raw_recs = []
        for mkt in mkts:
            try:
                r = self._analyze(mkt, nhl_teams, nhl_goalies, nba_teams,
                                  injuries, live_games, poly_prices)
                if r: raw_recs.append(r)
            except Exception as e:
                log.error(f"analyze {mkt.ticker}: {e}")

        # Deduplicate: for each (teams, market_category) keep highest-edge rec.
        # ML     bucket: "OKC @ SAS | ML"
        # TOTAL  bucket: "OKC @ SAS | TOTAL"
        # SPREAD bucket: "OKC @ SAS | SPREAD"
        # PROP   bucket: "OKC @ SAS | PROP:WEMB_PTS"
        best: Dict[str, BetRecommendation] = {}
        for r in raw_recs:
            teams_part = r.game.split("(")[0].strip()
            mtype_base = r.market_type.split("—")[0].strip()
            if mtype_base.startswith(("OVER","UNDER")):
                mtype_base = "TOTAL"
            elif mtype_base.startswith(("ATS", "PL")):
                mtype_base = "SPREAD"
            elif mtype_base.startswith("PROP"):
                # Bucket = PROP:{player}:{stat_type} — best line per player per stat
                words = mtype_base.split()
                # Format: "PROP {player_full} O{line} {type}"
                # Extract player (words 1..n-2) and type (last word)
                player_part = " ".join(words[1:-2]) if len(words) >= 4 else "?"
                stat_part   = words[-1] if len(words) >= 2 else "PTS"
                mtype_base  = f"PROP:{player_part}:{stat_part}"
            bucket = f"{teams_part}|{mtype_base}"
            if bucket not in best or r.edge > best[bucket].edge:
                best[bucket] = r

        recs = list(best.values())

        # Store all spread recs (before dedup) for the summary table
        self._all_spread_recs = sorted(
            [r for r in raw_recs if r.market_type.startswith(("ATS", "PL"))],
            key=lambda r: -r.edge)

        # ── Tonight's game coverage summary ─────────────────
        self._print_tonight_coverage(raw_recs, nba_teams)

        # ── Combo detection ─────────────────────────────────
        self._print_combos(recs)

        # Print injury status for watched players
        _WATCH = ["Jalen Williams", "Dylan Harper", "De'Aaron Fox",
                  "Shai Gilgeous-Alexander", "Chet Holmgren", "Victor Wembanyama"]
        watch_found = []
        for inj in injuries:
            for w in _WATCH:
                if _fuzzy_player(inj.player, w):
                    watch_found.append(f"  {inj.player} ({inj.team}): {inj.status} — {inj.injury or 'N/A'}")
        if watch_found:
            print(Fore.RED + Style.BRIGHT + "\n  WATCHED PLAYER INJURY REPORT:")
            for line in watch_found:
                print(Fore.RED + line)
            print()
        else:
            print(Fore.GREEN + "  Watched players (Williams, Harper, Fox): All active (no injury report)")

        # Record bettable recommendations
        for r in recs:
            if r.category in ("BET", "STRONG_BET"):
                self.cal.record(r)

        return recs

    def _print_tonight_coverage(self, raw_recs: List[BetRecommendation],
                                 nba_teams: dict) -> None:
        """Print a one-line summary for every game analyzed tonight."""
        # Group by game
        by_game: Dict[str, List[BetRecommendation]] = {}
        for r in raw_recs:
            key = r.game.split("(")[0].strip()
            by_game.setdefault(key, []).append(r)

        if not by_game:
            return

        print(Fore.WHITE + Style.BRIGHT + "\n  TONIGHT'S COVERAGE")
        print(Fore.WHITE + "  " + "─" * (W - 2))
        for game, grecs in sorted(by_game.items()):
            sport = grecs[0].sport if grecs else "?"
            # Best edge per market type
            best_edge: Dict[str, float] = {}
            for r in grecs:
                mt = r.market_type.split("—")[0].strip()
                if mt.startswith(("OVER","UNDER")): mt = "TOTAL"
                elif mt.startswith(("ATS","PL")): mt = "SPREAD"
                elif "ML" in mt: mt = "ML"
                best_edge[mt] = max(best_edge.get(mt, -99), r.edge)

            parts = []
            for mt in ("ML", "TOTAL", "SPREAD"):
                e = best_edge.get(mt)
                if e is None: continue
                col = (Fore.GREEN + Style.BRIGHT if e >= 0.07
                       else Fore.YELLOW if e >= 0.03
                       else Style.DIM)
                flag = " ✓" if e >= 0.07 else ""
                parts.append(col + f"{mt} {e*100:+.1f}%{flag}" + Style.RESET_ALL)

            edges_str = "  ".join(parts) if parts else Style.DIM + "no edge"
            # NBA stats warning
            stats_warn = ""
            if sport == "NBA" and not nba_teams:
                stats_warn = Fore.YELLOW + " [NBA stats unavailable — ML only]" + Style.RESET_ALL
            print(f"  {game:<22} {edges_str}{stats_warn}")
        print(Style.RESET_ALL)

    def _print_combos(self, recs: List[BetRecommendation]) -> None:
        """Print combo alerts when 2+ independent edges exist in the same game."""
        # Group by teams (game key)
        by_game: Dict[str, List[BetRecommendation]] = {}
        for r in recs:
            if r.category in ("SKIP", "DATA_ERROR", "LIVE-SKIP"): continue
            if r.edge < 0.07: continue
            game_key = r.game.split("(")[0].strip()
            by_game.setdefault(game_key, []).append(r)

        # Independent market pairs
        _INDEPENDENT = {
            ("ML", "TOTAL"), ("ML", "PROP"),
            ("SPREAD", "TOTAL"), ("TOTAL", "PROP"),
            ("ML", "SPREAD"),   # correlated but different markets
        }

        def _mcat(r: BetRecommendation) -> str:
            mt = r.market_type.split("—")[0].strip()
            if mt.startswith(("OVER","UNDER")): return "TOTAL"
            if mt.startswith(("ATS","PL")):     return "SPREAD"
            if mt.startswith("PROP"):           return "PROP"
            if "ML" in mt:                      return "ML"
            return mt

        for game, game_recs in by_game.items():
            if len(game_recs) < 2: continue

            combos = []
            for i, r1 in enumerate(game_recs):
                for r2 in game_recs[i+1:]:
                    c1, c2 = _mcat(r1), _mcat(r2)
                    pair = tuple(sorted((c1, c2)))
                    if pair in _INDEPENDENT:
                        combos.append((r1, r2))

            if combos:
                print(Fore.MAGENTA + Style.BRIGHT + "\n  ╔" + "═" * (W-4) + "╗")
                print(Fore.MAGENTA + Style.BRIGHT + f"  ║  COMBO ALERT — {game}".ljust(W-2) + "║")
                print(Fore.MAGENTA + Style.BRIGHT + "  ╠" + "═" * (W-4) + "╣")
                seen_pairs = set()
                for r1, r2 in combos:
                    pair_key = (id(r1), id(r2))
                    if pair_key in seen_pairs: continue
                    seen_pairs.add(pair_key)
                    # Combined EV: treat as independent bets
                    combined_ev = r1.ev_per_dollar + r2.ev_per_dollar
                    print(Fore.MAGENTA + f"  ║  {r1.market_type:<28} edge={r1.edge*100:+.1f}%  ${r1.bet_size:.0f}  ║")
                    print(Fore.MAGENTA + f"  ║  {r2.market_type:<28} edge={r2.edge*100:+.1f}%  ${r2.bet_size:.0f}  ║")
                    print(Fore.MAGENTA + f"  ║  Combined EV: +${combined_ev:.3f}/$ staked".ljust(W-2) + "║")
                print(Fore.MAGENTA + Style.BRIGHT + "  ╚" + "═" * (W-4) + "╝")
                print(Style.RESET_ALL)

    def _print_spread_summary(self, recs: List[BetRecommendation]) -> None:
        """Always show all analyzed spread markets regardless of edge threshold."""
        spread_recs = getattr(self, '_all_spread_recs', [])
        if not spread_recs:
            return
        print(Fore.CYAN + Style.BRIGHT + "\n  SPREAD / PUCK LINE ANALYSIS")
        print(Fore.CYAN + "  " + "─" * (W - 2))
        print(Fore.CYAN + f"  {'Game + Market':<40} {'Model':>7} {'Price':>7} {'Edge':>7}")
        print(Fore.CYAN + "  " + "─" * (W - 2))
        prev_game = ""
        for r in spread_recs:
            game_short = r.game.split("(")[0].strip()
            if game_short != prev_game:
                if prev_game:
                    print()
                prev_game = game_short
            edge_color = (Fore.GREEN + Style.BRIGHT if r.edge >= 0.07
                          else Fore.YELLOW if r.edge >= 0.03
                          else Fore.RED)
            flag = " ✓ BET" if r.edge >= 0.07 else ""
            mkt_label = r.market_type
            price = r.model_prob - r.edge
            print(edge_color +
                  f"  {mkt_label:<40} {r.model_prob*100:>6.1f}%  {price*100:>6.1f}%  {r.edge*100:>+6.1f}%{flag}")
        print(Style.RESET_ALL)

    def run_and_print(self) -> List[BetRecommendation]:
        recs = self.run()
        print_report(recs)
        self._print_spread_summary(recs)
        self._alert(recs)
        # Print coefficient comparison table once per session
        if not hasattr(self, '_coeff_printed'):
            self._coeff_printed = True
            print(self.hist.coeff_comparison(self._hist_rates))
        return recs

    # ── terminal alerts ──────────────────────────────────
    def _alert(self, recs: List[BetRecommendation]):
        with self._lock:
            for r in recs:
                key = r.game + "|" + r.market_type
                prev = self._prev_cats.get(key)

                # New edge ≥ 7% that wasn't there before
                if r.edge >= 0.07 and (prev is None or prev == "SKIP"):
                    print(Fore.GREEN + Style.BRIGHT +
                          f"  ⚡ NEW EDGE  {r.game}  {r.market_type}  +{r.edge*100:.1f}%")

                # Line moved ≥ 3¢
                if abs(r.mv_1h) >= 3.0:
                    direction = "toward" if (r.mv_1h > 0) == (r.edge > 0) else "against"
                    print(Fore.YELLOW + Style.BRIGHT +
                          f"  ⚡ LINE MOVE  {r.game}  {r.mv_1h:+.1f}¢ last hr ({direction} model)")

            self._prev_cats = {r.game+"|"+r.market_type: r.category for r in recs}

# ══════════════════════════════════════════════════════
# SECTION 17 — SCHEDULER
# ══════════════════════════════════════════════════════
def _run_scheduler(finder: EdgeFinder, cal: Calibration):
    schedule.every(30).minutes.do(finder.run_and_print)
    schedule.every().monday.at("08:00").do(lambda: print(cal.weekly_summary()))

    next_run = schedule.next_run()
    print(Fore.CYAN + f"  Scheduler active — next run at {next_run.strftime('%H:%M:%S')}")
    print(Fore.CYAN + "  Press Ctrl-C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print(Fore.CYAN + "\n  Stopped. Good luck.")

# ══════════════════════════════════════════════════════
# SECTION 18 — ENTRY POINT
# ══════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(
        description="edge_finder — NHL/NBA playoff betting edge detection")
    ap.add_argument("--bankroll",   type=float, default=DEFAULT_BANKROLL,
                    help=f"Bankroll in USD (default {DEFAULT_BANKROLL})")
    ap.add_argument("--kalshi-key", type=str,   default="",
                    help="Kalshi API key (or set KALSHI_API_KEY env var)")
    ap.add_argument("--once",       action="store_true",
                    help="Run once and exit")
    ap.add_argument("--weekly",     action="store_true",
                    help="Print weekly ROI summary and exit")
    ap.add_argument("--discover",   action="store_true",
                    help="Discover available Kalshi series and exit")
    args = ap.parse_args()

    print(Fore.WHITE + Style.BRIGHT + "\n" + _bar())
    print(Fore.WHITE + Style.BRIGHT + "  EDGE FINDER  —  NHL · NBA Playoff Analysis".center(W))
    print(Fore.WHITE + Style.BRIGHT + f"  Bankroll: ${args.bankroll:.2f}   Season: {SEASON}".center(W))
    print(Fore.WHITE + Style.BRIGHT + _bar() + "\n")

    key    = args.kalshi_key or os.getenv("KALSHI_API_KEY", "")
    finder = EdgeFinder(bankroll=args.bankroll, kalshi_key=key)

    if args.discover:
        print(Fore.CYAN + "\n  Probing Kalshi API for sport-related series…")
        series = finder.kalshi.discover_sports_series()
        if series:
            print(Fore.GREEN + f"  Found {len(series)} series:")
            for s in series:
                print(f"    {s}")
        else:
            print(Fore.YELLOW + "  No NBA/NHL series found (check API key or try later).")
        return

    if args.weekly:
        print(finder.cal.weekly_summary())
        return

    finder.run_and_print()

    if not args.once:
        _run_scheduler(finder, finder.cal)

if __name__ == "__main__":
    main()
