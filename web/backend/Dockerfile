# Backend ZefiroSplit — FastAPI + trimesh/manifold3d
# Build context: raiz do repositório (precisa de src/ e config.json)
#   docker build -f web/backend/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

# Dependências primeiro (camada cacheável). pip atualizado (CVEs da ferramenta).
COPY web/backend/requirements.txt /app/web/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /app/web/backend/requirements.txt

# Código: src/ compartilhado + config + backend
COPY src /app/src
COPY config.json /app/config.json
COPY web/backend/*.py /app/web/backend/
COPY web/backend/routes /app/web/backend/routes

WORKDIR /app/web/backend

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

# --proxy-headers + --forwarded-allow-ips: atrás do nginx, o backend enxerga o
# IP real do cliente (X-Forwarded-For) em vez do IP do container — o rate-limit
# por IP volta a isolar cada cliente em vez de compartilhar um único balde.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
