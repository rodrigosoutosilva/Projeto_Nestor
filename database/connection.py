"""
connection.py - Gerenciamento de Conexão com o Banco de Dados
============================================================

Conceito de Engenharia de Software: Padrão Singleton para conexão.
Usamos SQLAlchemy como ORM (Object-Relational Mapping) para abstrair
o SQL puro, tornando o código mais Pythonico e seguro contra SQL Injection.

SQLite é ideal para este projeto pois:
- Zero configuração (arquivo local)
- Perfeito para aplicações single-user
- Fácil de fazer backup (copiar 1 arquivo)
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Caminho do banco: fica na raiz do projeto como "invest_platform.db"
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "invest_platform.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# ---------------------------------------------------------------------------
# Engine: ponto central de comunicação do SQLAlchemy com o banco SQLite.
# check_same_thread=False é necessário para uso com Streamlit (multi-thread).
# ---------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Mude para True para debug SQL
)

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
    """
    from database.models import Base
    Base.metadata.create_all(bind=engine)

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
