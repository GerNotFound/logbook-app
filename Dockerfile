# Fase 1: Usa un'immagine Python ufficiale e snella come base
FROM python:3.11-slim

# Imposta la cartella di lavoro all'interno del container
WORKDIR /app

# Imposta variabili d'ambiente per Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copia solo il file dei requisiti prima, per sfruttare la cache di Docker
COPY requirements.txt .

# Installa le dipendenze
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il resto del codice dell'applicazione
COPY . .

# Esponi la porta su cui Gunicorn sarà in ascolto
EXPOSE 8000

# MODIFICA TEMPORANEA
# Comando per avviare l'applicazione in produzione usando Gunicorn
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:create_app()"]

# NUOVO COMANDO: Esegui lo script del database una sola volta
CMD ["python", "database.py"]