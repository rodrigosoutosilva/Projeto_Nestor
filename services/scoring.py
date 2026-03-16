"""
scoring.py - Motor de Scoring sem IA (v2 — Fundamentalista + Técnico)
======================================================================
Calcula pontuações para ativos com base em indicadores técnicos,
dados fundamentalistas (P/L, P/VP, DY) e perfil do investidor.

Score Final = (Técnico * 0.35) + (Fundamentalista * 0.35) + (Perfil * 0.30)

Parâmetros neutros nos limites técnicos para configuração futura.
"""
from services.market_data import (
    buscar_historico, calcular_indicadores_tecnicos,
    buscar_dados_fundamentalistas
)
from database.crud import buscar_persona_por_id, buscar_portfolio_por_id, listar_ativos_portfolio
from utils.helpers import formatar_moeda


# =====================================================================
# LIMITES CONFIGURÁVEIS (posição neutra — ajustáveis no futuro)
# =====================================================================
LIMITES = {
    "rsi_sobrevendido": 30,
    "rsi_sobrecomprado": 70,
    "pl_barato": 10,
    "pl_caro": 25,
    "pvp_barato": 1.0,
    "pvp_caro": 3.0,
    "dy_bom": 6.0,       # % ao ano
    "dy_otimo": 10.0,     # % ao ano
    "volume_alto": 1.5,   # ratio vs média 20d
}


def calcular_score_tecnico(indicadores: dict) -> float:
    """
    Score técnico (0–100) baseado em RSI, SMA, MACD e Volume.
    """
    rsi = indicadores.get("rsi", 50)
    preco = indicadores.get("preco_atual", 0)
    sma_20 = indicadores.get("sma_20", preco)
    macd = indicadores.get("macd", 0)
    macd_signal = indicadores.get("macd_signal", 0)
    volume_ratio = indicadores.get("volume_ratio", 1.0)

    # --- Score RSI (0–100) ---
    if rsi <= LIMITES["rsi_sobrevendido"]:
        score_rsi = 80 + (LIMITES["rsi_sobrevendido"] - rsi)
    elif rsi >= LIMITES["rsi_sobrecomprado"]:
        score_rsi = max(0, 30 - (rsi - LIMITES["rsi_sobrecomprado"]))
    else:
        score_rsi = 50 + (50 - rsi) * 0.75
    score_rsi = max(0, min(100, score_rsi))

    # --- Score SMA (0–100) ---
    if sma_20 > 0:
        desvio = ((preco - sma_20) / sma_20) * 100
        score_sma = 50 + desvio * 5
        score_sma = max(0, min(100, score_sma))
    else:
        score_sma = 50

    # --- Score MACD (0–100) ---
    if macd > macd_signal:
        score_macd = 60 + min(40, abs(macd - macd_signal) * 1000)
    else:
        score_macd = 40 - min(40, abs(macd - macd_signal) * 1000)
    score_macd = max(0, min(100, score_macd))

    # --- Score Volume (0–100) — volume alto confirma tendência ---
    if volume_ratio > LIMITES["volume_alto"]:
        score_vol = 70
    elif volume_ratio > 1.0:
        score_vol = 55
    elif volume_ratio > 0.5:
        score_vol = 40
    else:
        score_vol = 25

    # Média ponderada: RSI(35%) + SMA(25%) + MACD(25%) + Volume(15%)
    score_final = (score_rsi * 0.35) + (score_sma * 0.25) + (score_macd * 0.25) + (score_vol * 0.15)
    return round(max(0, min(100, score_final)), 2)


def calcular_score_fundamentalista(fundamentos: dict, portfolio: dict) -> float:
    """
    Score fundamentalista (0–100) baseado em P/L, P/VP e DY.
    Posição neutra quando os dados não estão disponíveis.
    """
    pl = fundamentos.get("pl")
    pvp = fundamentos.get("pvp")
    dy = fundamentos.get("dy")
    estilo = portfolio.get("objetivo_prazo", "medio")

    scores = []
    pesos = []

    # --- Score P/L ---
    if pl is not None and pl > 0:
        if pl < LIMITES["pl_barato"]:
            score_pl = 85   # Potencialmente barato
        elif pl < LIMITES["pl_caro"]:
            score_pl = 55   # Faixa razoável
        else:
            score_pl = 25   # Caro
        scores.append(score_pl)
        pesos.append(0.35)

    # --- Score P/VP ---
    if pvp is not None and pvp > 0:
        if pvp < LIMITES["pvp_barato"]:
            score_pvp = 85  # Abaixo do patrimônio — potencial de valor
        elif pvp < LIMITES["pvp_caro"]:
            score_pvp = 55  # Faixa neutra
        else:
            score_pvp = 25  # Premium alto
        scores.append(score_pvp)
        pesos.append(0.35)

    # --- Score DY ---
    if dy is not None and dy > 0:
        if dy >= LIMITES["dy_otimo"]:
            score_dy = 90
        elif dy >= LIMITES["dy_bom"]:
            score_dy = 70
        elif dy >= 3.0:
            score_dy = 50
        else:
            score_dy = 30
        # Peso do DY aumenta se o portfólio foca em dividendos
        peso_dy = 0.40 if estilo == "longo" else 0.30
        scores.append(score_dy)
        pesos.append(peso_dy)

    if not scores:
        return 50.0  # Posição neutra quando dados indisponíveis

    # Normalizar pesos
    soma_pesos = sum(pesos)
    score_final = sum(s * (p / soma_pesos) for s, p in zip(scores, pesos))
    return round(max(0, min(100, score_final)), 2)


def calcular_score_perfil(persona: dict, portfolio: dict, indicadores: dict, fundamentos: dict = None) -> float:
    """Mede o alinhamento entre o ativo e o perfil do investidor."""
    tolerancia = persona.get("tolerancia_risco", 5)
    estilo = persona.get("estilo", "dividendos")
    prazo = portfolio.get("objetivo_prazo", "longo")
    tendencia = indicadores.get("tendencia", "neutra")

    score = 50  # Base neutra

    # --- Tendência vs tolerância ---
    if tendencia == "alta":
        score += 15
    elif tendencia == "baixa":
        if tolerancia >= 7:
            score += 5   # Arrojado vê oportunidade na queda
        else:
            score -= 15  # Conservador prefere estabilidade

    # --- RSI vs estilo ---
    rsi = indicadores.get("rsi", 50)
    if estilo == "dividendos":
        if 40 <= rsi <= 60:
            score += 15   # Estável é bom para renda passiva
    else:  # crescimento
        if 50 <= rsi <= 70:
            score += 15   # Momento positivo

    # --- Prazo ---
    if prazo == "longo":
        score += 10  # Longo prazo tolera mais volatilidade
    elif prazo == "curto":
        if tendencia == "baixa":
            score -= 10

    # --- Tolerância ao risco ---
    score += (tolerancia - 5) * 2

    # --- DY vs objetivo de dividendos ---
    if fundamentos:
        dy = fundamentos.get("dy")
        meta_dy = portfolio.get("meta_dividendos", 6.0)
        if dy is not None and dy > 0:
            if dy >= meta_dy:
                score += 10
            elif dy < meta_dy * 0.5:
                score -= 5

    return round(max(0, min(100, score)), 2)


def pontuar_ativo(ticker: str, persona: dict, portfolio: dict, pm_atual: float = 0.0, usar_preco_futuro: bool = False) -> dict:
    """
    Calcula a pontuação de um ativo (0–100) sem usar IA.
    Score = (Técnico * 0.35) + (Fundamentalista * 0.35) + (Perfil * 0.30)
    Se usar_preco_futuro for True, ajusta o score baseado no preço alvo e margem de ganho.
    """
    historico = buscar_historico(ticker, "6mo")
    if historico is None or historico.empty:
        return {"sucesso": False, "erro": "Dados históricos indisponíveis", "ticker": ticker}

    indicadores = calcular_indicadores_tecnicos(historico)
    fundamentos = buscar_dados_fundamentalistas(ticker)

    score_tecnico = calcular_score_tecnico(indicadores)
    score_fundament = calcular_score_fundamentalista(fundamentos, portfolio)
    score_perfil = calcular_score_perfil(persona, portfolio, indicadores, fundamentos)

    score_final = (score_tecnico * 0.35) + (score_fundament * 0.35) + (score_perfil * 0.30)

    # --- Lógica de Preço Futuro ---
    texto_futuro = ""
    if usar_preco_futuro:
        preco_atual = indicadores.get("preco_atual", 0)
        preco_alvo = fundamentos.get("preco_alvo_medio") or fundamentos.get("preco_alvo_max")
        freq = persona.get("frequencia_acao", "semanal")

        if preco_atual > 0 and preco_alvo and preco_alvo > 0:
            upside = ((preco_alvo - preco_atual) / preco_atual) * 100
            
            # Threshold de venda adaptável conforme a frequência de giro da carteira
            # day traders aceitam sair um pouco antes do alvo; buy and hold espera até passar do alvo.
            threshold_venda = 0.0
            if freq == "diario": threshold_venda = 2.0
            elif freq == "semanal": threshold_venda = 0.0
            else: threshold_venda = -5.0

            if pm_atual > 0:
                lucro_pct = ((preco_atual - pm_atual) / pm_atual) * 100
                if upside <= threshold_venda and lucro_pct > 0:
                    # Atingiu o alvo e está com lucro -> força VENDA (reduz drastically o score)
                    score_final = min(score_final, 35.0)
                    texto_futuro = f" O preço (R$ {preco_atual:.2f}) atingiu a região do preço-alvo médio (R$ {preco_alvo:.2f}) com lucro de {lucro_pct:.1f}%. Pela sua frequência de revisão ({freq}), sugere-se realizar lucro."
                elif upside > 15.0 and lucro_pct < -5.0:
                    # Caiu, mas o alvo continua indicando alta forte -> força COMPRA para baixar PM
                    score_final = max(score_final, 75.0)
                    texto_futuro = f" O ativo caiu e está com prejuízo de {abs(lucro_pct):.1f}%, mas o preço-alvo (R$ {preco_alvo:.2f}) indica potencial de {upside:.1f}%. Oportunidade para reduzir seu preço médio."
            else:
                if upside > 20.0:
                    score_final = max(score_final, 75.0)
                    texto_futuro = f" O preço-alvo (R$ {preco_alvo:.2f}) indica um excelente potencial de alta de {upside:.1f}% frente à cotação atual."
                elif upside <= 5.0:
                    score_final = min(score_final, 45.0)
                    texto_futuro = f" Cotação (R$ {preco_atual:.2f}) muito próxima ao preço-alvo (R$ {preco_alvo:.2f}). Margem de segurança baixa para novas compras."

    score_final = round(score_final, 2)

    # Mesclar fundamentos nos indicadores para exibição
    indicadores_completos = {**indicadores, **fundamentos}
    indicadores_completos["texto_futuro"] = texto_futuro

    return {
        "sucesso": True,
        "ticker": ticker,
        "score": score_final,
        "score_tecnico": score_tecnico,
        "score_fundamentalista": score_fundament,
        "score_perfil": score_perfil,
        "indicadores": indicadores_completos,
    }


def gerar_texto_resumo(ticker: str, indicadores: dict, score: float) -> str:
    """Gera um texto breve explicativo sobre o score e indicadores sem usar IA."""
    tendencia = indicadores.get("tendencia", "neutra")
    rsi = indicadores.get("rsi", 50)
    pl = indicadores.get("pl")
    pvp = indicadores.get("pvp")
    dy = indicadores.get("dy")
    volume_ratio = indicadores.get("volume_ratio", 1.0)

    texto = f"O ativo **{ticker}** possui um **Score de {score:.1f}/100** "
    texto += "*(nota de 0 a 100 que avalia o momento de mercado, fundamentos e alinhamento ao seu perfil)*. "

    # Tendência
    if tendencia == "alta":
        texto += "O gráfico indica **Tendência de ALTA** no curto prazo "
        texto += "*(preço acima da média dos últimos 20 dias, com MACD confirmando)*. "
    elif tendencia == "baixa":
        texto += "O gráfico indica **Tendência de BAIXA** no curto prazo "
        texto += "*(preço inferior à média de 20 dias)*. "
    else:
        texto += "Encontra-se sem tendência clara no momento. "

    # RSI
    if rsi < LIMITES["rsi_sobrevendido"]:
        texto += f"O **RSI ({rsi:.0f})** aponta **SOBREVENDIDO** "
        texto += "*(o mercado vendeu muito, pode ser oportunidade de compra)*. "
    elif rsi > LIMITES["rsi_sobrecomprado"]:
        texto += f"O **RSI ({rsi:.0f})** aponta **SOBRECOMPRADO** "
        texto += "*(o mercado comprou rápido demais, risco de correção)*. "
    else:
        texto += f'O **RSI ({rsi:.0f})** está em patamar **Neutro** *(sem pressão excessiva de compra ou venda)*. '

    # P/L
    if pl is not None and pl > 0:
        if pl < LIMITES["pl_barato"]:
            texto += f"O **P/L ({pl:.1f})** indica que o ativo está **barato** em relação ao lucro que gera. "
        elif pl > LIMITES["pl_caro"]:
            texto += f"O **P/L ({pl:.1f})** indica um preço **elevado** em relação ao lucro. "
        else:
            texto += f"O **P/L ({pl:.1f})** está em faixa **razoável**. "

    # P/VP
    if pvp is not None and pvp > 0:
        if pvp < LIMITES["pvp_barato"]:
            texto += f"O **P/VP ({pvp:.2f})** mostra que o ativo negocia **abaixo do patrimônio** — potencial de valor. "
        elif pvp > LIMITES["pvp_caro"]:
            texto += f"O **P/VP ({pvp:.2f})** está **acima do patrimônio** — o mercado paga um prêmio alto. "
        else:
            texto += f"O **P/VP ({pvp:.2f})** está em faixa normal. "

    # Dividend Yield
    if dy is not None and dy > 0:
        if dy >= LIMITES["dy_otimo"]:
            texto += f"Distribui excelentes dividendos (**DY {dy:.2f}%** ao ano). "
        elif dy >= LIMITES["dy_bom"]:
            texto += f"Paga bons dividendos (**DY {dy:.2f}%** ao ano). "
        else:
            texto += f"Paga dividendos modestos (**DY {dy:.2f}%** ao ano). "

    # Volume
    if volume_ratio > LIMITES["volume_alto"]:
        texto += "O **volume** está acima da média, confirmando o movimento atual. "

    # Conclusão
    if score >= 70:
        texto += "**Conclusão:** Excelente alinhamento com a sua carteira e momento favorável."
    elif score >= 50:
        texto += "**Conclusão:** Momento neutro — acompanhe os próximos movimentos."
    elif score <= 40:
        texto += "**Conclusão:** Momento desfavorável ou baixo alinhamento com o perfil da carteira."

    texto_futuro = indicadores.get("texto_futuro", "")
    if texto_futuro:
        texto += f"\n\n**Análise de Preço Futuro:**{texto_futuro}"

    return texto


# Tickers populares organizados por setor (para sugestão de novos ativos)
TICKERS_POR_SETOR = {
    "bancos": ["ITUB4", "BBAS3", "BBDC4", "ITSA4", "B3SA3", "BBSE3"],
    "energia": ["TAEE11", "ELET3", "CPLE6", "EQTL3", "ENGI11", "SBSP3"],
    "mineracao": ["VALE3", "CMIN3", "CSNA3", "GGBR4"],
    "petroleo": ["PETR4", "PETR3", "PRIO3"],
    "varejo": ["MGLU3", "LREN3", "VIIA3"],
    "tecnologia": ["TOTS3", "LWSA3", "POSI3"],
    "saude": ["HAPV3", "RDOR3", "FLRY3"],
    "construcao": ["MRV3", "CYRE3", "EZTC3"],
    "saneamento": ["SBSP3", "SAPR11"],
    "seguros": ["BBSE3", "IRBR3", "PSSA3"],
    # FIIs
    "logistica": ["HGLG11", "XPLG11", "BTLG11", "VILG11"],
    "shoppings": ["XPML11", "VISC11", "HGBS11"],
    "recebiveis": ["KNCR11", "HGCR11", "IRDM11", "MXRF11"],
    "lajes": ["PVBI11", "KNRI11"],
    "fof": ["BCFF11"],
    # Genéricos
    "acoes": ["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3", "ABEV3", "EMBR3", "SUZB3"],
    "fiis": ["MXRF11", "HGLG11", "XPML11", "KNCR11", "KNRI11", "BTLG11", "VISC11"],
}


def gerar_sugestoes_carteira(portfolio_id: int, usar_preco_futuro: bool = False) -> list[dict]:
    """
    Gera sugestões de movimento usando scoring completo (técnico + fundamentalista + perfil).
    Inclui tanto ativos já possuídos quanto novos ativos relevantes para o perfil.
    """
    portfolio = buscar_portfolio_por_id(portfolio_id)
    if not portfolio: return []
    persona = buscar_persona_por_id(portfolio["persona_id"])
    if not persona: return []

    ativos = listar_ativos_portfolio(portfolio_id)
    tickers_possuidos = {a["ticker"].upper() for a in ativos}
    sugestoes = []

    # --- 1) Analisar ativos já possuídos ---
    for ativo in ativos:
        resultado = pontuar_ativo(ativo["ticker"], persona, portfolio, pm_atual=ativo["preco_medio"], usar_preco_futuro=usar_preco_futuro)
        if resultado.get("sucesso"):
            score = resultado["score"]
            if score >= 75:
                acao_sugerida = "compra"
            elif score >= 60:
                acao_sugerida = "observar"
            elif score <= 40:
                acao_sugerida = "venda"
            else:
                acao_sugerida = "manter"

            texto = gerar_texto_resumo(ativo["ticker"], resultado["indicadores"], score)
            
            if acao_sugerida == "observar":
                texto = texto.replace("Momento neutro — acompanhe os próximos movimentos.", "Ativo forte e pontuação alta, mas **aguarde melhor ponto de entrada**.")
                texto = texto.replace("Excelente alinhamento com a sua carteira e momento favorável.", "Excelente alinhamento, mas **aguarde melhor ponto de entrada** devido à saturação do preço atual.")

            sugestoes.append({
                "ticker": ativo["ticker"],
                "score": score,
                "score_tecnico": resultado.get("score_tecnico", 0),
                "score_fundamentalista": resultado.get("score_fundamentalista", 0),
                "score_perfil": resultado.get("score_perfil", 0),
                "acao": acao_sugerida,
                "texto": texto,
                "preco_atual": resultado["indicadores"].get("preco_atual", 0),
                "indicadores": resultado["indicadores"],
                "novo": False
            })

    # --- 2) Sugerir ativos NOVOS baseados nos setores da carteira ---
    setores_pref = portfolio.get("setores_preferidos", "") or ""
    tipo_ativo = portfolio.get("tipo_ativo", "acoes")
    
    tickers_candidatos = set()
    
    if setores_pref:
        for setor in setores_pref.split(","):
            setor = setor.strip().lower()
            if setor in TICKERS_POR_SETOR:
                tickers_candidatos.update(TICKERS_POR_SETOR[setor])
    
    # Se não há setores preferidos, usar os genéricos do tipo de ativo
    if not tickers_candidatos:
        tickers_candidatos.update(TICKERS_POR_SETOR.get(tipo_ativo, []))
    
    # Remover ativos já possuídos
    tickers_novos = tickers_candidatos - tickers_possuidos
    
    # Limitar a 5 para não fazer muitas chamadas de API
    for ticker in list(tickers_novos)[:5]:
        resultado = pontuar_ativo(ticker, persona, portfolio, usar_preco_futuro=usar_preco_futuro)
        if resultado.get("sucesso") and resultado["score"] >= 50:
            texto = gerar_texto_resumo(ticker, resultado["indicadores"], resultado["score"])
            sugestoes.append({
                "ticker": ticker,
                "score": resultado["score"],
                "score_tecnico": resultado.get("score_tecnico", 0),
                "score_fundamentalista": resultado.get("score_fundamentalista", 0),
                "score_perfil": resultado.get("score_perfil", 0),
                "acao": "compra",
                "texto": texto,
                "preco_atual": resultado["indicadores"].get("preco_atual", 0),
                "indicadores": resultado["indicadores"],
                "novo": True
            })

    # sort by score desc
    sugestoes.sort(key=lambda x: x["score"], reverse=True)
    return sugestoes
