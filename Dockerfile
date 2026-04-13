# Usamos la imagen oficial de Python ligera
FROM python:3.12-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de requerimientos e instalarlos
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el grueso de la aplicación
COPY . .

# Exponer el puerto
EXPOSE 8001

# Comando por defecto para correr FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
