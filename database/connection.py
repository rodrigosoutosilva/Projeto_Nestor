"""
connection.py - Gerenciamento de Conexão com o Banco de Dados
============================================================

Suporta dois modos:
- PostgreSQL (produção): via DATABASE_URL do Supabase/outro serviço
- SQLite (desenvolvimento local): fallback automático
"""

import os
import time
from urllib.parse import urlparse, unquote, parse_qs
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Marcador de versão para confirmar deploy
_VERSION = "v6-varchar-migration"
print(f"[connection] === Versao: {_VERSION} ===")

# ---------------------------------------------------------------------------
# DATABASE_URL: tenta Streamlit secrets PRIMEIRO, depois env var.
# ---------------------------------------------------------------------------
DATABASE_URL = ""
_url_source = ""

try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL", "")
    if DATABASE_URL:
        _url_source = "Streamlit Secrets"
except Exception:
    pass

if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if DATABASE_URL:
        _url_source = "Variavel de Ambiente"

if not DATABASE_URL:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "invest_platform.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    _url_source = "SQLite (fallback local)"

print(f"[connection] Fonte da URL: {_url_source}")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("[connection] Convertido postgres:// -> postgresql://")

_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
    print("[connection] Banco: SQLite (local)")
else:
    _parsed = urlparse(DATABASE_URL)
    _host = _parsed.hostname or "localhost"
    _port = _parsed.port or 5432
    _user = unquote(_parsed.username) if _parsed.username else "postgres"
    _pass = unquote(_parsed.password) if _parsed.password else ""
    _db = (_parsed.path or "/postgres").lstrip("/")

    _query = {}
    if _parsed.query:
        for k, v in parse_qs(_parsed.query).items():
            _query[k] = v[0] if len(v) == 1 else v

    if "sslmode" not in _query:
        _query["sslmode"] = "require"

    print(f"[connection] Banco: PostgreSQL (remoto)")
    print(f"[connection] Host: '{_host}'")
    print(f"[connection] Port: {_port}")
    print(f"[connection] User: '{_user}'")
    print(f"[connection] DB:   '{_db}'")

    _url_object = URL.create(
        drivername="postgresql+psycopg2",
        username=_user,
        password=_pass,
        host=_host,
        port=_port,
        database=_db,
        query=_query,
    )

    engine = create_engine(
        _url_object,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
        pool_timeout=10,
        connect_args={"connect_timeout": 10},
        echo=False,
    )

# ---------------------------------------------------------------------------
# SessionLocal
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _executar_migracao(conn):
    """
    Migracao incremental de schema usando apenas VARCHAR.
    Sem tipos ENUM nativos do PostgreSQL — evita conflitos de tipo.
    Cada ALTER TABLE falha silenciosamente se a coluna ja existe.
    """
    def try_sql(sql, label=""):
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"[migration] OK ({label})")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                print(f"[migration] SKIP ({label}): {str(e)[:120]}")
            except Exception:
                print(f"[migration] SKIP ({label}): (erro nao imprimivel)")

    # -------------------------------------------------------------------
    # PERSONAS: adicionar perfil_investimento como VARCHAR
    # -------------------------------------------------------------------
    try_sql(
        "ALTER TABLE personas ADD COLUMN perfil_investimento VARCHAR(30) DEFAULT 'buy_and_hold'",
        "personas.perfil_investimento"
    )
    # Tentar migrar dados da coluna antiga frequencia_acao (pode nao existir)
    try_sql("""
        UPDATE personas SET perfil_investimento =
        CASE
            WHEN CAST(frequencia_acao AS VARCHAR) = 'diario' THEN 'day_trader'
            WHEN CAST(frequencia_acao AS VARCHAR) = 'semanal' THEN 'swing_trader'
            ELSE 'buy_and_hold'
        END
        WHERE perfil_investimento IS NULL OR perfil_investimento = ''
    """, "migrar frequencia->perfil")

    # -------------------------------------------------------------------
    # PORTFOLIOS: adicionar objetivo como VARCHAR
    # -------------------------------------------------------------------
    try_sql(
        "ALTER TABLE portfolios ADD COLUMN objetivo VARCHAR(30) DEFAULT 'equilibrado'",
        "portfolios.objetivo"
    )
    # Tentar migrar dados da coluna antiga objetivo_prazo (pode nao existir)
    try_sql("""
        UPDATE portfolios SET objetivo =
        CASE
            WHEN CAST(objetivo_prazo AS VARCHAR) = 'curto' THEN 'crescimento'
            WHEN CAST(objetivo_prazo AS VARCHAR) = 'longo' THEN 'dividendos'
            ELSE 'equilibrado'
        END
        WHERE objetivo IS NULL OR objetivo = ''
    """, "migrar objetivo_prazo->objetivo")

    # -------------------------------------------------------------------
    # Outras colunas
    # -------------------------------------------------------------------
    try_sql(
        "ALTER TABLE portfolios ADD COLUMN taxa_saldo_negativo FLOAT DEFAULT 10.0",
        "portfolios.taxa_saldo_negativo"
    )


def init_db():
    """Cria tabelas e executa seed. Inclui retry para falhas transitorias."""
    from database.models import Base

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()

            # Criar tabelas novas que nao existem ainda
            Base.metadata.create_all(bind=engine)

            # Migracao incremental: adiciona colunas/converte dados sem perder nada
            with engine.connect() as conn:
                _executar_migracao(conn)

            print(f"[connection] Banco inicializado/migrado com sucesso (tentativa {attempt})")
            break
        except Exception as e:
            print(f"[connection] Tentativa {attempt}/{max_retries} falhou: {e}")
            if attempt < max_retries:
                wait = attempt * 2
                print(f"[connection] Aguardando {wait}s...")
                time.sleep(wait)
            else:
                print(f"[connection] ERRO FINAL: {type(e).__name__}: {e}")
                raise

    try:
        from database.seed_data import seed_usuario_teste
        seed_usuario_teste()
    except Exception as e:
        print(f"[connection] Erro ao executar seed: {e}")


@contextmanager
def get_session():
    """Context Manager para sessoes do banco."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
