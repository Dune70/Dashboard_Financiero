# 🤖 Script de Actualización Automática de Bonos

Script Node.js que trae bonos en vivo desde IOL API cada 15 minutos y guarda en `data/bonos_live.json`.

---

## 1. Instalación

### Requisitos
- **Node.js 16+** ([descargar](https://nodejs.org))
- Git configurado
- Repositorio GitHub clonado localmente

### Pasos

```bash
# 1. Ir a la carpeta del proyecto
cd /ruta/a/herramientas-financieras-ar

# 2. Instalar dependencias
npm install

# 3. Crear .env con tus credenciales
cp .env.example .env
# Editar .env con usuario/contraseña de IOL
```

### Contenido de `.env`
```
IOL_USER=tu_usuario@ejemplo.com
IOL_PASS=tu_contraseña_iol
GITHUB_TOKEN=ghp_xxxxxxxxxxxxx  # Opcional
REPO_PATH=.
```

---

## 2. Usar el Script

### Ejecución manual (prueba)
```bash
node actualizar-bonos.js
```

Debería ver:
```
📊 Actualizando bonos... [04/04/2026 14:30:15]
✓ Autenticado en IOL
⟳ Descargando bonos desde IOL...
✓ 35 bonos descargados
✓ Guardado en: data/bonos_live.json
✓ Pushed a GitHub
✅ Completado
```

---

## 3. Programar cada 15 minutos

### En Linux/Mac (cron)

```bash
# Abrir editor de crontab
crontab -e

# Agregar esta línea (ejecuta cada 15 min entre 10:30-17:00, lunes-viernes)
*/15 10-17 * * 1-5 cd /ruta/a/herramientas-financieras-ar && /usr/bin/node actualizar-bonos.js >> /tmp/bonos-update.log 2>&1
```

**Verificar que está activo:**
```bash
crontab -l
```

---

### En Windows (Task Scheduler)

1. Abrir **Task Scheduler** (Administrador)
2. **Create Basic Task**
3. **Name:** `Actualizar Bonos IOL`
4. **Trigger:** 
   - Repeat task every `15 minutes`
   - Start time: `10:30 AM`
   - End time: `5:00 PM`
5. **Action:**
   - Program: `C:\Program Files\nodejs\node.exe`
   - Arguments: `C:\ruta\actualizar-bonos.js`
   - Start in: `C:\ruta\herramientas-financieras-ar`
6. **Conditions:** Run only on weekdays (mon-fri)

---

## 4. Usar datos en HTML

En tu `bonos_renta_fija.html`, simplemente carga el JSON:

```javascript
async function cargarBonosLocal() {
  const res = await fetch('./data/bonos_live.json');
  const data = await res.json();
  
  console.log(`Última actualización: ${data.fecha_actualizacion}`);
  console.log(`${data.bonos.length} bonos cargados`);
  
  // rawBonos es la variable que usa el dashboard
  rawBonos = data.bonos;
  
  // Re-renderizar
  buildTickerBtns();
  initCarryHeaders();
  update();
}

// Cargar al iniciar
document.addEventListener('DOMContentLoaded', cargarBonosLocal);
```

---

## 5. Estructura de JSON generado

```json
{
  "fecha_actualizacion": "2026-04-04T14:30:15.123Z",
  "fuente": "IOL_API_LIVE",
  "horario_mercado": "10:30 - 17:00 ART",
  "bonos": [
    {
      "ticker": "AL30",
      "descripcion": "Bono Soberano Ley Argentina 2030",
      "tipo": "BONO",
      "precio": 85.50,
      "valVto": 100,
      "dias": 1234,
      "vto": "30/07/2030",
      "volumen": 50000000,
      "variacion": -0.15,
      "precioCompra": 85.45,
      "precioVenta": 85.55,
      "apertura": 86.00,
      "minimo": 85.20,
      "maximo": 86.50
    }
  ]
}
```

---

## 6. Seguridad

✅ **Credenciales locales solo:**
- `.env` nunca sube a GitHub (agregar a `.gitignore`)
- Token solo existe en tu máquina
- Cowork/Anthropic NO toca nada

✅ **GitHub Token (si usas auto-push):**
- Generar en https://github.com/settings/tokens
- Seleccionar permisos: `repo` (full control)
- Usar en `.env`

✅ **Logs:**
- Guardados en `/tmp/bonos-update.log` (Linux/Mac)
- Revisar regularmente para errores

---

## 7. Troubleshooting

### ❌ "IOL login fallido"
- Verificar usuario/contraseña en `.env`
- Confirmar que la cuenta tiene APIs habilitadas en IOL
- Revisar IP bloqueada (¿VPN?)

### ❌ "Cannot find module 'dotenv'"
```bash
npm install
```

### ❌ "Git push fallido"
- Verificar que `GITHUB_TOKEN` es válido
- Verificar permisos en GitHub
- O simplemente no usar auto-push (dejar GITHUB_TOKEN vacío)

### ❌ Cron no ejecuta
```bash
# Verificar logs
tail -f /tmp/bonos-update.log

# Verificar sintaxis
crontab -l
```

---

## 8. Script adicional: ejecutar manualmente

Si queres actualizar sin esperar cron:

```bash
npm run update-bonos
# O directamente:
node actualizar-bonos.js
```

---

## Próximos pasos

- [ ] Configurar `.env` con credenciales
- [ ] Ejecutar `node actualizar-bonos.js` para probar
- [ ] Configurar cron (Linux/Mac) o Task Scheduler (Windows)
- [ ] Editar `bonos_renta_fija.html` para cargar `data/bonos_live.json`
- [ ] Verificar que se actualiza cada 15 min

¿Dudas? Avisame.
