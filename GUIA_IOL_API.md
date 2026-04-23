# Guía IOL API — Herramientas Financieras AR
**Fecha:** 18/04/2026 | **Autor:** Christian

---

## 1. Autenticación

**Login inicial** (token dura ~15 minutos):
```powershell
$body = "username=TU_EMAIL&password=TU_CONTRASEÑA&grant_type=password"
$response = Invoke-RestMethod -Method POST -Uri "https://api.invertironline.com/token" -Body $body -ContentType "application/x-www-form-urlencoded"
$token = $response.access_token
$headers = @{Authorization = "Bearer $token"}
Write-Host "Token OK"
```

**Refresh automático** (lo maneja `scheduler_iol.py` internamente).

---

## 2. Arquitectura de Fetch por Instrumento

### LECAPs — Panel general (1 request)
```powershell
$letras = Invoke-RestMethod -Method GET -Uri "https://api.invertironline.com/api/v2/Cotizaciones/Letras/argentina/Todos" -Headers $headers
$letras.titulos | Where-Object { $_.simbolo -in @("S30A6","S15Y6",...) } | Select-Object simbolo, ultimoPrecio, variacion
```
- **Campo precio:** `ultimoPrecio` — escala 100 VN (ej: 126,815)
- **Campo variación:** `variacion` — % directo (ej: 0,25 = 0,25%)
- **Volumen:** viene en 0 en panel general (normal fuera de horario)

### BONCAPs — Cotización individual (1 request por ticker)
```powershell
$t = Invoke-RestMethod -Method GET -Uri "https://api.invertironline.com/api/v2/bCBA/Titulos/T30J6/Cotizacion" -Headers $headers
```
- **Motivo:** NO aparecen en ningún panel general de IOL
- **Tickers:** T30J6, T15E7, T30A7, T31Y7, T30J7

### Bonos CER — Cotización individual (1 request por ticker)
```powershell
$t = Invoke-RestMethod -Method GET -Uri "https://api.invertironline.com/api/v2/bCBA/Titulos/TX26/Cotizacion" -Headers $headers
```
- **Motivo:** NO aparecen en ningún panel general de IOL
- **Tickers:** CUAP, DICP, DIP0, PAP0, PARP, TX26, TX28, TX31, TZX26, TZX27, TZX28, TZXA7, TZXD6, TZXD7, TZXM7, TZXM9, TZXO6, TZXS7, TZXS8, TZXY7

### Bonos Soberanos USD — Cotización individual (1 request por ticker)
```powershell
$t = Invoke-RestMethod -Method GET -Uri "https://api.invertironline.com/api/v2/bCBA/Titulos/AL30/Cotizacion" -Headers $headers
```
- **Tickers ARS:** TVPP, TVPY, AO27, AL29, GD29, AL30, GD30, AO28, AN29, AE38, GD38, AL35, GD35, AL41, GD41, GD46
- **Tickers USD (especie D):** AL29D, AL30D, AL35D, AL41D, GD29D, GD30D, GD35D, GD38D, GD41D, GD46D, AE38D, AO27D, AO28D, AN29D
- **MEP:** AL30 (ARS) / AL30D (USD) — actualizar cada 5 min

### ONs Corporativas — Cotización individual (1 request por ticker)
```powershell
$t = Invoke-RestMethod -Method GET -Uri "https://api.invertironline.com/api/v2/bCBA/Titulos/VSCVO/Cotizacion" -Headers $headers
```
- **Tickers:** VSCVO, IRCPO, PN43O, PLC4O, TSC4O, RC1CO, YM34O, VSCXO, PLC5O, RUCDO, RVS1O, TLCPO

---

## 3. Campos del Response /Cotizacion

| Campo | Descripción | Ejemplo |
|---|---|---|
| `ultimoPrecio` | Precio último operado (escala 100 VN) | 139,05 |
| `variacion` | Variación % del día (% directo) | 0,39 |
| `montoOperado` | Volumen en pesos operado | 24.326.710.784 |
| `cantidadOperaciones` | Número de operaciones | 1070 |
| `descripcionTitulo` | Nombre del instrumento | "Boncap T30J6 Vto 30/06/2026" |
| `cierreAnterior` | Precio de cierre anterior | 139,05 |
| `apertura` | Precio de apertura | 138,55 |
| `maximo` | Precio máximo del día | 139,50 |
| `minimo` | Precio mínimo del día | 138,55 |

---

## 4. Cálculo de Tasas (base 365)

Con precio IOL (escala 100 VN) y valVto del JSON estático (misma escala):

```python
ratio = valVto / precio          # ej: 127.486 / 126.815
dias  = (fecha_vto - hoy).days   # calculado dinámicamente

TNA = (ratio^(1/dias) - 1) × 365
TEA = ratio^(365/dias) - 1
TEM = ratio^(30/dias) - 1
TIR = TEA  # sin comisión
```

---

## 5. Presupuesto de Requests/Mes

| Scheduler | Frecuencia | Requests/ciclo | Requests/mes |
|---|---|---|---|
| MEP (AL30 + AL30D) | cada 5 min | 2 | 2.376 |
| LECAPs + BONCAPs | cada 15 min | 6 | 3.564 |
| CER + Soberanos + ONs | cada 30 min | 46 | 13.524 |
| **Total** | | | **19.464/mes** |

**Límite IOL:** 25.000/mes gratuitos ✅ (margen: ~5.500 requests)

---

## 6. JSONs Estáticos del Proyecto

Ubicación: `C:\IA\Dashboard_Financiero\data\`

| Archivo | Contenido | Tickers |
|---|---|---|
| `lecaps_static.json` | valVto + vencimiento LECAPs/BONCAPs | 15 |
| `bonos_cer_static.json` | tasa cupón + vencimiento CER | 20 |
| `bonos_soberanos_static.json` | tasa cupón + vencimiento soberanos | 16 |
| `ons_static.json` | tasa cupón + vencimiento ONs | 12 |

**Regla:** Los JSONs estáticos se actualizan manualmente cuando hay nuevas emisiones o vencimientos.

---

## 7. Convenciones Confirmadas

- **Escala de precios:** 100 VN (ej: AL30 = 90.190, no 901,90)
- **Campo variación:** `variacion` (no `variacionPorcentual`) — viene como % directo
- **Formato fechas display:** DD/MM/YYYY (ej: 30/04/2026)
- **Formato fechas interno/JSON:** YYYY-MM-DD (ej: 2026-04-30)
- **Formato números:** separador de miles = punto, decimal = coma
- **Base de cálculo:** 365 días para todos los instrumentos en ARS

---

## 8. Scheduler Windows Task Scheduler

**Configuración actual:**
- Tarea: `IOL Dashboard`
- Script: `C:\IA\Dashboard_Financiero\scheduler_iol.py`
- Horario: lunes a viernes, 10:30 hs
- Loop interno: cada 15 min hasta las 17:00 hs
- Feriados: hardcodeados en el script (actualizar anualmente)

**Verificar tarea:**
```powershell
schtasks /query /tn "IOL Dashboard"
```

**Log del scheduler:**
```
C:\IA\Dashboard_Financiero\logs\scheduler.log
```
