import sys
import os

# Permite importar src.* do projeto raiz
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from bootstrap import seed_admin
from db import init_db
from routes.auth import router as auth_router, get_current_user
from routes.billing_routes import router as billing_router
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


@app.on_event("startup")
def _startup():
    init_db()
    seed_admin()  # conta do dono (ADMIN_EMAIL/ADMIN_PASSWORD) — Pro ativo


# Públicos: registro/login e billing (catálogo público; os demais endpoints de
# billing exigem token internamente; o webhook autentica por assinatura própria)
app.include_router(auth_router)
app.include_router(billing_router)

# TODOS os endpoints de malha e exportação exigem usuário autenticado
app.include_router(mesh_router, dependencies=[Depends(get_current_user)])
app.include_router(export_router, dependencies=[Depends(get_current_user)])


@app.get("/health")
def health():
    return {"status": "ok"}
