import sys
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_session, init_db
from database.crud import Portfolio, Transaction, cobrar_juros_cheque_especial, criar_usuario, criar_persona, criar_portfolio
from database.models import User, Persona

init_db()

with get_session() as session:
    # 1. Setup minimal data for testing if it doesn't exist
    user = session.query(User).filter_by(email="test_juros@example.com").first()
    if not user:
        user = User(nome="Test Juros", email="test_juros@example.com", senha="123")
        session.add(user)
        session.flush()

    persona = session.query(Persona).filter_by(user_id=user.id, nome="Test Persona").first()
    if not persona:
        persona = Persona(user_id=user.id, nome="Test Persona")
        session.add(persona)
        session.flush()

    # Create a dummy portfolio
    port = Portfolio(
        persona_id=persona.id,
        nome="Carteira Negativada",
        objetivo_prazo="curto",
        tipo_ativo="misto",
        aporte_periodico=0,
        montante_disponivel=-1000.0 # Negative balance
    )
    session.add(port)
    session.commit()

    # Record ID for test
    port_id = port.id

# 2. Run the interest function
print("Lidando com saldo de -R$1000.0 ... Cobrando juros...")
cobrar_juros_cheque_especial()

# 3. Verify modifications
with get_session() as session:
    port = session.query(Portfolio).filter_by(id=port_id).first()
    taxa_esperada = (10.0 / 100.0 / 30.0) * 1000.0
    saldo_esperado = -1000.0 - taxa_esperada
    
    print(f"Saldo Original: -1000.0")
    print(f"Taxa Esperada (aprox): {taxa_esperada:.4f}")
    print(f"Novo Saldo: {port.montante_disponivel:.4f}")

    if abs(port.montante_disponivel - saldo_esperado) < 0.0001:
        print("[OK] Cobranca aplicada corretamente no Portfolio.")
    else:
        print("[ERRO] Erro na atualizacao do Portfolio.")
        
    transacoes = session.query(Transaction).filter_by(portfolio_id=port_id).all()
    if any("Juros" in t.descricao for t in transacoes):
        print("[OK] Transacao de Juros registrada no historico.")
    else:
        print("[ERRO] Faltando transacao no historico.")

print("Testes finais concluídos.")
