# ========================================
# 🎰 SPEED BACCARAT DATA COLLECTOR
# Versión solo SQLite con patrones y probabilidades
# ========================================

import requests
import json
import time
import random
import sqlite3
from datetime import datetime
from colorama import init, Fore, Style
from pathlib import Path

# Inicializar colorama
init(autoreset=True)

# ========================================
# CONFIGURACIÓN
# ========================================

API_URL = "https://api-cs.casino.org/svc-evolution-game-events/api/speedbaccarata/latest"
POLLING_INTERVAL = 1

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.43 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0"
]

RESULT_EMOJIS = {
    "Player": "🟢",
    "Banker": "🔴",
    "Tie": "🟡"
}

# Directorio de datos
DATA_DIR = Path("baccarat_data")
DATA_DIR.mkdir(exist_ok=True)

DB_FILE = DATA_DIR / "baccarat.db"

# ========================================
# FUNCIONES DE UTILIDAD
# ========================================

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def format_datetime(iso_time):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_time

def format_time(iso_time):
    try:
        dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except:
        return iso_time

# ========================================
# BASE DE DATOS SQLITE
# ========================================

def init_db():
    """Crea las tablas necesarias si no existen"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabla Historial
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
    
    # Tabla Probabilidades
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
    
    # Tabla Datos_Necesarios (para variables de control)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Datos_Necesarios (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_ultimo_patron_score():
    """Obtiene el último patron_score guardado (el de la jugada anterior)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM Datos_Necesarios WHERE clave='ultimo_patron_score'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return int(row[0])
    return None

def set_ultimo_patron_score(valor):
    """Guarda el patron_score actual como último para la próxima jugada"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO Datos_Necesarios (clave, valor) VALUES (?, ?)", 
                   ('ultimo_patron_score', str(valor)))
    conn.commit()
    conn.close()

def game_id_existe(game_id):
    """Verifica si un game_id ya está registrado en Historial"""
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
    """Actualiza las estadísticas para el patrón dado (el de la jugada anterior)"""
    if patron_id is None:
        return  # No hay patrón anterior
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Asegurar que existe la fila para este patrón
    cursor.execute("INSERT OR IGNORE INTO Probabilidades (patron_tabla) VALUES (?)", (patron_id,))
    
    # Incrementar contadores según el resultado
    if outcome == "Player":
        cursor.execute('''
            UPDATE Probabilidades 
            SET patron_player = patron_player + 1,
                patron_total = patron_total + 1
            WHERE patron_tabla = ?
        ''', (patron_id,))
    elif outcome == "Banker":
        cursor.execute('''
            UPDATE Probabilidades 
            SET patron_banker = patron_banker + 1,
                patron_total = patron_total + 1
            WHERE patron_tabla = ?
        ''', (patron_id,))
    elif outcome == "Tie":
        cursor.execute('''
            UPDATE Probabilidades 
            SET patron_tie = patron_tie + 1,
                patron_total = patron_total + 1
            WHERE patron_tabla = ?
        ''', (patron_id,))
    else:
        conn.close()
        return
    
    # Recalcular probabilidades
    cursor.execute('''
        UPDATE Probabilidades 
        SET prob_player = CAST(patron_player AS REAL) / patron_total,
            prob_banker = CAST(patron_banker AS REAL) / patron_total,
            prob_tie = CAST(patron_tie AS REAL) / patron_total
        WHERE patron_tabla = ?
    ''', (patron_id,))
    
    conn.commit()
    conn.close()

# ========================================
# FUNCIONES DE API
# ========================================

def fetch_game_data():
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }
    try:
        response = requests.get(API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"{Fore.RED}❌ Error de conexión: {e}")
        return None

def process_game_data(data):
    if not data:
        return None
    
    game_data = data.get("data", data)
    result = game_data.get("result", {})
    
    return {
        'game_id': data.get("id", ""),               # ID de la respuesta general
        'shoe_id': game_data.get("id", ""),           # ID de la ronda (zapato)
        'started_at': format_datetime(game_data.get("startedAt", "")),
        'started_at_short': format_time(game_data.get("startedAt", "")),
        'outcome': result.get("outcome", "Unknown"),
        'emoji': RESULT_EMOJIS.get(result.get("outcome", "Unknown"), "❓"),
        'player_score': result.get("player", {}).get("score", 0),
        'banker_score': result.get("banker", {}).get("score", 0)
    }

# ========================================
# SISTEMA PRINCIPAL
# ========================================

def run_collector():
    # Inicializar base de datos
    init_db()
    
    # Obtener último patron_score (si existe)
    ultimo_patron = get_ultimo_patron_score()
    
    # Contadores
    new_records = 0
    duplicate_records = 0
    errors = 0
    start_time = datetime.now()
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}🚀 INICIANDO RECOPILACIÓN DE DATOS (solo SQLite)")
    print(f"⏱️ Intervalo: {POLLING_INTERVAL} segundo(s)")
    print(f"📁 Base de datos: {DB_FILE}{Style.RESET_ALL}")
    print(f"\n{Fore.MAGENTA}{'─' * 60}")
    
    try:
        while True:
            raw_data = fetch_game_data()
            
            if raw_data:
                game_info = process_game_data(raw_data)
                
                if game_info:
                    game_id = game_info['game_id']
                    
                    # Verificar si ya existe en la base de datos
                    if not game_id_existe(game_id):
                        # Calcular patron_score actual
                        patron_score_actual = game_info['player_score'] + game_info['banker_score']
                        
                        # Insertar en Historial
                        insert_historial(
                            zapato_id=game_info['shoe_id'],
                            game_id=game_id,
                            patron_id=ultimo_patron,
                            patron_score=patron_score_actual,
                            player_score=game_info['player_score'],
                            banker_score=game_info['banker_score'],
                            outcome=game_info['outcome'],
                            started_at=game_info['started_at']
                        )
                        
                        # Actualizar probabilidades para el patrón anterior
                        if ultimo_patron is not None:
                            actualizar_probabilidades(ultimo_patron, game_info['outcome'])
                        
                        # Guardar el nuevo patron_score como último
                        ultimo_patron = patron_score_actual
                        set_ultimo_patron_score(ultimo_patron)
                        
                        new_records += 1
                        
                        # Mostrar en consola
                        print(f"{Fore.GREEN}✅ [{new_records}] {game_info['started_at_short']} | "
                              f"{game_info['emoji']} {game_info['outcome']} | "
                              f"Jugada: {game_id[:8]}... | Zapato: {game_info['shoe_id'][:8]}...{Style.RESET_ALL}")
                    else:
                        duplicate_records += 1
            else:
                errors += 1
            
            time.sleep(POLLING_INTERVAL)
            
    except KeyboardInterrupt:
        end_time = datetime.now()
        duration = end_time - start_time
        
        print(f"\n\n{Fore.YELLOW}{Style.BRIGHT}🛑 RECOPILACIÓN DETENIDA")
        print(f"{Fore.CYAN}{'─' * 60}")
        print(f"⏱️ Tiempo de ejecución: {duration}")
        print(f"✅ Nuevos registros: {new_records}")
        print(f"🔄 Duplicados ignorados: {duplicate_records}")
        print(f"❌ Errores: {errors}")
        
        # Contar total de registros en Historial
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Historial")
        total = cursor.fetchone()[0]
        conn.close()
        print(f"📊 Total de registros en Historial: {total}")
        print(f"{'─' * 60}{Style.RESET_ALL}")

# ========================================
# PUNTO DE ENTRADA
# ========================================

if __name__ == "__main__":
    print("\n")
    print(f"{Fore.MAGENTA}{Style.BRIGHT}")
    print("╔══════════════════════════════════════════════════╗")
    print("║     🎰 SPEED BACCARAT DATA COLLECTOR 🎰         ║")
    print("║         (Versión solo SQLite)                   ║")
    print("╚══════════════════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}\n")
    
    run_collector()
