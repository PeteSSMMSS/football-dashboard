// ============================================================================
// KONFIGURATION
// ============================================================================

const API_BASE = window.location.origin;
const UPDATE_INTERVAL = 60 * 60 * 1000; // 60 Minuten
const TIMELINE_DAYS = 30; // Anzahl Tage im Kalender (ca. 1 Monat)

// ============================================================================
// STATE
// ============================================================================

let allMatches = {
    bundesliga: [],
    champions_league: [],
    dfb_pokal: [],
    germany: []
};

let allTables = {
    bundesliga: [],
    champions_league: [],
    dfb_pokal_teams: []
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Formatiert Datum für Anzeige
 */
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const days = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
    const months = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'];
    
    return {
        dayName: days[date.getDay()],
        day: date.getDate(),
        month: months[date.getMonth()],
        monthNum: date.getMonth() + 1,
        year: date.getFullYear(),
        fullDate: date.toISOString().split('T')[0]
    };
}

/**
 * Prüft ob Datum heute ist
 */
function isToday(dateStr) {
    const today = new Date();
    const date = new Date(dateStr);
    return date.toDateString() === today.toDateString();
}

/**
 * Zählt Spiele pro Datum
 */
function countMatchesByDate() {
    const counts = {};
    
    Object.values(allMatches).flat().forEach(match => {
        const date = match.date.split('T')[0];
        counts[date] = (counts[date] || 0) + 1;
    });
    
    return counts;
}

// ============================================================================
// API CALLS
// ============================================================================

/**
 * Lädt alle Daten von der API
 */
async function fetchAllData() {
    try {
        console.log('Fetching data from API...');
        
        const response = await fetch(`${API_BASE}/api/all`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        allMatches = {
            bundesliga: data.bundesliga || [],
            champions_league: data.champions_league || [],
            dfb_pokal: data.dfb_pokal || [],
            germany: data.germany || []
        };
        
        allTables = data.tables || {
            bundesliga: [],
            champions_league: [],
            dfb_pokal_teams: []
        };
        
        console.log('Data loaded:', {
            bundesliga: allMatches.bundesliga.length,
            champions_league: allMatches.champions_league.length,
            dfb_pokal: allMatches.dfb_pokal.length,
            germany: allMatches.germany.length
        });
        
        updateUI();
        updateLastUpdate();
        
    } catch (error) {
        console.error('Error fetching data:', error);
        showError('Fehler beim Laden der Daten. Bitte später erneut versuchen.');
    }
}

// ============================================================================
// TIMELINE RENDERING
// ============================================================================

/**
 * Erstellt die Timeline
 */
function renderTimeline() {
    const timeline = document.getElementById('timeline');
    const matchCounts = countMatchesByDate();
    
    timeline.innerHTML = '';
    
    const today = new Date();
    
    for (let i = 0; i < TIMELINE_DAYS; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() + i);
        
        const dateStr = date.toISOString().split('T')[0];
        const formatted = formatDate(dateStr);
        const matchCount = matchCounts[dateStr] || 0;
        
        const dayDiv = document.createElement('div');
        dayDiv.className = `timeline-day ${isToday(dateStr) ? 'today' : ''}`;
        dayDiv.dataset.date = dateStr;
        
        dayDiv.innerHTML = `
            <div class="day-name">${formatted.dayName}</div>
            <div class="day-date">${formatted.day}</div>
            <div class="day-month">${formatted.month}</div>
            ${matchCount > 0 ? `<div class="day-matches">${matchCount} Spiel${matchCount > 1 ? 'e' : ''}</div>` : ''}
        `;
        
        // Click Handler: Scroll zu Spielen an diesem Datum
        if (matchCount > 0) {
            dayDiv.style.cursor = 'pointer';
            dayDiv.addEventListener('click', () => {
                scrollToDate(dateStr);
            });
        }
        
        timeline.appendChild(dayDiv);
    }
    
    // Scroll zu heute
    setTimeout(() => {
        const todayElement = timeline.querySelector('.today');
        if (todayElement) {
            todayElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
    }, 100);
}

/**
 * Scrollt zu Spielen eines bestimmten Datums
 */
function scrollToDate(dateStr) {
    const firstMatch = document.querySelector(`[data-match-date="${dateStr}"]`);
    if (firstMatch) {
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // Highlight-Effekt
        firstMatch.style.transform = 'scale(1.02)';
        setTimeout(() => {
            firstMatch.style.transform = '';
        }, 500);
    }
}

// ============================================================================
// MATCHES RENDERING
// ============================================================================

/**
 * Erstellt eine Match-Card
 */
function createMatchCard(match, competition) {
    const card = document.createElement('div');
    card.className = `match-card ${competition}`;
    card.dataset.matchDate = match.date.split('T')[0];
    
    const dateInfo = formatDate(match.date);
    
    // Extra Info je nach Wettbewerb
    let extraInfo = '';
    if (match.matchday) {
        extraInfo = `Spieltag ${match.matchday}`;
    } else if (match.round) {
        extraInfo = match.round;
    } else if (match.status && !match.is_placeholder) {
        extraInfo = match.status;
    }
    
    // Score anzeigen wenn beendet
    let scoreDisplay = '';
    if (match.finished && match.score) {
        scoreDisplay = `<div class="match-score">${match.score}</div>`;
    }
    
    // TBD Styling für Platzhalter
    const teamClass = match.is_placeholder ? 'team-tbd' : '';
    const dateDisplay = match.is_placeholder ? 
        `<div class="match-round-header">${match.round}</div>` :
        `<div class="match-date">${dateInfo.dayName}, ${dateInfo.day}. ${dateInfo.month} ${dateInfo.year}</div>`;
    
    const timeDisplay = match.is_placeholder ? 
        `<div class="match-date-tbd">${match.status}</div>` : 
        `<div class="match-time">${match.time} Uhr</div>`;
    
    card.innerHTML = `
        <div class="match-header">
            ${dateDisplay}
            ${timeDisplay}
        </div>
        ${scoreDisplay}
        <div class="match-teams">
            <div class="team">
                <span class="team-name team-home ${teamClass}">${match.team_home}</span>
            </div>
            <div class="team">
                <span class="team-name ${teamClass}">${match.team_away}</span>
            </div>
        </div>
        ${match.location || extraInfo ? `
            <div class="match-info">
                <span class="match-location">📍 ${match.location || '—'}</span>
                ${extraInfo ? `<span class="match-extra">${extraInfo}</span>` : ''}
            </div>
        ` : ''}
    `;
    
    return card;
}

/**
 * Rendert Spiele einer Competition
 */
function renderMatches(matches, containerId, competition) {
    const container = document.getElementById(containerId);
    const countElement = document.getElementById(`${containerId.split('-')[0]}-count`);
    
    container.innerHTML = '';
    
    if (matches.length === 0) {
        container.innerHTML = '<div class="no-matches">Keine anstehenden Spiele</div>';
        countElement.textContent = '0';
        return;
    }
    
    countElement.textContent = matches.length;
    
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    let scrollTarget = null;
    
    matches.forEach((match, index) => {
        const card = createMatchCard(match, competition);
        
        // Markiere erste zukünftige Match für Auto-Scroll
        const matchDate = new Date(match.date);
        matchDate.setHours(0, 0, 0, 0);
        
        if (!scrollTarget && matchDate >= today && !match.finished) {
            card.classList.add('scroll-target');
            scrollTarget = card;
        }
        
        // Markiere vergangene Spiele visuell
        if (match.finished) {
            card.classList.add('finished');
        }
        
        // Markiere Platzhalter (TBD)
        if (match.is_placeholder) {
            card.classList.add('placeholder');
        }
        
        container.appendChild(card);
    });
    
    // KEIN Auto-Scroll mehr - Seite bleibt oben
    // (Nur Timeline scrollt zum heutigen Datum)
}

/**
 * Aktualisiert die gesamte UI
 */
function updateUI() {
    renderTimeline();
    renderTables();
    renderMatches(allMatches.bundesliga, 'bundesliga-matches', 'bundesliga');
    renderMatches(allMatches.champions_league, 'cl-matches', 'champions-league');
    renderMatches(allMatches.dfb_pokal, 'pokal-matches', 'dfb-pokal');
    renderMatches(allMatches.germany, 'germany-matches', 'germany');
}

// ============================================================================
// TABLES RENDERING
// ============================================================================

/**
 * Rendert alle Tabellen
 */
function renderTables() {
    renderBundesligaTable(allTables.bundesliga);
    renderChampionsLeagueTable(allTables.champions_league);
    renderDFBPokalTeams(allTables.dfb_pokal_teams);
}

/**
 * Rendert Bundesliga Tabelle (kompakt mit Logos)
 */
function renderBundesligaTable(standings) {
    const tbody = document.querySelector('#bundesliga-table tbody');
    
    if (!standings || standings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">Keine Daten verfügbar</td></tr>';
        return;
    }
    
    tbody.innerHTML = '';
    
    standings.forEach((team, index) => {
        const row = document.createElement('tr');
        
        // Highlight für Top 4 (Champions League), 5-6 (Europa League), 16-18 (Abstieg)
        if (index < 4) row.classList.add('cl-zone');
        else if (index < 6) row.classList.add('el-zone');
        else if (index >= 15) row.classList.add('relegation-zone');
        
        const logoHtml = team.logo ? `<img src="${team.logo}" alt="${team.team}" class="team-logo">` : '';
        
        row.innerHTML = `
            <td class="position">${index + 1}</td>
            <td class="team-name">
                ${logoHtml}
                <span>${team.team}</span>
            </td>
            <td class="centered">${team.matches}</td>
            <td class="points centered"><strong>${team.points}</strong></td>
        `;
        
        tbody.appendChild(row);
    });
}

/**
 * Rendert Champions League Tabelle (kompakt mit Logos)
 */
function renderChampionsLeagueTable(standings) {
    const tbody = document.querySelector('#cl-table tbody');
    
    if (!standings || standings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="no-data">Keine Daten verfügbar</td></tr>';
        return;
    }
    
    tbody.innerHTML = '';
    
    standings.forEach((team, index) => {
        const row = document.createElement('tr');
        
        // Highlight für Top 8 (direktes Achtelfinale)
        if (index < 8) row.classList.add('cl-zone');
        
        const logoHtml = team.logo ? `<img src="${team.logo}" alt="${team.team}" class="team-logo">` : '';
        
        row.innerHTML = `
            <td class="position">${team.position}</td>
            <td class="team-name">
                ${logoHtml}
                <span>${team.team}</span>
            </td>
            <td class="centered">${team.matches}</td>
            <td class="points centered"><strong>${team.points}</strong></td>
        `;
        
        tbody.appendChild(row);
    });
}

/**
 * Rendert DFB-Pokal verbleibende Teams
 */
function renderDFBPokalTeams(teams) {
    const container = document.getElementById('pokal-teams');
    
    if (!teams || teams.length === 0) {
        container.innerHTML = '<div class="no-data">Noch keine Teams qualifiziert</div>';
        return;
    }
    
    container.innerHTML = '';
    
    // Zeige Teams als Grid
    teams.forEach(team => {
        const teamCard = document.createElement('div');
        teamCard.className = 'team-badge';
        teamCard.textContent = team;
        container.appendChild(teamCard);
    });
}

/**
 * Aktualisiert "Zuletzt aktualisiert" Text
 */
function updateLastUpdate() {
    const lastUpdate = document.getElementById('last-update');
    const now = new Date();
    const timeStr = now.toLocaleTimeString('de-DE', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit'
    });
    const dateStr = now.toLocaleDateString('de-DE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
    
    lastUpdate.textContent = `Zuletzt aktualisiert: ${dateStr} um ${timeStr} Uhr`;
}

/**
 * Zeigt Fehlermeldung
 */
function showError(message) {
    const containers = [
        'bundesliga-matches',
        'cl-matches',
        'pokal-matches'
    ];
    
    containers.forEach(id => {
        const container = document.getElementById(id);
        container.innerHTML = `<div class="no-matches">❌ ${message}</div>`;
    });
}

// ============================================================================
// INIT & AUTO-UPDATE
// ============================================================================

/**
 * Initialisierung beim Laden der Seite
 */
async function init() {
    console.log('🚀 Football Dashboard initialized');
    
    // Initiales Laden
    await fetchAllData();
    
    // Auto-Update alle 60 Minuten
    setInterval(fetchAllData, UPDATE_INTERVAL);
    
    console.log(`✅ Auto-update enabled (every ${UPDATE_INTERVAL / 60000} minutes)`);
}

// Starte App wenn DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
