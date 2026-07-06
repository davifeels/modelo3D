import sys
import os

# Permite importar src.* do projeto raiz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from routes.mesh import router as mesh_router
from routes.export import router as export_router

app = FastAPI(title="ZefiroSplit API", version="1.0.0")

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção: restringir ao domínio do frontend
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mesh_router)
app.include_router(export_router)


@app.get("/health")
def health():
    return {"status": "ok"}
