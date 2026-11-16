@echo off
REM Doble clic: abre el simulador en el navegador (solo requiere Python 3.8+; no instala nada)
cd /d "%~dp0"
where py >nul 2>nul && (py main.py) || (python main.py)
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Verifica que Python este instalado (python.org).
  pause
)
