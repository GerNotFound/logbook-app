@echo off
title Logbook Launcher

echo ======================================================
echo == Avvio del server Logbook e del Tunnel Cloudflare ==
echo ======================================================
echo.
echo Verranno aperte due nuove finestre del terminale:
echo   1. Il server della tua app (Waitress)
echo   2. Il tunnel di connessione a internet (Cloudflare)
echo.
echo NON CHIUDERE QUELLE FINESTRE per mantenere il sito online.
echo.

echo Avvio del server Waitress...
start "Logbook Server (Waitress)" cmd /c ".\.venv\Scripts\activate.bat && waitress-serve --host 127.0.0.1 --port 8000 app:app"

echo Attendo 5 secondi per l'avvio del server...
timeout /t 5

echo Avvio del Cloudflare Tunnel...
start "Cloudflare Tunnel" .\cloudflared.exe tunnel --url http://127.0.0.1:8000

echo.
echo Avvio completato. Cerca il link https://....trycloudflare.com nella finestra "Cloudflare Tunnel".
echo.
pause