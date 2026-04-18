@echo off
REM Obtener d?a de la semana (1=lunes, 7=domingo)
for /f %%a in ('powershell [int][datetime]::Now.DayOfWeek') do set dia=%%a

REM Obtener hora actual (HHMM)
for /f %%a in ('powershell [datetime]::Now.ToString("HHmm")') do set tiempo=%%a

REM Solo ejecutar lunes-viernes (1-5) y entre 10:30-17:00
if %dia% geq 1 if %dia% leq 5 if %tiempo% geq 1030 if %tiempo% lss 1700 (
  cd /d C:\IA\Dashboard_Financiero
  node actualizar-bonos-windows.js >> %TEMP%\bonos_update.log 2>&1
)
