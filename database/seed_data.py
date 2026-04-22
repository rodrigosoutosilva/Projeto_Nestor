"""
seed_data.py - Dados Iniciais de Teste
========================================

Cria o usuário "teste" (senha "teste") com 2 personas pré-configuradas:
- Thiaguinho: Arrojado, semanal, 1 carteira (Mix Ações)
- Palmito: Conservador, manual, 1 carteira (Ações)

Todas as carteiras: R$500 caixa, R$100 aporte mensal, sem ativos.

Executado automaticamente no init_db() se o usuário "teste" não existir.
"""

from datetime import date, timedelta
from database.crud import (
    criar_usuario, buscar_usuario_por_email,
    criar_persona, criar_portfolio,
    registrar_transacao
)


def seed_usuario_teste():
    """Cria o usuário teste com personas e carteiras pré-configuradas."""

    existente = buscar_usuario_por_email("teste")
    if existente:
        return

    user = criar_usuario("Usuário Teste", "teste", "teste")
    uid = user["id"]

    # ===================================================================
    # PERSONA 1: Thiaguinho — Arrojado, Semanal
    # ===================================================================
    thiaguinho = criar_persona(
        user_id=uid, nome="Thiaguinho", frequencia="semanal",
        tolerancia_risco=8, estilo="crescimento"
    )

    # Carteira 1: Mix Ações (todos setores, curto prazo, valorização)
    c1 = criar_portfolio(
        persona_id=thiaguinho["id"], nome="Mix Ações",
        objetivo_prazo="curto", meta_dividendos=2.0,
        tipo_ativo="acoes", setores_preferidos="bancos,energia,mineracao,tecnologia,varejo,saude",
        montante_disponivel=0,
        aporte_periodico=100.0, frequencia_aporte="mensal"
    )
    registrar_transacao(
        portfolio_id=c1["id"], tipo="aporte", valor=500.0,
        descricao="Aporte inicial", data_transacao=date.today()
    )

    # ===================================================================
    # PERSONA 2: Palmito — Conservador, Manual (mensal)
    # ===================================================================
    palmito = criar_persona(
        user_id=uid, nome="Palmito", frequencia="mensal",
        tolerancia_risco=3, estilo="dividendos"
    )

    # Carteira 1: Ações (energia, mineração, bancos, médio prazo)
    c3 = criar_portfolio(
        persona_id=palmito["id"], nome="Ações",
        objetivo_prazo="medio", meta_dividendos=5.0,
        tipo_ativo="acoes", setores_preferidos="energia,mineracao,bancos",
        montante_disponivel=0,
        aporte_periodico=100.0, frequencia_aporte="mensal"
    )
    registrar_transacao(
        portfolio_id=c3["id"], tipo="aporte", valor=500.0,
        descricao="Aporte inicial", data_transacao=date.today()
    )

    print("[seed_data] Usuário 'teste' criado com 2 personas (Thiaguinho + Palmito) e 2 carteiras vazias!")
