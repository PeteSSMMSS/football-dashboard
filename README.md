# ⚽ Fußball Dashboard

Minimalistisches One-Page Dashboard für Fußball-Spieltermine aus Bundesliga, Champions League und DFB-Pokal.

## 🎯 Features

- **📅 Timeline**: Horizontale Monatsansicht mit Spielterminen
- **🇩🇪 1. Bundesliga**: Nächste Spiele aus der OpenLigaDB API
- **🏆 Champions League**: Aktuelle Spiele von ESPN API
- **🏅 DFB-Pokal**: Pokalspiele aus OpenLigaDB
- **🎨 Modern & Minimal**: Dark Theme, schnelles Laden, responsive
- **🔄 Auto-Update**: Daten werden stündlich aktualisiert
- **🐳 Docker Ready**: Einfaches Deployment

## 🚀 Lokales Testing

### Voraussetzungen
- Python 3.11+
- Docker (optional)

### Option 1: Direkt mit Python

```bash
# In das Projektverzeichnis wechseln
cd football-dashboard

# Dependencies installieren
pip install -r api/requirements.txt

# Server starten
python api/main.py
```

Server läuft auf: **http://localhost:8080**

### Option 2: Mit Docker Compose

```bash
# In das Projektverzeichnis wechseln
cd football-dashboard

# Container bauen und starten
docker-compose up -d

# Logs ansehen
docker-compose logs -f

# Container stoppen
docker-compose down
```

Server läuft auf: **http://localhost:8080**

## 📁 Projektstruktur

```
football-dashboard/
├── api/
│   ├── main.py              # FastAPI Backend
│   └── requirements.txt     # Python Dependencies
├── web/
│   ├── index.html          # Frontend HTML
│   ├── style.css           # CSS Styling
│   └── app.js              # JavaScript Logic
├── Dockerfile              # Docker Image Definition
├── docker-compose.yml      # Docker Compose Config
└── README.md              # Diese Datei
```

## 🔌 API Endpoints

- `GET /health` - Health Check
- `GET /api/bundesliga` - Bundesliga Spiele
- `GET /api/champions-league` - Champions League Spiele
- `GET /api/dfb-pokal` - DFB-Pokal Spiele
- `GET /api/all` - Alle Wettbewerbe kombiniert
- `GET /` - Frontend (index.html)

## 🏠 Synology NAS Deployment

### 1. Docker Image auf NAS übertragen

**Option A: Docker Registry**
```bash
# Lokal: Image bauen und pushen
docker build -t your-registry/football-dashboard:latest .
docker push your-registry/football-dashboard:latest

# Auf NAS: Image pullen
docker pull your-registry/football-dashboard:latest
```

**Option B: Image exportieren/importieren**
```bash
# Lokal: Image als .tar exportieren
docker save -o football-dashboard.tar football-dashboard:latest

# Datei auf NAS kopieren (via SCP, SMB, etc.)
scp football-dashboard.tar user@nas-ip:/volume1/docker/

# Auf NAS: Image importieren
docker load -i /volume1/docker/football-dashboard.tar
```

### 2. Container auf NAS starten

**Via SSH:**
```bash
ssh user@nas-ip

# docker-compose.yml auf NAS kopieren
cd /volume1/docker/football-dashboard

# Container starten
docker-compose up -d
```

**Via Synology Container Manager (GUI):**
1. Container Manager öffnen
2. "Image" → "Hinzufügen" → "Von Datei hinzufügen"
3. football-dashboard.tar auswählen
4. "Container" → "Erstellen"
5. Port 8080 auf gewünschten Port mappen
6. Umgebungsvariable `TZ=Europe/Berlin` setzen
7. Container starten

### 3. Zugriff
Dashboard ist erreichbar unter: `http://nas-ip:8080`

### 4. Reverse Proxy (Optional)

Für HTTPS und Custom Domain via Synology Reverse Proxy:
1. Systemsteuerung → Anmeldungsportal → Erweitert → Reverse Proxy
2. Erstellen:
   - Protokoll: HTTPS
   - Hostname: football.your-domain.com
   - Port: 443
   - Ziel: localhost, Port 8080
3. SSL-Zertifikat zuweisen

## 🔧 Konfiguration

### Umgebungsvariablen

```env
TZ=Europe/Berlin              # Zeitzone
```

### Port ändern

In `docker-compose.yml`:
```yaml
ports:
  - "8080:8080"  # Host:Container
```

In `api/main.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8080)
```

## 🛠️ Entwicklung

### API Debugging

Debug-Script zum Testen der APIs:
```bash
python debug_apis.py
```

Erstellt `debug_output.json` mit allen Rohdaten.

### Cache löschen

Der API-Cache wird stündlich automatisch invalidiert. Manuelles Löschen:
```python
# In Python Console
from api.main import _fetch_bundesliga_cached
_fetch_bundesliga_cached.cache_clear()
```

### Hot Reload (Entwicklung)

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8080
```

## 📊 Datenquellen

- **Bundesliga & DFB-Pokal**: [OpenLigaDB](https://www.openligadb.de/)
- **Champions League**: [ESPN API](https://site.web.api.espn.com/)

## 🎨 Design

- **Theme**: Dark Mode
- **Colors**: 
  - Bundesliga: Rot (`#d20515`)
  - Champions League: Blau (`#0e1f5b`)
  - DFB-Pokal: Grün (`#006837`)
  - Heute: Grün (`#00ff88`)
- **Font**: System Fonts (San Francisco, Segoe UI, Roboto)

## 📝 Lizenz

MIT License - Frei verwendbar für private und kommerzielle Projekte.

## 🐛 Troubleshooting

### Server startet nicht
```bash
# Port bereits belegt?
netstat -ano | findstr :8080  # Windows
lsof -i :8080                 # Linux/Mac

# Dependencies fehlen?
pip install -r api/requirements.txt
```

### Keine Daten werden geladen
```bash
# API erreichbar?
curl http://localhost:8080/health

# Logs prüfen
docker-compose logs -f
```

### Container startet nicht auf NAS
- Docker-Berechtigungen prüfen
- Port 8080 verfügbar?
- Firewall-Regeln prüfen

## 📧 Support

Bei Fragen oder Problemen: GitHub Issues erstellen oder Logs teilen.

---

**Erstellt mit ❤️ für Fußball-Fans**
