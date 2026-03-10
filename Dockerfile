FROM python:3.10-slim
WORKDIR /app

# Copiar dependencias e instalarlas
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar archivos fuente con rutas absolutas
COPY main.py /app/main.py
COPY index.html /app/index.html

# Crear directorio para la base de datos y verificar archivos (opcional)
RUN mkdir -p /app/baccarat_data && ls -la /app

# Exponer puerto
EXPOSE 10000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
