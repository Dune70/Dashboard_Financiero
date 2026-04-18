"""
fetch_iol.py — Actualización automática de cotizaciones IOL
Herramientas Financieras AR

Ejecución: python fetch_iol.py
Cowork Task Scheduler: lunes a viernes, 10:30 hs.

Requiere:
  - .env con IOL_USER, IOL_PASS, REPO_PATH
  - lecaps_static.json en REPO_PATH/data/
  - git configurado en REPO_PATH
"""

import os, json, subprocess, sys
from datetime import datetime, date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
IOL_BASE   = "https://api.invertironline.com"
IOL_USER   = os.getenv("IOL_USER")
IOL_PASS   = os.getenv("IOL_PASS")
REPO_PATH  = Path(os.getenv("REPO_PATH", "."))   # ej: C:/Users/Christian/repos/herramientas-ar
DATA_DIR   = REPO_PATH / "data"
STATIC_JSON = DATA_DIR / "lecaps_static.json"
OUTPUT_JSON = DATA_DIR / "lecaps_boncaps.json"

# Tickers válidos (LECAPs + BONCAPs actuales)
TICKERS_VALIDOS = {
    "S17A6","S30A6","S15Y6","S29Y6","S31L6","S31G6",
    "S30S6","S30O6","S30N6",                          # LECAPs
    "T30J6","T15E7","T30A7","T31Y7","T30J7",          # BONCAPs
}

# ── Auth IOL ──────────────────────────────────────────────────────────────────
def login():
    r = requests.post(f"{IOL_BASE}/token", data={
        "username":   IOL_USER,
        "password":   IOL_PASS,
        "grant_type": "password"
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    return d["access_token"], d["refresh_token"]

def refresh(refresh_token):
    r = requests.post(f"{IOL_BASE}/token", data={
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token"
    }, timeout=15)
    r.raise_for_status()
    d = r.json()
    return d["access_token"], d["refresh_token"]

def headers(token):
    return {"Authorization": f"Bearer {token}"}

# ── Fetch cotizaciones ────────────────────────────────────────────────────────
def fetch_panel(token, instrumento):
    """
    GET /api/v2/Cotizaciones/{Instrumento}/argentina/Todos
    Devuelve lista de títulos del panel completo.
    """
    url = f"{IOL_BASE}/api/v2/Cotizaciones/{instrumento}/argentina/Todos"
    r = requests.get(url, headers=headers(token), timeout=20)
    r.raise_for_status()
    return r.json()

def extraer_cotizacion(item):
    """
    Mapea un item del response de IOL al formato interno.
    Los nombres de campo pueden variar — ajustar según respuesta real.
    Campos observados en IOL: simbolo, ultimoPrecio, variacion, 
                              cantidadOperaciones, montoOperado, volumen
    """
    simbolo = (item.get("simbolo") or item.get("ticker") or "").strip().upper()

    # Precio: IOL puede devolver ultimoPrecio o ultimo
    precio = (
        item.get("ultimoPrecio") or
        item.get("ultimo") or
        item.get("precio") or 0
    )

    # Variación: porcentaje o decimal
    var_raw = (
        item.get("variacion") or
        item.get("variacionPorcentual") or 0
    )
    # IOL a veces devuelve 0.42 (%) y a veces 0.0042 (decimal) — normalizar
    var_pct = float(var_raw)
    if abs(var_pct) > 1:          # viene en %, convertir a decimal
        var_pct = var_pct / 100

    # Volumen: preferir montoOperado en pesos
    vol = (
        item.get("montoOperado") or
        item.get("volumen") or
        item.get("cantidadOperaciones") or 0
    )

    return {
        "ticker":  simbolo,
        "precio":  float(precio),
        "var_pct": round(var_pct, 6),
        "vol":     float(vol),
    }

# ── Cargar datos estáticos ────────────────────────────────────────────────────
def cargar_estaticos():
    """Lee lecaps_static.json con valVto y vencimiento por ticker."""
    if not STATIC_JSON.exists():
        print(f"[WARN] {STATIC_JSON} no encontrado — calculando sin valVto")
        return {}
    with open(STATIC_JSON, encoding="utf-8") as f:
        data = json.load(f)
    # formato: { "S17A6": {"valVto": 1.1013, "vencimiento": "2026-04-17", "tipo": "LECAP"}, ... }
    return data

# ── Merge y cálculo de tasas ──────────────────────────────────────────────────
def calcular_tasas(precio, val_vto, vencimiento_str):
    """TNA, TEA, TEM a partir de precio de mercado + valVto."""
    hoy = date.today()
    try:
        vto = date.fromisoformat(vencimiento_str)
        dias = max(1, (vto - hoy).days)
    except Exception:
        return None

    ratio = val_vto / precio
    tna   = (pow(ratio, 1 / dias) - 1) * 365
    tea   = pow(ratio, 365 / dias) - 1
    tem   = pow(ratio, 30  / dias) - 1
    tir   = tea  # sin comisión

    return {
        "dias": dias,
        "tna":  round(tna, 6),
        "tea":  round(tea, 6),
        "tem":  round(tem, 6),
        "tir":  round(tir, 6),
    }

def construir_output(cotizaciones_raw, estaticos):
    instrumentos = []
    hoy_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    for item in cotizaciones_raw:
        cot = extraer_cotizacion(item)
        ticker = cot["ticker"]

        if ticker not in TICKERS_VALIDOS:
            continue

        est = estaticos.get(ticker, {})
        val_vto = est.get("valVto")
        vencimiento = est.get("vencimiento")
        tipo = est.get("tipo", "LECAP")

        if not val_vto or not vencimiento:
            print(f"[WARN] {ticker}: sin valVto o vencimiento en static — omitido")
            continue

        tasas = calcular_tasas(cot["precio"], val_vto, vencimiento)
        if not tasas:
            continue

        instrumentos.append({
            "ticker":      ticker,
            "tipo":        tipo,
            "vencimiento": vencimiento,
            "precio":      round(cot["precio"], 4),
            "var_pct":     cot["var_pct"],
            "vol":         cot["vol"],
            "valVto":      val_vto,
            **tasas
        })

    return {
        "fecha_actualizacion": hoy_str,
        "fuente": "IOL_API",
        "instrumentos": sorted(instrumentos, key=lambda x: x["vencimiento"])
    }

# ── Git push ──────────────────────────────────────────────────────────────────
def git_push(mensaje):
    try:
        subprocess.run(["git", "-C", str(REPO_PATH), "add", str(OUTPUT_JSON)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(REPO_PATH), "commit", "-m", mensaje],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(REPO_PATH), "push"],
                       check=True, capture_output=True)
        print("[OK] git push completado")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] git: {e.stderr.decode()}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now():%H:%M:%S}] Iniciando fetch IOL...")

    if not IOL_USER or not IOL_PASS:
        print("[ERROR] IOL_USER o IOL_PASS no configurados en .env")
        sys.exit(1)

    # 1. Login
    token, rt = login()
    print("[OK] Login IOL exitoso")

    # 2. Fetch paneles — Letras cubre LECAPs, Bonos puede incluir BONCAPs
    raw_letras = fetch_panel(token, "Letras")
    print(f"[OK] Letras: {len(raw_letras)} items")

    # Refresh token antes del segundo fetch (por las dudas)
    token, rt = refresh(rt)
    raw_bonos = fetch_panel(token, "Bonos")
    print(f"[OK] Bonos: {len(raw_bonos)} items")

    # 3. Unir ambos paneles (puede haber duplicados, el set filtra)
    todos = raw_letras + raw_bonos

    # 4. Datos estáticos
    estaticos = cargar_estaticos()
    print(f"[OK] Estáticos cargados: {len(estaticos)} tickers")

    # 5. Construir output
    output = construir_output(todos, estaticos)
    encontrados = len(output["instrumentos"])
    print(f"[OK] Instrumentos mapeados: {encontrados}/{len(TICKERS_VALIDOS)}")

    if encontrados == 0:
        print("[ERROR] Ningún instrumento mapeado — revisar campos del response IOL")
        # Mostrar muestra del response para debugging
        if todos:
            print("[DEBUG] Muestra del primer item:")
            print(json.dumps(todos[0], indent=2, ensure_ascii=False)[:800])
        sys.exit(1)

    # 6. Guardar JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON guardado: {OUTPUT_JSON}")

    # 7. Git push
    msg = f"data: actualización automática {datetime.now():%Y-%m-%d %H:%M}"
    git_push(msg)

    print(f"[{datetime.now():%H:%M:%S}] Proceso completado.")

if __name__ == "__main__":
    main()
