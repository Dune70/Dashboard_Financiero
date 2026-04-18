# 🪟 Configuración en Windows (Task Scheduler)

Windows no tiene `crontab`. Usa **Task Scheduler** para tareas automáticas.

---

## PASO 1: Reemplaza el archivo

Descarga `actualizar-bonos-windows.js` (limpio) y reemplaza el corrupto:

```
C:\IA\Dashboard_Financiero\actualizar-bonos.js  ← REEMPLAZA por el nuevo
```

---

## PASO 2: Prueba que funciona

Abre **PowerShell** (o CMD):

```powershell
cd C:\IA\Dashboard_Financiero
node actualizar-bonos.js
```

Debería ver:
```
📊 Actualizando bonos... [04/04/2026 14:30:15]
✓ Autenticado en IOL
⟳ Descargando bonos desde IOL...
✓ 35 bonos descargados
✓ Guardado en: data\bonos_live.json
✅ Completado
```

Si funciona, continúa. Si no, **avisame el error**.

---

## PASO 3: Abre Task Scheduler

Presiona **Windows + R** y escribe:

```
taskschd.msc
```

Abre la ventana de **Task Scheduler**.

---

## PASO 4: Crear tarea programada

En el panel derecho, haz clic en **Create Basic Task...**

---

## PASO 5: Nombra la tarea

**Name:** `Actualizar Bonos IOL`

**Description:** `Descarga bonos desde IOL cada 15 minutos`

Haz clic **Next**

---

## PASO 6: Configurar trigger (cuándo ejecutar)

Selecciona: **On a schedule**

Haz clic **Next**

---

## PASO 7: Configurar horario

**Recurrence:** `Daily`

Haz clic **Next**

---

## PASO 8: Configurar acción

Selecciona: **Start a program**

Haz clic **Next**

---

## PASO 9: Especificar programa

**Program/script:**
```
C:\Program Files\nodejs\node.exe
```

*(O donde esté instalado Node en tu máquina)*

**Para confirmar dónde está Node:**
```powershell
where node
# Output: C:\Program Files\nodejs\node.exe (o similar)
```

**Add arguments (optional):**
```
actualizar-bonos.js
```

**Start in (optional):**
```
C:\IA\Dashboard_Financiero
```

Haz clic **Next**

---

## PASO 10: Revisar y crear

Verifica que esté correcto:
```
✓ Actualizar Bonos IOL
✓ On a schedule (Daily)
✓ Start C:\Program Files\nodejs\node.exe
```

Haz clic **Finish**

---

## PASO 11: Editar la tarea para repetir cada 15 min

**Problema:** Task Scheduler no repite "cada 15 min" en la UI. Necesitamos editarlo:

1. En **Task Scheduler**, busca `Actualizar Bonos IOL`
2. **Click derecho** → **Properties**
3. Abre la pestaña **Triggers**
4. **Edita el trigger (doble click)**
5. Marca: **Repeat task every: 15 minutes**
6. **Duration:** `Until 5:00 PM` (17:00)
7. OK, OK

---

## PASO 12: Añadir restricción de horario (opcional)

Si quieres que **SOLO** se ejecute entre 10:30 AM y 5:00 PM:

1. En **Properties** → **General**
2. Marca: **Run only when user is logged on**
3. Marca: **Run with highest privileges** (para permisos)

---

## PASO 13: Verifica que se ejecute

**Opción A: Ejecuta la tarea manualmente**
1. En Task Scheduler, click derecho en `Actualizar Bonos IOL`
2. **Run**
3. Debería ver que `data\bonos_live.json` se actualiza

**Opción B: Espera 15 minutos**
- Mañana a las 10:30, debería ejecutarse automáticamente

---

## PASO 14: Ver logs

Los logs se guardan en **Event Viewer**:

1. Presiona **Windows + R**
2. Escribe: `eventvwr.msc`
3. Busca eventos de Task Scheduler

O simplemente verifica que `data\bonos_live.json` se actualiza cada 15 min.

---

## ⚠️ Troubleshooting

### Task no ejecuta
**Solución:**
- Verifica que la ruta a Node es correcta: `where node`
- Verifica que `.env` existe en `C:\IA\Dashboard_Financiero`
- Marca "Run with highest privileges" en Properties

### "file not found: actualizar-bonos.js"
**Solución:**
- El "Start in" debe ser: `C:\IA\Dashboard_Financiero`
- O usa ruta completa en "Add arguments": `C:\IA\Dashboard_Financiero\actualizar-bonos.js`

### "Cannot find module 'dotenv'"
**Solución:**
```powershell
cd C:\IA\Dashboard_Financiero
npm install dotenv
```

---

## ✅ Checklist final

- [ ] Descargaste `actualizar-bonos-windows.js` (limpio)
- [ ] `node actualizar-bonos.js` funciona manualmente
- [ ] `data\bonos_live.json` fue creado
- [ ] Abriste Task Scheduler (`taskschd.msc`)
- [ ] Creaste tarea "Actualizar Bonos IOL"
- [ ] Configuraste Node.exe correctamente
- [ ] Configuraste "Repeat every 15 minutes"
- [ ] Ejecutaste manualmente para probar
- [ ] `data\bonos_live.json` se actualiza cada 15 min

---

## Resultado

A partir de mañana a las 10:30 AM:

✅ Task Scheduler ejecuta el script automáticamente cada 15 min  
✅ `data\bonos_live.json` se actualiza  
✅ Tu navegador carga datos frescos  
✅ Cero intervención manual

---

¿Dudas? Avisame en qué paso te trabas.
