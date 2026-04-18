"""
scheduler_iol.py — Scheduler automático de cotizaciones IOL
Herramientas Financieras AR

Cowork Task Scheduler: lunes a viernes, 10:30 hs.
El script se encarga solo del loop de 15 minutos hasta las 17:00 hs.
Excluye sábados, domingos y feriados nacionales argentinos.

Uso: python scheduler_iol.py
"""

import os, json, subprocess, sys, time, logging
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
IOL_BASE        = "https://api.invertironline.com"
IOL_USER        = os.getenv("IOL_USER")
IOL_PASS        = os.getenv("IOL_PASS")
REPO_PATH       = Path(os.getenv("REPO_PATH", "."))
DATA_DIR        = REPO_PATH / "data"
STATIC_JSON     = DATA_DIR / "lecaps_static.json"
OUTPUT_JSON     = DATA_DIR / "lecaps_boncaps.json"
LOG_FILE        = REPO_PATH / "logs" / "scheduler.log"

HORA_INICIO     = (10, 30)   # 10:30 hs.
HORA_FIN        = (17,  0)   # 17:00 hs.
INTERVALO_MIN   = 15         # minutos entre cada fetch

TICKERS_VALIDOS = {
    # LECAPs — vienen del panel general /Cotizaciones/Letras/argentina/Todos
    "S30A6","S15Y6","S29Y6","S17L6","S31L6","S14G6",
    "S31G6","S30S6","S30O6","S30N6",
    # BONCAPs — NO están en ningún panel, se consultan individualmente
    "T30J6","T15E7","T30A7","T31Y7","T30J7",
}

# BONCAPs: consulta individual obligatoria
BONCAPS = ["T30J6","T15E7","T30A7","T31Y7","T30J7"]

# ── Feriados nacionales Argentina ─────────────────────────────────────────────
# Actualizar cada año. Incluye feriados inamovibles + movibles + puentes.
# Fuente: Decreto del PEN / Ministerio del Interior
FERIADOS = {
    # 2026
    date(2026,  1,  1),   # Año Nuevo
    date(2026,  2, 16),   # Carnaval
    date(2026,  2, 17),   # Carnaval
    date(2026,  3, 23),   # Puente turístico
    date(2026,  3, 24),   # Día de la Memoria
    date(2026,  4,  2),   # Veteranos de Malvinas
    date(2026,  4,  3),   # Viernes Santo
    date(2026,  5,  1),   # Día del Trabajador
    date(2026,  5, 25),   # Revolución de Mayo
    date(2026,  6, 19),   # Puente turístico (Belgrano)
    date(2026,  6, 20),   # Paso a la Inmortalidad — Gral. Belgrano
    date(2026,  7,  9),   # Independencia
    date(2026,  8, 17),   # Paso a la Inmortalidad — Gral. San Martín
    date(2026, 10, 12),   # Diversidad Cultural
    date(2026, 11, 20),   # Soberanía Nacional
    date(2026, 12,  7),   # Puente turístico (Inmaculada)
    date(2026, 12,  8),   # Inmaculada Concepción
    date(2026, 12, 25),   # Navidad
    # 2027 — completar cuando se publique el decreto
    date(2027,  1,  1),   # Año Nuevo
}

# ── Logging ───────────────────────────────────────────────────────────────────
def setup_logging():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ]
    )

log = logging.getLogger(__name__)

# ── Validaciones de calendario ────────────────────────────────────────────────
def es_dia_habil(d: date) -> bool:
    if d.weekday() >= 5:          # sábado=5, domingo=6
        return False
    if d in FERIADOS:
        return False
    return True

def dentro_de_horario(ahora: datetime) -> bool:
    t = (ahora.hour, ahora.minute)
    return HORA_INICIO <= t < HORA_FIN

def proxima_ejecucion(desde: datetime) -> datetime:
    """Calcula el próximo tick cada INTERVALO_MIN minutos, alineado al :00 o :30."""
    siguiente = desde + timedelta(minutes=INTERVALO_MIN)
    return siguiente

# ── Auth IOL ──────────────────────────────────────────────────────────────────
_token = None
_refresh_token = None
_token_expira = None

def login():
    global _token, _refresh_token, _token_expira
    r = requests.post(f"{IOL_BASE}/token", data={
        "username":   IOL_USER,
        "password":   IOL_PASS,
        "grant_type": "password"
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    _token         = d["access_token"]
    _refresh_token = d["refresh_token"]
    _token_expira  = datetime.now() + timedelta(seconds=d.get("expires_in", 840) - 60)
    log.info("Login IOL OK")

def get_token():
    """Devuelve token válido, hace refresh si está por expirar."""
    global _token, _refresh_token, _token_expira
    if _token is None or datetime.now() >= _token_expira:
        if _refresh_token:
            try:
                r = requests.post(f"{IOL_BASE}/token", data={
                    "refresh_token": _refresh_token,
                    "grant_type":    "refresh_token"
                }, timeout=15)
                r.raise_for_status()
                d = r.json()
                _token         = d["access_token"]
                _refresh_token = d["refresh_token"]
                _token_expira  = datetime.now() + timedelta(seconds=d.get("expires_in", 840) - 60)
                log.info("Token IOL refrescado")
            except Exception as e:
                log.warning(f"Refresh falló ({e}), re-login...")
                login()
        else:
            login()
    return _token

def headers():
    return {"Authorization": f"Bearer {get_token()}"}

# ── Fetch cotizaciones ────────────────────────────────────────────────────────
def fetch_panel(instrumento):
    """1 request — trae todos los LECAPs del panel Letras."""
    url = f"{IOL_BASE}/api/v2/Cotizaciones/{instrumento}/argentina/Todos"
    r = requests.get(url, headers=headers(), timeout=20)
    r.raise_for_status()
    return r.json().get("titulos", [])

def fetch_cotizacion_individual(ticker):
    """
    1 request por ticker — único método que funciona para BONCAPs.
    Confirmado: no aparecen en ningún panel general de IOL.
    Ventaja: trae montoOperado real (ej: T30J6 → $24.326M).
    """
    url = f"{IOL_BASE}/api/v2/bCBA/Titulos/{ticker}/Cotizacion"
    r = requests.get(url, headers=headers(), timeout=20)
    r.raise_for_status()
    d = r.json()
    # Normalizar al mismo formato que panel general
    return {
        "simbolo":             ticker,
        "ultimoPrecio":        d.get("ultimoPrecio", 0),
        "variacion":           d.get("variacion", 0),
        "montoOperado":        d.get("montoOperado", 0),
        "cantidadOperaciones": d.get("cantidadOperaciones", 0),
    }

def extraer_cotizacion(item):
    """
    Mapea un item del panel general de IOL al formato interno.
    Confirmado en sesión 18/04/2026:
      - ultimoPrecio: precio cada 100 VN (ej: 126.815)
      - variacion: % directo (ej: 0.16 = 0,16%)
      - montoOperado: viene 0 en panel general (mercado cerrado o limitación API)
      - cantidadOperaciones: único campo con dato útil de actividad
    """
    simbolo = (item.get("simbolo") or "").strip().upper()
    precio  = float(item.get("ultimoPrecio") or 0)
    # variacion viene como % directo: 0.25 = 0,25% → convertir a decimal
    var_pct = float(item.get("variacion") or 0) / 100
    # volumen: montoOperado viene 0 en panel, usamos cantidadOperaciones como proxy
    vol     = float(item.get("montoOperado") or 0)
    cant_op = int(item.get("cantidadOperaciones") or 0)
    return {
        "ticker":  simbolo,
        "precio":  precio,
        "var_pct": round(var_pct, 6),
        "vol":     vol,
        "cant_op": cant_op,
    }

# ── Datos estáticos ───────────────────────────────────────────────────────────
def cargar_estaticos():
    if not STATIC_JSON.exists():
        log.warning(f"{STATIC_JSON} no encontrado")
        return {}
    with open(STATIC_JSON, encoding="utf-8") as f:
        return json.load(f)

# ── Cálculo de tasas ──────────────────────────────────────────────────────────
def calcular_tasas(precio, val_vto, vencimiento_str):
    hoy = date.today()
    try:
        vto  = date.fromisoformat(vencimiento_str)
        dias = max(1, (vto - hoy).days)
    except Exception:
        return None
    ratio = val_vto / precio
    return {
        "dias": dias,
        "tna":  round((pow(ratio, 1/dias) - 1) * 365,   6),
        "tea":  round( pow(ratio, 365/dias) - 1,          6),
        "tem":  round( pow(ratio, 30/dias)  - 1,          6),
        "tir":  round( pow(ratio, 365/dias) - 1,          6),
    }

def construir_output(cotizaciones_raw, estaticos):
    """
    Precio IOL viene cada 100 VN (ej: 126.815).
    valVto en lecaps_static.json debe estar en la misma escala (ej: 127.486).
    """
    instrumentos = []
    for item in cotizaciones_raw:
        cot    = extraer_cotizacion(item)
        ticker = cot["ticker"]
        if ticker not in TICKERS_VALIDOS:
            continue
        est = estaticos.get(ticker, {})
        val_vto, vencimiento = est.get("valVto"), est.get("vencimiento")
        if not val_vto or not vencimiento or cot["precio"] <= 0:
            continue
        tasas = calcular_tasas(cot["precio"], val_vto, vencimiento)
        if not tasas:
            continue
        instrumentos.append({
            "ticker":      ticker,
            "tipo":        est.get("tipo", "LECAP"),
            "vencimiento": vencimiento,
            "vto":         f"{vencimiento[8:10]}/{vencimiento[5:7]}/{vencimiento[:4]}",
            "precio":      round(cot["precio"], 4),
            "var_pct":     cot["var_pct"],
            "vol":         cot["vol"],
            "cant_op":     cot["cant_op"],
            "valVto":      val_vto,
            **tasas
        })
    return {
        "fecha_actualizacion": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "fuente": "IOL_API",
        "instrumentos": sorted(instrumentos, key=lambda x: x["vencimiento"])
    }

# ── Git push ──────────────────────────────────────────────────────────────────
def git_push():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        subprocess.run(["git","-C",str(REPO_PATH),"add",str(OUTPUT_JSON)],
                       check=True, capture_output=True)
        result = subprocess.run(
            ["git","-C",str(REPO_PATH),"commit","-m",f"data: IOL {ts}"],
            capture_output=True)
        if result.returncode == 0:
            subprocess.run(["git","-C",str(REPO_PATH),"push"],
                           check=True, capture_output=True)
            log.info("git push OK")
        else:
            log.info("Sin cambios para commitear")
    except subprocess.CalledProcessError as e:
        log.warning(f"git error: {e.stderr.decode().strip()}")

# ── Un ciclo de fetch ─────────────────────────────────────────────────────────
def ejecutar_fetch():
    """
    Estrategia definitiva (confirmada 18/04/2026):
      - LECAPs: 1 request via panel /Cotizaciones/Letras/argentina/Todos
      - BONCAPs: 5 requests individuales /bCBA/Titulos/{ticker}/Cotizacion
        (no aparecen en ningún panel general de IOL)
    Total: 6 requests/ciclo → ~3.564 requests/mes
    """
    log.info("── Fetch iniciado ──")
    try:
        # 1 request — LECAPs
        raw_letras = fetch_panel("Letras")
        log.info(f"Panel Letras: {len(raw_letras)} items")

        # 5 requests — BONCAPs individuales
        raw_boncaps = []
        for ticker in BONCAPS:
            try:
                item = fetch_cotizacion_individual(ticker)
                raw_boncaps.append(item)
                log.info(f"  {ticker}: ${item['ultimoPrecio']} | "
                         f"var {item['variacion']}% | "
                         f"monto ${item['montoOperado']:,.0f}")
            except Exception as e:
                log.warning(f"  {ticker}: error ({e})")

        log.info(f"BONCAPs individuales: {len(raw_boncaps)}/5")

        # Merge, calcular, guardar
        estaticos = cargar_estaticos()
        output    = construir_output(raw_letras + raw_boncaps, estaticos)
        n         = len(output["instrumentos"])
        log.info(f"Instrumentos mapeados: {n}/{len(TICKERS_VALIDOS)}")

        if n == 0:
            log.error("Ningún instrumento mapeado — verificar campos IOL")
            if raw_letras:
                log.info(f"[DEBUG] Primer item Letras: "
                         f"{json.dumps(raw_letras[0], ensure_ascii=False)[:300]}")
            return False

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        log.info(f"JSON guardado → {OUTPUT_JSON.name}")
        git_push()
        return True

    except requests.HTTPError as e:
        log.error(f"HTTP error IOL: {e}")
    except Exception as e:
        log.exception(f"Error inesperado: {e}")
    return False

# ── Loop principal ────────────────────────────────────────────────────────────
def main():
    setup_logging()
    hoy = date.today()

    log.info("=" * 60)
    log.info(f"Scheduler IOL iniciado — {hoy.strftime('%A %d/%m/%Y')}")

    # Validar día hábil
    if not es_dia_habil(hoy):
        razon = "fin de semana" if hoy.weekday() >= 5 else "feriado nacional"
        log.info(f"Hoy es {razon}. No se ejecuta. Saliendo.")
        sys.exit(0)

    # Validar que la hora de inicio sea alcanzable
    ahora = datetime.now()
    inicio_dt = ahora.replace(hour=HORA_INICIO[0], minute=HORA_INICIO[1],
                               second=0, microsecond=0)
    fin_dt    = ahora.replace(hour=HORA_FIN[0],    minute=HORA_FIN[1],
                               second=0, microsecond=0)

    if ahora >= fin_dt:
        log.info("Fuera de horario (después de las 17:00). Saliendo.")
        sys.exit(0)

    # Si se ejecutó antes de las 10:30, esperar
    if ahora < inicio_dt:
        espera = (inicio_dt - ahora).seconds
        log.info(f"Esperando hasta las 10:30 ({espera//60} min)...")
        time.sleep(espera)

    # Login inicial
    if not IOL_USER or not IOL_PASS:
        log.error("IOL_USER o IOL_PASS no configurados en .env")
        sys.exit(1)
    login()

    # ── Loop de 15 minutos ──────────────────────────────────────────────────
    ciclo = 0
    while dentro_de_horario(datetime.now()):
        ciclo += 1
        log.info(f"Ciclo #{ciclo} | {datetime.now().strftime('%H:%M:%S')}")
        ejecutar_fetch()

        # Calcular próximo tick
        prox = proxima_ejecucion(datetime.now())
        fin  = datetime.now().replace(hour=HORA_FIN[0], minute=HORA_FIN[1],
                                       second=0, microsecond=0)
        if prox >= fin:
            log.info("Próximo tick fuera del horario. Finalizando.")
            break

        espera_seg = (prox - datetime.now()).total_seconds()
        if espera_seg > 0:
            log.info(f"Próximo fetch: {prox.strftime('%H:%M')} "
                     f"(en {int(espera_seg//60)}m {int(espera_seg%60)}s)")
            time.sleep(espera_seg)

    log.info(f"Scheduler finalizado. Total ciclos: {ciclo}")
    log.info("=" * 60)

if __name__ == "__main__":
    main()
