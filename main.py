import asyncio
import json
import sqlite3
import requests
import random
import time
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# ========================================
# CONFIGURACIÓN COMPARTIDA
# ========================================
API_URL = "https://api-cs.casino.org/svc-evolution-game-events/api/speedbaccarata/latest"
USER_AGENTS = [ ... ]  # (misma lista larga)
RESULT_EMOJIS = {"Player": "🟢", "Banker": "🔴", "Tie": "🟡"}

DATA_DIR = Path("/app/baccarat_data")
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "baccarat.db"

# ========================================
# FUNCIONES DE BASE DE DATOS
# ========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zapato_id TEXT NOT NULL,
            game_id TEXT NOT NULL UNIQUE,
            patron_id INTEGER,
            patron_score INTEGER NOT NULL,
            player_score INTEGER NOT NULL,
            banker_score INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            started_at TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Probabilidades (
            patron_tabla INTEGER PRIMARY KEY,
            patron_player INTEGER DEFAULT 0,
            patron_banker INTEGER DEFAULT 0,
            patron_tie INTEGER DEFAULT 0,
            patron_total INTEGER DEFAULT 0,
            prob_player REAL DEFAULT 0.0,
            prob_banker REAL DEFAULT 0.0,
            prob_tie REAL DEFAULT 0.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Datos_Necesarios (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_ultimo_patron_score():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM Datos_Necesarios WHERE clave='ultimo_patron_score'")
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else None

def set_ultimo_patron_score(valor):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO Datos_Necesarios (clave, valor) VALUES (?, ?)", 
                   ('ultimo_patron_score', str(valor)))
    conn.commit()
    conn.close()

def game_id_existe(game_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Historial WHERE game_id = ?", (game_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def insert_historial(zapato_id, game_id, patron_id, patron_score, player_score, banker_score, outcome, started_at):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO Historial 
        (zapato_id, game_id, patron_id, patron_score, player_score, banker_score, outcome, started_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (zapato_id, game_id, patron_id, patron_score, player_score, banker_score, outcome, started_at))
    conn.commit()
    conn.close()

def actualizar_probabilidades(patron_id, outcome):
    if patron_id is None: return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO Probabilidades (patron_tabla) VALUES (?)", (patron_id,))
    if outcome == "Player":
        cursor.execute("UPDATE Probabilidades SET patron_player = patron_player + 1, patron_total = patron_total + 1 WHERE patron_tabla = ?", (patron_id,))
    elif outcome == "Banker":
        cursor.execute("UPDATE Probabilidades SET patron_banker = patron_banker + 1, patron_total = patron_total + 1 WHERE patron_tabla = ?", (patron_id,))
    elif outcome == "Tie":
        cursor.execute("UPDATE Probabilidades SET patron_tie = patron_tie + 1, patron_total = patron_total + 1 WHERE patron_tabla = ?", (patron_id,))
    cursor.execute('''
        UPDATE Probabilidades 
        SET prob_player = CAST(patron_player AS REAL) / patron_total,
            prob_banker = CAST(patron_banker AS REAL) / patron_total,
            prob_tie = CAST(patron_tie AS REAL) / patron_total
        WHERE patron_tabla = ?
    ''', (patron_id,))
    conn.commit()
    conn.close()

def get_latest_games(limit=100):
    if not DB_FILE.exists():
        return []
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT zapato_id, game_id, patron_id, patron_score, player_score, banker_score, outcome, started_at
        FROM Historial
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    games = []
    for row in rows:
        games.append({
            "zapato_id": row[0],
            "game_id": row[1],
            "patron_id": row[2],
            "patron_score": row[3],
            "player_score": row[4],
            "banker_score": row[5],
            "outcome": row[6],
            "started_at": row[7]
        })
    return list(reversed(games))

def get_probabilidades():
    if not DB_FILE.exists():
        return []
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Probabilidades ORDER BY patron_tabla")
    rows = cursor.fetchall()
    conn.close()
    probs = []
    for row in rows:
        probs.append({
            "patron_tabla": row[0],
            "patron_player": row[1],
            "patron_banker": row[2],
            "patron_tie": row[3],
            "patron_total": row[4],
            "prob_player": row[5],
            "prob_banker": row[6],
            "prob_tie": row[7]
        })
    return probs

# ========================================
# FUNCIONES DEL RECOLECTOR
# ========================================
def get_random_user_agent():
    return random.choice(USER_AGENTS)

def format_datetime(iso_time):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_time

def fetch_game_data():
    headers = {'User-Agent': get_random_user_agent(), 'Accept': 'application/json'}
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return None

def process_game_data(data):
    if not data: return None
    game_data = data.get("data", data)
    result = game_data.get("result", {})
    return {
        'game_id': data.get("id", ""),
        'shoe_id': game_data.get("id", ""),
        'started_at': format_datetime(game_data.get("startedAt", "")),
        'outcome': result.get("outcome", "Unknown"),
        'player_score': result.get("player", {}).get("score", 0),
        'banker_score': result.get("banker", {}).get("score", 0)
    }

# ========================================
# TAREA DE FONDO: RECOLECTOR
# ========================================
async def collector_task():
    init_db()
    ultimo_patron = get_ultimo_patron_score()
    print("🚀 Recolector iniciado")
    while True:
        try:
            raw_data = fetch_game_data()
            if raw_data:
                game_info = process_game_data(raw_data)
                if game_info and game_info['game_id']:
                    if not game_id_existe(game_info['game_id']):
                        patron_score_actual = game_info['player_score'] + game_info['banker_score']
                        insert_historial(
                            zapato_id=game_info['shoe_id'],
                            game_id=game_info['game_id'],
                            patron_id=ultimo_patron,
                            patron_score=patron_score_actual,
                            player_score=game_info['player_score'],
                            banker_score=game_info['banker_score'],
                            outcome=game_info['outcome'],
                            started_at=game_info['started_at']
                        )
                        if ultimo_patron is not None:
                            actualizar_probabilidades(ultimo_patron, game_info['outcome'])
                        ultimo_patron = patron_score_actual
                        set_ultimo_patron_score(ultimo_patron)
                        print(f"✅ Nueva jugada: {game_info['outcome']} {game_info['game_id']}")
        except Exception as e:
            print(f"Error en recolector: {e}")
        await asyncio.sleep(1)

# ========================================
# LIFESPAN PARA INICIAR TAREA DE FONDO
# ========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(collector_task())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

# ========================================
# ENDPOINTS REST
# ========================================
@app.get("/", response_class=HTMLResponse)
async def get_html():
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>index.html no encontrado</h1>", status_code=404)

@app.get("/api/history")
async def api_history(limit: int = 100):
    return get_latest_games(limit)

@app.get("/api/probabilities")
async def api_probabilities():
    return get_probabilidades()

@app.get("/api/latest")
async def api_latest():
    games = get_latest_games(1)
    return games[0] if games else {}
