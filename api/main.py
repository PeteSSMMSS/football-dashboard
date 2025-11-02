"""
FastAPI Backend für Fußball-Dashboard
Endpoints: /api/bundesliga, /api/champions-league, /api/dfb-pokal
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Dict, List, Any
import requests
import logging
from functools import lru_cache

# ============================================================================
# KONFIGURATION
# ============================================================================

app = FastAPI(
    title="Fußball Dashboard API",
    description="API für Bundesliga, Champions League und DFB-Pokal Spieltermine",
    version="1.0.0"
)

# CORS für lokale Entwicklung
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konstanten
OPENLIGA_BASE = "https://api.openligadb.de"
ESPN_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/uefa.champions"
ESPN_DFB_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/ger.dfb_pokal"
ESPN_WM_QUALI_BASE = "https://site.web.api.espn.com/apis/site/v2/sports/soccer/fifa.worldq.uefa"
BERLIN_TZ = ZoneInfo("Europe/Berlin")
CACHE_TTL = 3600  # 1 Stunde Cache

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def to_berlin(dt_iso: str) -> datetime:
    """Konvertiert ISO datetime string zu Berlin Zeit"""
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
    except Exception:
        dt = datetime.fromisoformat(dt_iso)
    return dt.astimezone(BERLIN_TZ)

def current_season_year(now_berlin: datetime) -> int:
    """Berechnet Saison-Jahr (Pokal/Bundesliga)"""
    return now_berlin.year if now_berlin.month >= 7 else now_berlin.year - 1

def weekday_german(dt: datetime) -> str:
    """Gibt deutschen Wochentag zurück"""
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    return days[dt.weekday()]

def format_match(
    date: datetime,
    team_home: str,
    team_away: str,
    location: str = "",
    extra: Dict = None
) -> Dict[str, Any]:
    """Formatiert Match-Daten einheitlich"""
    return {
        "date": date.isoformat(),
        "date_readable": date.strftime("%d.%m.%Y"),
        "time": date.strftime("%H:%M"),
        "weekday": date.strftime("%A"),
        "team_home": team_home,
        "team_away": team_away,
        "location": location,
        **(extra or {})
    }

# ============================================================================
# BUNDESLIGA ENDPOINT
# ============================================================================

@lru_cache(maxsize=1)
def _fetch_bundesliga_cached(cache_key: str) -> List[Dict]:
    """Cached Bundesliga-Daten (Cache invalidiert stündlich via cache_key)"""
    try:
        now = datetime.now(BERLIN_TZ)
        season = current_season_year(now)
        
        url = f"{OPENLIGA_BASE}/getmatchdata/bl1/{season}"
        logger.info(f"Fetching Bundesliga: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        matches = r.json()
        
        # Filtere zukünftige Spiele
        future_matches = []
        for m in matches:
            match_date_str = m.get("matchDateTime")
            if match_date_str:
                try:
                    match_dt = to_berlin(match_date_str)
                    if match_dt.date() >= now.date():
                        group = m.get("group") or {}
                        team1 = m.get("team1") or {}
                        team2 = m.get("team2") or {}
                        location = m.get("location") or {}
                        
                        future_matches.append(
                            format_match(
                                date=match_dt,
                                team_home=team1.get("teamName", "Unbekannt"),
                                team_away=team2.get("teamName", "Unbekannt"),
                                location=location.get("locationCity", ""),
                                extra={
                                    "matchday": group.get("groupOrderID", 0),
                                    "finished": m.get("matchIsFinished", False)
                                }
                            )
                        )
                except Exception as e:
                    logger.warning(f"Error parsing match: {e}")
                    continue
        
        # Sortiere nach Datum
        future_matches.sort(key=lambda x: x["date"])
        return future_matches[:20]  # Max 20 Spiele
        
    except Exception as e:
        logger.error(f"Error fetching Bundesliga: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bundesliga")
async def get_bundesliga():
    """Gibt die nächsten Bundesliga-Spiele zurück"""
    # Cache-Key basiert auf aktueller Stunde -> Cache invalidiert stündlich
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "1. Bundesliga",
        "matches": _fetch_bundesliga_cached(cache_key)
    }

# ============================================================================
# CHAMPIONS LEAGUE ENDPOINT
# ============================================================================

@lru_cache(maxsize=1)
def _fetch_champions_league_cached(cache_key: str) -> List[Dict]:
    """Cached Champions League-Daten"""
    try:
        now = datetime.now(BERLIN_TZ)
        
        url = f"{ESPN_BASE}/scoreboard"
        logger.info(f"Fetching Champions League: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        events = data.get("events", [])
        future_matches = []
        
        for event in events:
            try:
                date_str = event.get("date", "")
                if not date_str:
                    continue
                    
                match_dt = to_berlin(date_str)
                
                # Extrahiere Teams
                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                    
                competition = competitions[0]
                competitors = competition.get("competitors", [])
                if len(competitors) < 2:
                    continue
                
                home_team = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away_team = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                
                team1_name = home_team.get("team", {}).get("displayName", "")
                team2_name = away_team.get("team", {}).get("displayName", "")
                
                # Status
                status_info = competition.get("status", {})
                status_type = status_info.get("type", {})
                is_finished = status_type.get("completed", False)
                
                # Venue
                venue_info = competition.get("venue", {})
                venue = venue_info.get("fullName", "")
                
                if match_dt.date() >= now.date():
                    future_matches.append(
                        format_match(
                            date=match_dt,
                            team_home=team1_name,
                            team_away=team2_name,
                            location=venue,
                            extra={
                                "finished": is_finished,
                                "status": status_type.get("shortDetail", "Scheduled")
                            }
                        )
                    )
                    
            except Exception as e:
                logger.warning(f"Error parsing event: {e}")
                continue
        
        # Sortiere nach Datum
        future_matches.sort(key=lambda x: x["date"])
        return future_matches[:20]  # Max 20 Spiele
        
    except Exception as e:
        logger.error(f"Error fetching Champions League: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/champions-league")
async def get_champions_league():
    """Gibt die nächsten Champions League-Spiele zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "Champions League",
        "matches": _fetch_champions_league_cached(cache_key)
    }

# ============================================================================
# DFB-POKAL ENDPOINT (HYBRID: OpenLigaDB + ESPN)
# ============================================================================

@lru_cache(maxsize=1)
def _fetch_dfb_pokal_cached(cache_key: str) -> List[Dict]:
    """
    Cached DFB-Pokal-Daten - HYBRID Strategie:
    1. OpenLigaDB für ALLE Spiele (vergangen + zukünftig falls vorhanden)
    2. ESPN für zusätzliche/neuere Spiele
    3. ESPN Calendar für Termine ohne Teams
    """
    try:
        now = datetime.now(BERLIN_TZ)
        season = current_season_year(now)
        all_matches = []
        
        # ========== STRATEGIE 1: OpenLigaDB - ALLE Spiele laden ==========
        try:
            openliga_url = f"{OPENLIGA_BASE}/getmatchdata/dfb/{season}"
            logger.info(f"Fetching DFB-Pokal from OpenLigaDB: {openliga_url}")
            
            r = requests.get(openliga_url, timeout=20)
            r.raise_for_status()
            matches = r.json()
            
            logger.info(f"OpenLigaDB: {len(matches)} Spiele gefunden")
            
            # Parse ALLE Spiele (vergangen UND zukünftig)
            for m in matches:
                match_date_str = m.get("matchDateTime")
                if match_date_str:
                    try:
                        match_dt = to_berlin(match_date_str)
                        
                        group = m.get("group") or {}
                        team1 = m.get("team1") or {}
                        team2 = m.get("team2") or {}
                        location = m.get("location") or {}
                        is_finished = m.get("matchIsFinished", False)
                        
                        # Score für beendete Spiele
                        score = None
                        if is_finished:
                            results = m.get("matchResults") or []
                            if results:
                                final = results[-1]  # Letztes Ergebnis = Endergebnis
                                p1 = final.get("pointsTeam1")
                                p2 = final.get("pointsTeam2")
                                if p1 is not None and p2 is not None:
                                    score = f"{p1}:{p2}"
                        
                        all_matches.append(
                            format_match(
                                date=match_dt,
                                team_home=team1.get("teamName", "Unbekannt"),
                                team_away=team2.get("teamName", "Unbekannt"),
                                location=location.get("locationCity", ""),
                                extra={
                                    "round": group.get("groupName", ""),
                                    "finished": is_finished,
                                    "score": score,
                                    "status": "Final" if is_finished else "Scheduled"
                                }
                            )
                        )
                    except Exception as e:
                        logger.warning(f"Error parsing OpenLigaDB match: {e}")
                        continue
                        
        except Exception as e:
            logger.warning(f"OpenLigaDB fetch failed: {e}")
        
        # ========== STRATEGIE 2: ESPN für zusätzliche Spiele ==========
        url = f"{ESPN_BASE.replace('uefa.champions', 'ger.dfb_pokal')}/scoreboard"
        logger.info(f"Fetching DFB-Pokal from ESPN: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        events = data.get("events", [])
        
        events = data.get("events", [])
        espn_match_ids = set()
        
        # Parse ESPN Spiele (ergänzend zu OpenLigaDB)
        for event in events:
            try:
                date_str = event.get("date", "")
                if not date_str:
                    continue
                    
                match_dt = to_berlin(date_str)
                event_id = f"{match_dt.date()}_{event.get('id', '')}"
                
                # Skip wenn schon von OpenLigaDB
                if event_id in espn_match_ids:
                    continue
                espn_match_ids.add(event_id)
                
                # Extrahiere Teams
                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                    
                competition = competitions[0]
                competitors = competition.get("competitors", [])
                if len(competitors) < 2:
                    continue
                
                home_team = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away_team = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                
                team1_name = home_team.get("team", {}).get("displayName", "")
                team2_name = away_team.get("team", {}).get("displayName", "")
                
                # Status & Scores
                status_info = competition.get("status", {})
                status_type = status_info.get("type", {})
                is_finished = status_type.get("completed", False)
                
                score1 = str(home_team.get("score", "")) if home_team.get("score") is not None else ""
                score2 = str(away_team.get("score", "")) if away_team.get("score") is not None else ""
                
                # Venue
                venue_info = competition.get("venue", {})
                venue = venue_info.get("fullName", "")
                
                # Round info
                season_info = event.get("season", {})
                round_info = season_info.get("type", {})
                round_name = round_info.get("name", "")
                
                all_matches.append(
                    format_match(
                        date=match_dt,
                        team_home=team1_name,
                        team_away=team2_name,
                        location=venue,
                        extra={
                            "round": round_name,
                            "finished": is_finished,
                            "status": status_type.get("shortDetail", "Scheduled"),
                            "score": f"{score1}:{score2}" if is_finished and score1 and score2 else None
                        }
                    )
                )
                    
            except Exception as e:
                logger.warning(f"Error parsing ESPN event: {e}")
                continue
        
        # ========== STRATEGIE 3: Zukünftige Runden als Platzhalter ==========
        future_exists = any(not m.get("finished", False) for m in all_matches)
        
        if not future_exists and len(all_matches) > 0:
            # Hole Calendar-Termine für ALLE zukünftigen Runden aus ESPN
            try:
                leagues = data.get("leagues", [])
                if leagues:
                    calendar = leagues[0].get("calendar", [{}])[0]
                    entries = calendar.get("entries", [])
                    
                    # Finde aktuelle Runde
                    current_round = leagues[0].get("season", {}).get("type", {})
                    current_round_value = int(current_round.get("id", "0"))
                    
                    logger.info(f"Aktuelle Runde: {current_round.get('name')} (ID: {current_round_value})")
                    
                    # Füge ALLE zukünftigen Runden als Platzhalter hinzu
                    for entry in entries:
                        entry_value = int(entry.get("value", "0"))
                        # Nur Runden >= aktueller Runde
                        if entry_value >= current_round_value:
                            label = entry.get("label", "TBD")
                            detail = entry.get("detail", "TBD")
                            
                            # Deutsche Übersetzung für Runden
                            round_map = {
                                "Rd of 16": "Achtelfinale",
                                "Round of 16": "Achtelfinale",
                                "Quarterfinals": "Viertelfinale",
                                "Semifinals": "Halbfinale",
                                "Final": "Finale"
                            }
                            round_name_de = round_map.get(label, label)
                            
                            logger.info(f"Platzhalter: {round_name_de} ({detail})")
                            
                            # Erstelle Platzhalter für jede Runde
                            all_matches.append({
                                "date": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                                "date_readable": detail,
                                "time": "TBD",
                                "weekday": "",
                                "team_home": "Noch nicht ausgelost",
                                "team_away": "Noch nicht ausgelost",
                                "location": "",
                                "round": round_name_de,
                                "finished": False,
                                "status": f"📅 Termin: {detail}",
                                "is_placeholder": True,
                                "sort_order": entry_value  # Für korrekte Sortierung
                            })
            except Exception as e:
                logger.warning(f"Error adding placeholders: {e}")
        
        # Sortiere: Beendete Spiele nach Datum aufsteigend, dann Platzhalter nach Round-Order
        all_matches.sort(key=lambda x: (
            not x.get("finished", False),  # Beendete zuerst (False < True)
            x.get("sort_order", 999) if x.get("is_placeholder") else 0,  # Platzhalter nach Round
            x["date"]  # Dann nach Datum
        ))
        
        # Filtere: NUR zukünftige Spiele (keine beendeten)
        future_matches = [m for m in all_matches if not m.get("finished", False)]
        
        logger.info(f"DFB-Pokal: {len(future_matches)} zukünftige Spiele (von {len(all_matches)} gesamt)")
        return future_matches
        
    except Exception as e:
        logger.error(f"Error fetching DFB-Pokal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dfb-pokal")
async def get_dfb_pokal():
    """Gibt die nächsten DFB-Pokal-Spiele zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "DFB-Pokal",
        "matches": _fetch_dfb_pokal_cached(cache_key)
    }

# ============================================================================
# DEUTSCHLAND NATIONALMANNSCHAFT (WM-Quali)
# ============================================================================

@lru_cache(maxsize=1)
def _fetch_germany_cached(cache_key: str) -> List[Dict]:
    """Cached Deutschland Nationalmannschaft Spiele (WM-Quali) von OpenLigaDB"""
    try:
        now = datetime.now(BERLIN_TZ)
        
        # OpenLigaDB Deutsche Nationalmannschaft 25/26
        url = f"{OPENLIGA_BASE}/getmatchdata/DFBNAT2526/2025"
        logger.info(f"Fetching Germany from OpenLigaDB: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        matches_data = r.json()
        
        all_matches = []
        
        for match in matches_data:
            try:
                match_dt = to_berlin(match.get("matchDateTime", ""))
                
                # Teams
                team1 = match.get("team1", {}).get("teamName", "")
                team2 = match.get("team2", {}).get("teamName", "")
                
                # Score
                results = match.get("matchResults", [])
                score = ""
                if results:
                    final_result = results[-1]  # Letztes Ergebnis (Endstand)
                    score = f"{final_result.get('pointsTeam1', '')}:{final_result.get('pointsTeam2', '')}"
                
                # Status
                finished = match.get("matchIsFinished", False)
                
                # Runde
                round_name = match.get("group", {}).get("groupName", "WM-Qualifikation")
                
                match_obj = {
                    "date": match_dt.isoformat(),
                    "date_readable": match_dt.strftime("%d.%m.%Y"),
                    "time": match_dt.strftime("%H:%M"),
                    "weekday": weekday_german(match_dt),
                    "team_home": team1,
                    "team_away": team2,
                    "location": match.get("location", {}).get("locationCity", ""),
                    "round": round_name,
                    "score": score,
                    "finished": finished,
                    "status": "Beendet" if finished else "Anstehend",
                    "competition": "germany"
                }
                
                all_matches.append(match_obj)
                
            except Exception as e:
                logger.warning(f"Error parsing Germany match: {e}")
                continue
        
        # Sortiere nach Datum
        all_matches.sort(key=lambda x: x["date"])
        
        logger.info(f"Deutschland Nationalmannschaft: {len(all_matches)} Spiele (OpenLigaDB)")
        return all_matches
        
    except Exception as e:
        logger.error(f"Error fetching Germany matches: {e}")
        return []  # Leere Liste statt Exception

@app.get("/api/germany")
async def get_germany():
    """Gibt Deutschland Nationalmannschaft Spiele zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "Deutschland",
        "matches": _fetch_germany_cached(cache_key)
    }

# ============================================================================
# TABELLEN ENDPOINTS
# ============================================================================

@lru_cache(maxsize=1)
def _fetch_bundesliga_table_cached(cache_key: str) -> List[Dict]:
    """Cached Bundesliga Tabelle"""
    try:
        now = datetime.now(BERLIN_TZ)
        season = current_season_year(now)
        
        url = f"{OPENLIGA_BASE}/getbltable/bl1/{season}"
        logger.info(f"Fetching Bundesliga Table: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        table = r.json()
        
        # Formatiere Tabelle mit Kurznamen und Logos
        standings = []
        for entry in table:
            team_name = entry.get("shortName") or entry.get("teamName", "")
            team_logo = entry.get("teamIconUrl", "")
            standings.append({
                "position": entry.get("teamInfoId", 0),
                "team": team_name,
                "logo": team_logo,
                "matches": entry.get("matches", 0),
                "won": entry.get("won", 0),
                "draw": entry.get("draw", 0),
                "lost": entry.get("lost", 0),
                "goals": f"{entry.get('goals', 0)}:{entry.get('opponentGoals', 0)}",
                "goal_diff": entry.get("goalDiff", 0),
                "points": entry.get("points", 0)
            })
        
        return standings
        
    except Exception as e:
        logger.error(f"Error fetching Bundesliga table: {e}")
        return []

@app.get("/api/bundesliga/table")
async def get_bundesliga_table():
    """Gibt Bundesliga Tabelle zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "1. Bundesliga",
        "standings": _fetch_bundesliga_table_cached(cache_key)
    }

@lru_cache(maxsize=1)
def _fetch_champions_league_table_cached(cache_key: str) -> List[Dict]:
    """Cached Champions League Tabelle/Standings"""
    try:
        # Nutze site.api.espn.com statt site.web.api.espn.com
        url = "https://site.api.espn.com/apis/v2/sports/soccer/uefa.champions/standings?season=2025"
        logger.info(f"Fetching Champions League Standings: {url}")
        
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        
        # Neue Liga-Phase Format
        standings = []
        children = data.get("children", [])
        
        if children:
            standings_data = children[0].get("standings", {})
            entries = standings_data.get("entries", [])
            
            logger.info(f"Champions League Entries gefunden: {len(entries)}")
            
            for entry in entries[:18]:  # Top 18 für Übersicht
                team = entry.get("team", {})
                stats = entry.get("stats", [])
                
                # Extrahiere Stats
                stat_dict = {}
                for s in stats:
                    stat_dict[s.get("name")] = s.get("displayValue", s.get("value", ""))
                
                # Nutze displayName (voller Name) statt Kurzform + Logo
                team_name = team.get("displayName", "")
                team_logo = ""
                logos = team.get("logos", [])
                if logos:
                    team_logo = logos[0].get("href", "")
                
                standings.append({
                    "position": stat_dict.get("rank", ""),
                    "team": team_name,
                    "logo": team_logo,
                    "matches": stat_dict.get("gamesPlayed", "0"),
                    "wins": stat_dict.get("wins", "0"),
                    "draws": stat_dict.get("ties", "0"),
                    "losses": stat_dict.get("losses", "0"),
                    "goal_diff": stat_dict.get("pointDifferential", "0"),
                    "points": stat_dict.get("points", "0")
                })
        
        logger.info(f"Champions League Tabelle: {len(standings)} Teams")
        return standings
        
    except Exception as e:
        logger.error(f"Error fetching Champions League table: {e}")
        return []

@app.get("/api/champions-league/table")
async def get_champions_league_table():
    """Gibt Champions League Tabelle zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "Champions League",
        "standings": _fetch_champions_league_table_cached(cache_key)
    }

@lru_cache(maxsize=1)
def _fetch_dfb_pokal_teams_cached(cache_key: str) -> List[str]:
    """Cached DFB-Pokal verbleibende Teams"""
    try:
        # Nutze die bereits geladenen Matches
        matches = _fetch_dfb_pokal_cached(cache_key)
        
        # Finde alle Teams die noch im Wettbewerb sind (zukünftige Spiele)
        teams = set()
        for match in matches:
            if not match.get("finished", True) and not match.get("is_placeholder", False):
                teams.add(match.get("team_home", ""))
                teams.add(match.get("team_away", ""))
        
        # Falls keine zukünftigen Spiele: Nimm Sieger der letzten Runde
        if not teams:
            # Finde letzte gespielte Runde
            finished_matches = [m for m in matches if m.get("finished", False)]
            if finished_matches:
                # Sortiere nach Runden-Nummer (letzte Runde = höchste Nummer)
                round_order = {"1. Runde": 1, "2. Runde": 2, "Achtelfinale": 3, "Viertelfinale": 4, "Halbfinale": 5, "Finale": 6}
                last_round = max(finished_matches, key=lambda x: round_order.get(x.get("round", ""), 0))
                last_round_name = last_round.get("round", "")
                
                # Alle Teams aus dieser Runde die gewonnen haben
                for match in finished_matches:
                    if match.get("round") == last_round_name:
                        score = match.get("score", "")
                        if score and ":" in score:
                            s1, s2 = score.split(":")
                            try:
                                if int(s1) > int(s2):
                                    teams.add(match.get("team_home", ""))
                                elif int(s2) > int(s1):
                                    teams.add(match.get("team_away", ""))
                            except:
                                pass
        
        return sorted(list(teams))
        
    except Exception as e:
        logger.error(f"Error fetching DFB-Pokal teams: {e}")
        return []

@app.get("/api/dfb-pokal/teams")
async def get_dfb_pokal_teams():
    """Gibt verbleibende DFB-Pokal Teams zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    return {
        "competition": "DFB-Pokal",
        "teams": _fetch_dfb_pokal_teams_cached(cache_key),
        "round": "Achtelfinale"
    }

# ============================================================================
# COMBINED ENDPOINT (für Frontend)
# ============================================================================

@app.get("/api/all")
async def get_all():
    """Gibt alle Wettbewerbe kombiniert zurück"""
    cache_key = datetime.now(BERLIN_TZ).strftime("%Y%m%d%H")
    
    return {
        "generated_at": datetime.now(BERLIN_TZ).isoformat(),
        "bundesliga": _fetch_bundesliga_cached(cache_key),
        "champions_league": _fetch_champions_league_cached(cache_key),
        "dfb_pokal": _fetch_dfb_pokal_cached(cache_key),
        "germany": _fetch_germany_cached(cache_key),
        "tables": {
            "bundesliga": _fetch_bundesliga_table_cached(cache_key),
            "champions_league": _fetch_champions_league_table_cached(cache_key),
            "dfb_pokal_teams": _fetch_dfb_pokal_teams_cached(cache_key)
        }
    }

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health():
    """Health Check Endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.now(BERLIN_TZ).isoformat()
    }

# ============================================================================
# STATIC FILES (Frontend)
# ============================================================================

# Mount static files (web/) am Ende, damit API-Routes Priorität haben
import os
web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
try:
    if os.path.exists(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
        logger.info(f"Mounted static files from: {web_dir}")
    else:
        logger.warning(f"Static files directory not found: {web_dir}")
except RuntimeError as e:
    logger.warning(f"Error mounting static files: {e}")

# ============================================================================
# MAIN (für lokales Testing)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
