FROM python:3.10-slim

WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el script
COPY baccarat.py .

# Crear directorio para la base de datos
RUN mkdir -p /app/baccarat_data

# Volumen para persistencia
VOLUME /app/baccarat_data

# Ejecutar el script
CMD ["python", "baccarat.py"]
