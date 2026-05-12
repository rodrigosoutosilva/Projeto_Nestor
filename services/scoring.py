"""
scoring.py - Motor de Pontuação e Sugestões (Refatorado)
========================================================

Sistema reestruturado com dois algoritmos:
- Algoritmo 1 (Criação): Sugere novos ativos com foco em fundamentos e otimização de entrada.
- Algoritmo 2 (Manutenção): Sugere movimentações em carteira existente, com regras estritas de venda.
"""

from typing import List, Dict, Any
from services.market_data import buscar_dados_completos, buscar_preco_atual

# ==============================================================================
# ALGORITMO 1 - CRIAÇÃO (SELEÇÃO DE NOVOS ATIVOS)
# ==============================================================================

def _calcular_score_fundamental_criacao(ind: dict) -> float:
    # ROE (50%)
    roe = ind.get("roe")
    score_roe = 50
    if roe is not None:
        if roe > 20: score_roe = 90
        elif roe > 15: score_roe = 75
        elif roe > 10: score_roe = 55
        elif roe > 5: score_roe = 35
        else: score_roe = 15

    # Dívida/EBITDA (50%)
    divida_ebitda = ind.get("divida_liquida_ebitda")
    score_div = 50
    if divida_ebitda is not None:
        if divida_ebitda < 1: score_div = 90
        elif divida_ebitda < 2: score_div = 70
        elif divida_ebitda < 3: score_div = 50
        elif divida_ebitda < 4: score_div = 30
        else: score_div = 10

    return (score_roe * 0.5) + (score_div * 0.5)

def _calcular_score_valuation_criacao(ind: dict) -> float:
    # P/L (35%)
    pl = ind.get("pl")
    score_pl = 50
    if pl is not None and pl > 0:
        if pl < 8: score_pl = 90
        elif pl < 12: score_pl = 75
        elif pl < 18: score_pl = 55
        elif pl < 25: score_pl = 35
        else: score_pl = 15

    # P/VP (30%)
    pvp = ind.get("pvp")
    score_pvp = 50
    if pvp is not None and pvp > 0:
        if pvp < 1: score_pvp = 90
        elif pvp < 1.5: score_pvp = 70
        elif pvp < 3: score_pvp = 50
        else: score_pvp = 25

    # EV/EBITDA (35%)
    ev_ebitda = ind.get("ev_ebitda")
    score_ev = 50
    if ev_ebitda is not None and ev_ebitda > 0:
        if ev_ebitda < 6: score_ev = 90
        elif ev_ebitda < 8: score_ev = 70
        elif ev_ebitda < 12: score_ev = 50
        elif ev_ebitda < 16: score_ev = 30
        else: score_ev = 10

    return (score_pl * 0.35) + (score_pvp * 0.30) + (score_ev * 0.35)

def _calcular_score_dividendos_criacao(ind: dict) -> float:
    # DY (50%)
    dy = ind.get("dy")
    score_dy = 50
    if dy is not None:
        if dy > 10: score_dy = 95
        elif dy > 6: score_dy = 75
        elif dy > 3: score_dy = 55
        elif dy > 1: score_dy = 35
        else: score_dy = 15

    # Payout (50%)
    payout = ind.get("payout")
    score_payout = 50
    if payout is not None and payout > 0:
        if payout < 30: score_payout = 50
        elif payout <= 60: score_payout = 90
        elif payout <= 80: score_payout = 65
        elif payout <= 100: score_payout = 30
        else: score_payout = 10

    return (score_dy * 0.5) + (score_payout * 0.5)

def _calcular_score_tecnico_criacao(ind: dict) -> float:
    # RSI (40%)
    rsi = ind.get("rsi")
    score_rsi = 50
    if rsi is not None:
        if rsi < 30: score_rsi = 90
        elif rsi < 40: score_rsi = 70
        elif rsi < 60: score_rsi = 50
        elif rsi < 70: score_rsi = 35
        else: score_rsi = 15
        
    # SMA 20 (30%)
    sma20 = ind.get("sma_20")
    preco = ind.get("preco_atual")
    score_sma = 50
    if sma20 and preco:
        if preco < sma20: score_sma = 80
        else: score_sma = 40

    # MACD (20%)
    macd = ind.get("macd")
    macd_signal = ind.get("macd_signal")
    score_macd = 50
    if macd is not None and macd_signal is not None:
        if macd > macd_signal: score_macd = 70
        else: score_macd = 30

    # Volume (10%)
    volume_ratio = ind.get("volume_ratio")
    score_vol = 50
    if volume_ratio is not None:
        if volume_ratio > 1.5: score_vol = 70
        elif volume_ratio < 0.5: score_vol = 30

    return (score_rsi * 0.40) + (score_sma * 0.30) + (score_macd * 0.20) + (score_vol * 0.10)

def pontuar_ativo_criacao(ticker: str, persona: dict, portfolio: dict, usar_preco_futuro: bool = False) -> dict:
    """Algoritmo 1: Seleção de novos ativos."""
    dados = buscar_dados_completos(ticker)
    ind = dados.get("indicadores", {})
    if not ind:
        return {"score": 0, "acao": "N/D", "texto": "Dados indisponíveis."}

    estilo = persona.get("estilo", "dividendos")
    if estilo == "dividendos":
        w_fund, w_val, w_div, w_tec = 0.40, 0.25, 0.25, 0.10
    elif estilo == "crescimento":
        w_fund, w_val, w_div, w_tec = 0.30, 0.35, 0.05, 0.30
    else: # equilibrado
        w_fund, w_val, w_div, w_tec = 0.35, 0.30, 0.15, 0.20

    s_fund = _calcular_score_fundamental_criacao(ind)
    s_val = _calcular_score_valuation_criacao(ind)
    s_div = _calcular_score_dividendos_criacao(ind)
    s_tec = _calcular_score_tecnico_criacao(ind)

    score_base = (s_fund * w_fund) + (s_val * w_val) + (s_div * w_div) + (s_tec * w_tec)

    # Ajuste Multiplicador
    ajuste = 1.0
    risco = persona.get("tolerancia_risco", 5)
    ajuste += (risco - 5) * 0.015
    
    prazo = portfolio.get("objetivo_prazo", "longo")
    if prazo == "curto" and ind.get("dy", 0) > 6:
        ajuste += 0.05
    if prazo == "longo" and ind.get("roe", 0) > 15:
        ajuste += 0.05
        
    preco = ind.get("preco_atual", 0)
    alvo = ind.get("preco_alvo_medio", 0)
    if preco > 0 and alvo > 0:
        upside = (alvo - preco) / preco
        if upside > 0.20:
            ajuste += 0.05
        elif upside < 0.05:
            ajuste -= 0.05

    score_final = max(0, min(100, score_base * ajuste))

    if score_final >= 70:
        acao = "compra"
    elif score_final >= 55:
        acao = "observar"
    else:
        acao = "ignorar"
        
    texto = gerar_texto_resumo_criacao(ticker, score_final, acao, ind)

    return {
        "ticker": ticker,
        "score": int(score_final),
        "acao": acao,
        "texto": texto,
        "indicadores": ind,
        "scores_detalhados": {
            "fundamental": int(s_fund),
            "valuation": int(s_val),
            "dividendos": int(s_div),
            "tecnico": int(s_tec)
        }
    }

def gerar_texto_resumo_criacao(ticker: str, score: float, acao: str, ind: dict) -> str:
    partes = []
    
    # Valuation / Target
    preco = ind.get("preco_atual", 0)
    alvo = ind.get("preco_alvo_medio", 0)
    if preco > 0 and alvo > 0:
        upside = ((alvo - preco) / preco) * 100
        if upside > 10:
            partes.append(f"Potencial de valorização (Upside de {upside:.1f}% vs Preço-Alvo dos analistas).")
        elif upside < 0:
            partes.append(f"Preço atual acima do consenso dos analistas ({upside:.1f}%).")
            
    # Fundamentos
    roe = ind.get("roe")
    if roe and roe > 15:
        partes.append(f"ROE muito saudável ({roe:.1f}%), indicando eficiência.")
        
    div_ebitda = ind.get("divida_liquida_ebitda")
    if div_ebitda is not None:
        if div_ebitda < 2:
            partes.append(f"Dívida controlada (Dívida L./EBITDA = {div_ebitda:.1f}x).")
        elif div_ebitda > 3:
            partes.append(f"⚠️ Alerta de alavancagem alta (Dívida L./EBITDA = {div_ebitda:.1f}x).")

    # Dividendos
    dy = ind.get("dy")
    payout = ind.get("payout")
    if dy and dy > 6:
        msg_div = f"Ótimo DY ({dy:.1f}%)."
        if payout and payout <= 80:
            msg_div += f" Payout sustentável ({payout:.1f}%)."
        elif payout and payout > 100:
            msg_div += f" ⚠️ Payout insustentável ({payout:.1f}%)."
        partes.append(msg_div)

    # Timing Técnico
    rsi = ind.get("rsi")
    if rsi:
        if rsi < 35:
            partes.append("Preço descontado no curto prazo (RSI sobrevendido), indicando possível ponto de entrada ideal.")
        elif rsi > 70:
            partes.append("Preço esticado no curto prazo (RSI sobrecomprado).")

    resumo = " ".join(partes)
    if not resumo:
        resumo = f"Ativo em radar com Score {int(score)}. Verifique dados completos na análise detalhada."

    return resumo

# ==============================================================================
# ALGORITMO 2 - MANUTENÇÃO (CARTEIRA EXISTENTE)
# ==============================================================================

def pontuar_ativo_manutencao(ticker: str, persona: dict, portfolio: dict, pm_atual: float, usar_preco_futuro: bool = False) -> dict:
    """Algoritmo 2: Manutenção. Regras estritas de venda. Sem técnicos."""
    dados = buscar_dados_completos(ticker)
    ind = dados.get("indicadores", {})
    if not ind:
        return {"score": 50, "acao": "manter", "texto": "Dados indisponíveis."}

    # -- 1. Score de Saúde Fundamental (Monitora Deterioração) --
    s_saude = 50
    roe = ind.get("roe")
    div_ebitda = ind.get("divida_liquida_ebitda")
    margem = ind.get("margem_liquida")
    
    score_roe_m = 50
    if roe is not None:
        if roe >= 10: score_roe_m = 80
        elif roe < 5: score_roe_m = 15
        
    score_div_m = 50
    if div_ebitda is not None:
        if div_ebitda > 4: score_div_m = 10
        elif div_ebitda <= 2: score_div_m = 80
        
    score_margem = 50
    if margem is not None:
        if margem < 0: score_margem = 10
        elif margem > 10: score_margem = 70
        
    s_saude = (score_roe_m * 0.4) + (score_div_m * 0.4) + (score_margem * 0.2)

    # -- 2. Score de Valuation (Esticada de preço) --
    s_val = 50
    pl = ind.get("pl")
    score_pl_m = 50
    if pl is not None and pl > 0:
        if pl > 25: score_pl_m = 15 # Genérico, o ideal seria vs setor
        elif pl < 12: score_pl_m = 80

    preco = ind.get("preco_atual", 0)
    alvo = ind.get("preco_alvo_medio", 0)
    score_alvo = 50
    if preco > 0 and alvo > 0:
        razao = preco / alvo
        if razao > 1.2: score_alvo = 10
        elif razao > 1.0: score_alvo = 30
        elif razao < 0.8: score_alvo = 80
        
    s_val = (score_pl_m * 0.5) + (score_alvo * 0.5)

    # -- 3. Sustentabilidade de Proventos --
    s_prov = 50
    payout = ind.get("payout")
    dy = ind.get("dy")
    dy_medio = ind.get("dy_medio_5_anos")
    
    score_payout_m = 50
    if payout is not None and payout > 0:
        if payout > 120: score_payout_m = 10
        elif payout <= 80: score_payout_m = 80
        
    score_dy_hist = 50
    if dy is not None and dy_medio is not None and dy_medio > 0:
        if dy < (dy_medio * 0.5): score_dy_hist = 25
        else: score_dy_hist = 70
        
    s_prov = (score_payout_m * 0.6) + (score_dy_hist * 0.4)
    
    # Pesos do Algoritmo 2
    estilo = persona.get("estilo", "dividendos")
    if estilo == "dividendos":
        w_saude, w_val, w_prov = 0.45, 0.25, 0.30
    elif estilo == "crescimento":
        w_saude, w_val, w_prov = 0.35, 0.35, 0.30
    else:
        w_saude, w_val, w_prov = 0.40, 0.30, 0.30

    score_final = (s_saude * w_saude) + (s_val * w_val) + (s_prov * w_prov)

    # =====================================================
    # CIRCUITO-BREAKER (REGRAS DE VENDA)
    # =====================================================
    condicoes_venda = 0
    alerta_textos = []

    # 1. Valuation Extremo
    if pl is not None and pl > 25 and preco > (alvo * 1.2):
        condicoes_venda += 1
        alerta_textos.append("Preço esticou muito além do valor intrínseco e histórico.")

    # 2. Explosão de Dívida
    if div_ebitda is not None and div_ebitda > 4:
        condicoes_venda += 1
        alerta_textos.append("Alerta grave de aumento de endividamento (Dívida/EBITDA > 4x).")

    # 3. Colapso de Fundamentos
    if roe is not None and roe < 5 and margem is not None and margem < 0:
        condicoes_venda += 1
        alerta_textos.append("Colapso de rentabilidade (Margem negativa e ROE muito baixo).")

    # 4. Payout Insustentável
    if payout is not None and payout > 120 and dy is not None and dy_medio is not None and dy < (dy_medio * 0.5):
        condicoes_venda += 1
        alerta_textos.append("Política de dividendos insustentável, comprometendo o caixa.")

    # Ações:
    acao = "manter"
    if condicoes_venda >= 2:
        acao = "venda"
    elif condicoes_venda == 1:
        acao = "observar"
    else:
        # Reforço de posição?
        if s_saude >= 70:
            if alvo > 0 and preco < (alvo * 0.8):
                acao = "compra" # Reforçar
            elif preco > 0 and pm_atual > 0 and preco < pm_atual:
                acao = "compra" # Oportunidade de baixar PM

    # Geração de texto para manutenção
    texto = "Fundamentos sólidos, manter posição."
    if acao == "venda":
        texto = "⚠️ ALERTA DE VENDA: " + " ".join(alerta_textos)
    elif acao == "observar":
        texto = "Atenção necessária: " + alerta_textos[0]
    elif acao == "compra":
        if preco < pm_atual:
            texto = f"Oportunidade de reforçar posição e baixar Preço Médio (Atual: R${preco:.2f} | PM: R${pm_atual:.2f})."
        else:
            texto = "Ativo com bons fundamentos descontado vs Preço-Alvo."

    return {
        "ticker": ticker,
        "score": int(score_final),
        "acao": acao,
        "texto": texto,
        "indicadores": ind,
        "scores_detalhados": {
            "saude": int(s_saude),
            "valuation": int(s_val),
            "proventos": int(s_prov)
        }
    }


# ==============================================================================
# FACADES PARA O FRONTEND
# ==============================================================================

def gerar_sugestoes_novos_ativos(portfolio_id: int) -> list[dict]:
    """Retorna sugestões de COMPRA de ativos que não estão na carteira."""
    from database.crud import buscar_portfolio_por_id, listar_ativos_portfolio
    portfolio, persona = buscar_portfolio_por_id(portfolio_id)
    if not portfolio or not persona: return []

    ativos_atuais = listar_ativos_portfolio(portfolio_id)
    tickers_atuais = {a["ticker"] for a in ativos_atuais}
    
    # Exemplo de Universo Fixo (na vida real, isso viria de um filtro mais amplo)
    universo = ["VALE3", "PETR4", "ITUB4", "BBDC4", "BBAS3", "WEGE3", "EGIE3", "TAEE11", "MGLU3", "B3SA3"]
    
    sugestoes = []
    for ticker in universo:
        if ticker not in tickers_atuais:
            res = pontuar_ativo_criacao(ticker, persona, portfolio)
            if res["acao"] in ["compra", "observar"]:
                res["novo"] = True
                sugestoes.append(res)
                
    return sorted(sugestoes, key=lambda x: x["score"], reverse=True)


def gerar_sugestoes_manutencao(portfolio_id: int, usar_preco_futuro: bool = False) -> list[dict]:
    """Retorna sugestões de MANUTENÇÃO (Compra, Venda, Manter) para quem JÁ está na carteira."""
    from database.crud import buscar_portfolio_por_id, listar_ativos_portfolio
    portfolio, persona = buscar_portfolio_por_id(portfolio_id)
    if not portfolio or not persona: return []

    ativos_atuais = listar_ativos_portfolio(portfolio_id)
    sugestoes = []
    
    for ativo in ativos_atuais:
        res = pontuar_ativo_manutencao(ativo["ticker"], persona, portfolio, pm_atual=ativo["preco_medio"], usar_preco_futuro=usar_preco_futuro)
        res["novo"] = False
        sugestoes.append(res)
        
    # Ordena: Vendas primeiro, Compras depois, Manter por último
    def peso_acao(acao):
        if acao == "venda": return 0
        if acao == "compra": return 1
        if acao == "observar": return 2
        return 3
        
    return sorted(sugestoes, key=lambda x: peso_acao(x["acao"]))

# ==============================================================================
# UTILITÁRIO MANTIDO PARA COMPATIBILIDADE (Se usado isoladamente noutro lugar)
# ==============================================================================
def calcular_score_tecnico(indicadores: dict) -> float:
    return _calcular_score_tecnico_criacao(indicadores)

def calcular_score_fundamental(indicadores: dict) -> float:
    return _calcular_score_fundamental_criacao(indicadores)

def pontuar_ativo(ticker: str, persona: dict, portfolio: dict, pm_atual: float = 0.0, usar_preco_futuro: bool = False) -> dict:
    """Fallback antigo que redireciona conforme PM para não quebrar outras áreas."""
    if pm_atual > 0:
        return pontuar_ativo_manutencao(ticker, persona, portfolio, pm_atual, usar_preco_futuro)
    else:
        return pontuar_ativo_criacao(ticker, persona, portfolio, usar_preco_futuro)
