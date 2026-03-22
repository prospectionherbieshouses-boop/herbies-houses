@echo off
cd /d "%~dp0"
echo Lancement du scraper Herbies...
python scraper\run_local.py

echo.
echo Envoi des resultats sur GitHub...
git add app/listings.json app/terrains.json 2>nul
git commit -m "Mise a jour listings %date% %time%"
git push

echo.
echo Resultats en ligne : https://prospectionherbieshouses-boop.github.io/herbies-houses/
pause
