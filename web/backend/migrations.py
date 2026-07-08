"""Migrações leves e idempotentes, rodadas no startup (após create_all).

create_all cria tabelas NOVAS mas não altera as existentes — os ADD COLUMN
daqui cobrem bancos criados antes da refatoração (users sem telefone etc.).
Cada passo é seguro de rodar duas vezes: Postgres usa IF NOT EXISTS; no SQLite
o erro "duplicate column" é engolido de propósito.
"""
from sqlalchemy import text

_USERS_NEW_COLUMNS = [
    ("telefone", "VARCHAR(40)"),
    ("codigo_acesso", "VARCHAR(20)"),
    ("status", "VARCHAR(20) DEFAULT 'ativo'"),
    ("plano", "VARCHAR(20)"),
    ("temp_password", "VARCHAR(64)"),
    ("token_version", "INTEGER DEFAULT 0"),
    ("last_login_at", "TIMESTAMP"),
    ("updated_at", "TIMESTAMP"),
]


def run_migrations(engine):
    is_sqlite = engine.dialect.name == "sqlite"
    with engine.begin() as conn:
        for col, ddl in _USERS_NEW_COLUMNS:
            if is_sqlite:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        raise
            else:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {ddl}"))
        # Contas pré-refatoração: garante status/versão e espelha o plano
        conn.execute(text("UPDATE users SET status = 'ativo' WHERE status IS NULL"))
        conn.execute(text("UPDATE users SET token_version = 0 WHERE token_version IS NULL"))
        conn.execute(text(
            "UPDATE users SET plano = ("
            "  SELECT s.plan FROM subscriptions s WHERE s.user_id = users.id"
            ") WHERE plano IS NULL"))
