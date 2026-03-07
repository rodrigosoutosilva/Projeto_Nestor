"""
connection.py - Gerenciamento de Conexão com o Banco de Dados
============================================================

Conceito de Engenharia de Software: Padrão Singleton para conexão.
Usamos SQLAlchemy como ORM (Object-Relational Mapping) para abstrair
o SQL puro, tornando o código mais Pythonico e seguro contra SQL Injection.

Suporta dois modos:
- PostgreSQL (produção): via DATABASE_URL do Supabase/outro serviço
- SQLite (desenvolvimento local): fallback automático quando DATABASE_URL
  não está configurada
"""

import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# DATABASE_URL: tenta ler de variáveis de ambiente, .env, ou Streamlit secrets.
# Se não encontrar, usa SQLite local como fallback para desenvolvimento.
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Fallback: Streamlit Cloud secrets (para deploy)
if not DATABASE_URL:
    try:
        import streamlit as st
        DATABASE_URL = st.secrets.get("DATABASE_URL", "")
    except Exception:
        pass

# Fallback final: SQLite local para desenvolvimento
if not DATABASE_URL:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "invest_platform.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# FIX: Muitos provedores (Supabase, Heroku, Render) fornecem DATABASE_URL
# com o scheme "postgres://", mas SQLAlchemy 2.0+ exige "postgresql://".
# Convertemos automaticamente para evitar OperationalError.
# ---------------------------------------------------------------------------
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("[connection] Convertido postgres:// → postgresql://")

# ---------------------------------------------------------------------------
# Engine: ponto central de comunicação do SQLAlchemy com o banco.
# Configuração varia entre SQLite e PostgreSQL.
# ---------------------------------------------------------------------------
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # Detecta conexões mortas antes de usar
        pool_size=5,           # Conexões mantidas no pool
        max_overflow=10,       # Conexões extras em pico de uso
        pool_recycle=300,      # Recicla conexões a cada 5 min (evita timeout)
        pool_timeout=10,       # Timeout ao obter conexão do pool
        echo=False
    )

_db_tipo = "SQLite (local)" if _is_sqlite else "PostgreSQL (remoto)"
print(f"[connection] Banco de dados: {_db_tipo}")

# ---------------------------------------------------------------------------
# SessionLocal: fábrica de sessões. Cada chamada cria uma "conversa" com o DB.
# autoflush=False evita writes automáticos, dando mais controle ao dev.
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """
    Cria todas as tabelas definidas nos modelos (se não existirem).
    Chamado uma vez no startup do app.

    Conceito: DDL (Data Definition Language) - comandos que definem
    a estrutura do banco (CREATE TABLE, ALTER TABLE, etc.)

    Inclui retry para lidar com falhas transitórias de conexão
    (ex: banco pausado, cold start do Supabase, rede instável).
    """
    from database.models import Base

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            # Testa a conexão primeiro
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()

            # Conexão OK — cria as tabelas
            Base.metadata.create_all(bind=engine)
            print(f"[connection] Banco inicializado com sucesso (tentativa {attempt})")
            break
        except Exception as e:
            print(f"[connection] Tentativa {attempt}/{max_retries} falhou: {e}")
            if attempt < max_retries:
                wait = attempt * 2  # backoff: 2s, 4s
                print(f"[connection] Aguardando {wait}s antes de tentar novamente...")
                time.sleep(wait)
            else:
                print(f"[connection] ERRO: Não foi possível conectar ao banco após {max_retries} tentativas.")
                print(f"[connection] Verifique se DATABASE_URL está correto e o banco está acessível.")
                raise

    # Seed: cria o usuário teste se não existir
    try:
        from database.seed_data import seed_usuario_teste
        seed_usuario_teste()
    except Exception as e:
        print(f"[connection] Erro ao executar seed: {e}")


@contextmanager
def get_session():
    """
    Context Manager para sessões do banco.

    Conceito de Eng. Software: Padrão Context Manager garante que
    a sessão será fechada mesmo se ocorrer um erro (try/finally implícito).

    Uso:
        with get_session() as session:
            session.query(User).all()
    """
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

