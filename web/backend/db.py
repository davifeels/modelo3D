"""Conexão com o banco de dados (SQLAlchemy).

- Produção/Docker: DATABASE_URL=postgresql+psycopg2://zefiro:zefiro@db:5432/zefiro
  (serviço `db` no docker-compose.yml).
- Dev local sem Docker: sem DATABASE_URL definido, cai em SQLite ao lado do backend
  (web/backend/zefiro.db) — zero setup para rodar uvicorn e a suíte de testes.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

_DEFAULT_SQLITE = "sqlite:///" + os.path.join(os.path.dirname(__file__), "zefiro.db").replace("\\", "/")
DATABASE_URL = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    """Dependency FastAPI: uma sessão de banco por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria as tabelas que ainda não existem. Chamado no startup do app."""
    import models  # noqa: F401 — registra os modelos no metadata
    Base.metadata.create_all(bind=engine)
