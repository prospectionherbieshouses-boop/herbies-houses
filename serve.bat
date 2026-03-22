@echo off
cd /d "%~dp0"
echo Demarrage du serveur local...
echo Ouvre http://localhost:8080 dans ton navigateur
echo (Ctrl+C pour arreter)
echo.
python -m http.server 8080 --directory app
