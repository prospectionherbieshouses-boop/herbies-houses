@echo off
echo Configuration du scraper automatique (1x par jour a 8h00)...

set SCRIPT_PATH=%~dp0scraper\run_local.py
set PYTHON_PATH=python

schtasks /create ^
  /tn "Herbies Houses Scraper" ^
  /tr "%PYTHON_PATH% \"%SCRIPT_PATH%\"" ^
  /sc daily ^
  /st 08:00 ^
  /f

if %errorlevel% == 0 (
    echo.
    echo Tache creee avec succes !
    echo Le scraper tournera tous les jours a 8h00.
    echo.
    echo Pour voir la tache : Planificateur de taches Windows
    echo Pour la supprimer  : schtasks /delete /tn "Herbies Houses Scraper" /f
) else (
    echo Erreur lors de la creation de la tache.
)

pause
