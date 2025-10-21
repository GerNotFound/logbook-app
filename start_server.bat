@echo off
echo Attivazione dell'ambiente virtuale...
call .\.venv\Scripts\activate.bat

echo Avvio del server di produzione (Waitress)...
echo L'app sara' disponibile su http://127.0.0.1:8000
echo Per fermare il server, chiudi questa finestra.

waitress-serve --host 127.0.0.1 --port 8000 app:app