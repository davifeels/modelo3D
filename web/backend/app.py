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
from routes.admin import router as admin_router
from routes.billing_routes import router as billing_router
from routes.mesh import router as mesh_router
from routes.export import router as export_router
from routes.purchase import router as purchase_router

# Docs (Swagger/OpenAPI) só quando explicitamente habilitados (dev). Em
# produção ficam OFF para não expor toda a superfície da API.
_DOCS = os.environ.get("ZS_ENABLE_DOCS", "0") == "1"
app = FastAPI(
    title="ZefiroSplit API", version="1.0.0",
    docs_url="/docs" if _DOCS else None,
    redoc_url="/redoc" if _DOCS else None,
    openapi_url="/openapi.json" if _DOCS else None,
)

# CORS restrito: origens permitidas via env (lista separada por vírgula).
# Sem '*' — os tokens vão no header Authorization a partir do front conhecido.
_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.on_event("startup")
def _startup():
    init_db()
    seed_admin()  # conta do dono (ADMIN_EMAIL/ADMIN_PASSWORD) — Pro ativo


# Públicos: login, compra (única porta de entrada de clientes) e billing
# (catálogo público; os demais endpoints exigem token internamente; o webhook
# autentica por assinatura própria). Admin tem autenticação separada.
app.include_router(auth_router)
app.include_router(purchase_router)
app.include_router(admin_router)
app.include_router(billing_router)

# TODOS os endpoints de malha e exportação exigem usuário autenticado
app.include_router(mesh_router, dependencies=[Depends(get_current_user)])
app.include_router(export_router, dependencies=[Depends(get_current_user)])


@app.get("/health")
def health():
    return {"status": "ok"}
