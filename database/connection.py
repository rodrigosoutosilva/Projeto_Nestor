"""
connection.py - Gerenciamento de Conexão com o Banco de Dados
============================================================

Suporta dois modos:
- PostgreSQL (produção): via DATABASE_URL do Supabase/outro serviço
- SQLite (desenvolvimento local): fallback automático
"""

import os
import time
from urllib.parse import urlparse, unquote, parse_qs, quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# Marcador de versão para confirmar deploy
_VERSION = "v4-urllib-fix"
print(f"[connection] === Versão: {_VERSION} ===")

# ---------------------------------------------------------------------------
# DATABASE_URL: tenta Streamlit secrets PRIMEIRO, depois env var.
# Priorizar secrets evita conflito com env vars antigas no Streamlit Cloud.
# ---------------------------------------------------------------------------
DATABASE_URL = ""
_url_source = ""

# Prioridade 1: Streamlit Cloud secrets
try:
    import streamlit as st
    DATABASE_URL = st.secrets.get("DATABASE_URL", "")
    if DATABASE_URL:
        _url_source = "Streamlit Secrets"
except Exception:
    pass

# Prioridade 2: variável de ambiente
if not DATABASE_URL:
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    if DATABASE_URL:
        _url_source = "Variável de Ambiente"

# Fallback final: SQLite local para desenvolvimento
if not DATABASE_URL:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "invest_platform.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    _url_source = "SQLite (fallback local)"

print(f"[connection] Fonte da URL: {_url_source}")

# ---------------------------------------------------------------------------
# FIX: postgres:// → postgresql:// (SQLAlchemy 2.0+)
# ---------------------------------------------------------------------------
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("[connection] Convertido postgres:// → postgresql://")

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
    print("[connection] Banco: SQLite (local)")
else:
    # -----------------------------------------------------------------------
    # Parse seguro com urllib.parse (usa o ÚLTIMO '@' como separador,
    # lidando corretamente com senhas que contenham '@').
    # Depois constrói via URL.create() que escapa tudo automaticamente.
    # -----------------------------------------------------------------------
    _parsed = urlparse(DATABASE_URL)

    _host = _parsed.hostname or "localhost"
    _port = _parsed.port or 5432
    _user = unquote(_parsed.username) if _parsed.username else "postgres"
    _pass = unquote(_parsed.password) if _parsed.password else ""
    _db = (_parsed.path or "/postgres").lstrip("/")

    # Query params (ex: sslmode)
    _query = {}
    if _parsed.query:
        for k, v in parse_qs(_parsed.query).items():
            _query[k] = v[0] if len(v) == 1 else v

    # Garantir SSL para provedores cloud
    if "sslmode" not in _query:
        _query["sslmode"] = "require"

    # ---- DIAGNÓSTICO (sem expor senha) ----
    print(f"[connection] Banco: PostgreSQL (remoto)")
    print(f"[connection] Host: '{_host}'")
    print(f"[connection] Port: {_port}")
    print(f"[connection] User: '{_user}'")
    print(f"[connection] DB:   '{_db}'")
    print(f"[connection] SSL:  {_query.get('sslmode', 'não definido')}")
    print(f"[connection] Senha: {'***' + _pass[-4:] if len(_pass) > 4 else '****'}")
    # Mostra os primeiros 50 chars da URL mascarando a senha
    _safe_url = DATABASE_URL[:50] + "..." if len(DATABASE_URL) > 50 else DATABASE_URL
    print(f"[connection] URL (parcial): {_safe_url}")

    # Criar URL via SQLAlchemy URL.create() — escapa caracteres especiais
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


def init_db():
    """Cria tabelas e executa seed. Inclui retry para falhas transitórias."""
    from database.models import Base

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()

            Base.metadata.create_all(bind=engine)
            
            # Auto-migrate: adiciona colunas novas em banco existente (evita recriar o DB)
            try:
                with engine.connect() as conn:
                    # Tenta adicionar taxa_saldo_negativo
                    conn.execute(text("ALTER TABLE portfolios ADD COLUMN taxa_saldo_negativo FLOAT DEFAULT 10.0"))
                    conn.commit()
            except Exception:
                pass  # Coluna já existe ou erro ignorável
                
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
    """Context Manager para sessões do banco."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
