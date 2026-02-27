"""
seed_data.py - Dados Iniciais de Teste
========================================

Cria o usuário "teste" (senha "teste") com 3 personas pré-configuradas:
- Adão: Arrojado, diário, 3 carteiras de ações
- Ricardo: Conservador, mensal, 2 carteiras de FIIs
- Trevor: Equilibrado, semanal, 2 carteiras mistas

Executado automaticamente no init_db() se o usuário "teste" não existir.
"""

from datetime import date, timedelta
from database.crud import (
    criar_usuario, buscar_usuario_por_email,
    criar_persona, criar_portfolio, adicionar_ativo,
    registrar_transacao
)


def _aporte(portfolio_id, valor, descricao, dias_atras):
    """Helper para registrar aporte com keyword args."""
    registrar_transacao(
        portfolio_id=portfolio_id,
        tipo="aporte",
        valor=valor,
        descricao=descricao,
        data_transacao=date.today() - timedelta(days=dias_atras),
        origem="seed"
    )


def _compra(portfolio_id, ticker, preco, qtd, descricao, dias_atras):
    """Helper para registrar compra + adicionar ativo."""
    adicionar_ativo(portfolio_id, ticker, preco, qtd,
                    data_posicao=date.today() - timedelta(days=dias_atras))
    registrar_transacao(
        portfolio_id=portfolio_id,
        tipo="compra",
        valor=preco * qtd,
        ticker=ticker,
        quantidade=qtd,
        preco_unitario=preco,
        descricao=descricao,
        data_transacao=date.today() - timedelta(days=dias_atras),
        origem="seed"
    )


def _dividendo(portfolio_id, valor, ticker, descricao, dias_atras):
    """Helper para registrar dividendo."""
    registrar_transacao(
        portfolio_id=portfolio_id,
        tipo="dividendo",
        valor=valor,
        ticker=ticker,
        descricao=descricao,
        data_transacao=date.today() - timedelta(days=dias_atras),
        origem="seed"
    )


def seed_usuario_teste():
    """Cria o usuário teste com todas as personas, carteiras e ativos."""

    existente = buscar_usuario_por_email("teste")
    if existente:
        return

    user = criar_usuario("Usuário Teste", "teste", "teste")
    uid = user["id"]

    # ===================================================================
    # PERSONA 1: Adão — Arrojado, Diário
    # ===================================================================
    adao = criar_persona(user_id=uid, nome="Adão", frequencia="diario",
                         tolerancia_risco=8, estilo="crescimento")

    # Carteira 1: Bancos (~R$1000, ~3 anos)
    c1 = criar_portfolio(persona_id=adao["id"], nome="Bancos Brasileiros",
                         objetivo_prazo="longo", meta_dividendos=5.0,
                         tipo_ativo="acoes", setores_preferidos="bancos,financeiro",
                         montante_disponivel=0)
    _aporte(c1["id"], 1000.0, "Aporte inicial", 1095)
    _compra(c1["id"], "ITUB4", 28.50, 15, "Compra ITUB4", 1095)
    _compra(c1["id"], "BBDC4", 13.20, 20, "Compra BBDC4", 900)
    _compra(c1["id"], "BBAS3", 27.80, 10, "Compra BBAS3", 730)

    # Carteira 2: Mineração (~R$1000, ~1 ano)
    c2 = criar_portfolio(persona_id=adao["id"], nome="Mineração & Commodities",
                         objetivo_prazo="medio", meta_dividendos=4.0,
                         tipo_ativo="acoes", setores_preferidos="mineracao,commodities",
                         montante_disponivel=0)
    _aporte(c2["id"], 1000.0, "Aporte inicial", 365)
    _compra(c2["id"], "VALE3", 68.50, 8, "Compra VALE3", 365)
    _compra(c2["id"], "CMIN3", 5.80, 40, "Compra CMIN3", 200)
    _compra(c2["id"], "CSNA3", 12.40, 15, "Compra CSNA3", 120)

    # Carteira 3: Mista (~R$1000, ~2 meses)
    c3 = criar_portfolio(persona_id=adao["id"], nome="Ações Diversificadas",
                         objetivo_prazo="longo", meta_dividendos=6.0,
                         tipo_ativo="acoes", setores_preferidos="tecnologia,energia,varejo",
                         montante_disponivel=0)
    _aporte(c3["id"], 1000.0, "Aporte inicial", 60)
    _compra(c3["id"], "PETR4", 37.50, 10, "Compra PETR4", 60)
    _compra(c3["id"], "WEGE3", 35.00, 8, "Compra WEGE3", 45)
    _compra(c3["id"], "MGLU3", 8.20, 30, "Compra MGLU3", 30)
    _aporte(c3["id"], 1000.0, "Caixa para investir", 5)

    # ===================================================================
    # PERSONA 2: Ricardo — Conservador, Mensal
    # ===================================================================
    ricardo = criar_persona(user_id=uid, nome="Ricardo", frequencia="mensal",
                            tolerancia_risco=3, estilo="dividendos")

    # Carteira 1: FIIs Tijolo (~R$1500)
    c4 = criar_portfolio(persona_id=ricardo["id"], nome="FIIs Tijolo",
                         objetivo_prazo="longo", meta_dividendos=8.0,
                         tipo_ativo="fiis", setores_preferidos="logistica,shoppings",
                         montante_disponivel=0)
    _aporte(c4["id"], 1500.0, "Aporte inicial", 540)
    _compra(c4["id"], "HGLG11", 160.00, 3, "Compra HGLG11", 540)
    _compra(c4["id"], "XPML11", 95.00, 5, "Compra XPML11", 400)
    _compra(c4["id"], "VISC11", 105.00, 5, "Compra VISC11", 300)

    # Carteira 2: FIIs Papel (~R$1500)
    c5 = criar_portfolio(persona_id=ricardo["id"], nome="FIIs Papel",
                         objetivo_prazo="longo", meta_dividendos=10.0,
                         tipo_ativo="fiis", setores_preferidos="recebiveis,papel",
                         montante_disponivel=0)
    _aporte(c5["id"], 1500.0, "Aporte inicial", 450)
    _compra(c5["id"], "MXRF11", 10.20, 60, "Compra MXRF11", 450)
    _compra(c5["id"], "KNCR11", 100.50, 4, "Compra KNCR11", 350)
    _compra(c5["id"], "HGCR11", 100.00, 4, "Compra HGCR11", 250)

    # Ricardo: R$1000 extra + dividendos
    _aporte(c4["id"], 1000.0, "Capital adicional", 10)
    for i in range(6):
        _dividendo(c4["id"], 12.50, "HGLG11", "Rendimento mensal HGLG11", 30 * (i + 1))
        _dividendo(c5["id"], 6.00, "MXRF11", "Rendimento mensal MXRF11", 30 * (i + 1))

    # ===================================================================
    # PERSONA 3: Trevor — Equilibrado, Semanal
    # ===================================================================
    trevor = criar_persona(user_id=uid, nome="Trevor", frequencia="semanal",
                           tolerancia_risco=5, estilo="equilibrado")

    # Carteira 1: Blue Chips (~R$1500)
    c6 = criar_portfolio(persona_id=trevor["id"], nome="Blue Chips BR",
                         objetivo_prazo="longo", meta_dividendos=6.0,
                         tipo_ativo="acoes", setores_preferidos="bancos,petroleo,mineracao",
                         montante_disponivel=0)
    _aporte(c6["id"], 2000.0, "Aporte inicial", 500)
    _compra(c6["id"], "PETR4", 32.00, 15, "Compra PETR4", 500)
    _compra(c6["id"], "VALE3", 72.00, 5, "Compra VALE3", 400)
    _compra(c6["id"], "BBAS3", 30.00, 10, "Compra BBAS3", 300)
    _compra(c6["id"], "ABEV3", 14.50, 25, "Compra ABEV3", 200)

    # Carteira 2: FIIs Diversificados (~R$1500)
    c7 = criar_portfolio(persona_id=trevor["id"], nome="FIIs Diversificados",
                         objetivo_prazo="longo", meta_dividendos=8.0,
                         tipo_ativo="fiis", setores_preferidos="logistica,recebiveis,shoppings",
                         montante_disponivel=0)
    _aporte(c7["id"], 2000.0, "Aporte inicial", 400)
    _compra(c7["id"], "HGLG11", 155.00, 4, "Compra HGLG11", 400)
    _compra(c7["id"], "MXRF11", 10.50, 50, "Compra MXRF11", 300)
    _compra(c7["id"], "XPML11", 98.00, 4, "Compra XPML11", 200)

    # Trevor: R$1000 extra + dividendos
    _aporte(c6["id"], 500.0, "Capital adicional", 7)
    _aporte(c7["id"], 500.0, "Capital adicional", 7)
    for i in range(4):
        _dividendo(c7["id"], 15.00, "HGLG11", "Rendimento mensal HGLG11", 30 * (i + 1))
        _dividendo(c7["id"], 5.00, "MXRF11", "Rendimento mensal MXRF11", 30 * (i + 1))

    print("[seed_data] Usuário 'teste' criado com 3 personas, 7 carteiras e ativos pré-configurados!")
