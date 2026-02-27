"""
recommendation.py - Motor de Recomendação e Agendamento
========================================================

Conceito de Eng. Software: Padrão Orchestrator (Orquestrador)
Este módulo orquestra todos os serviços (market_data, news_scraper, ai_brain)
para gerar uma recomendação completa e coerente.

Conceito de Finanças:
Fórmula de Pontuação:
  Score = (Indicadores Técnicos * 0.4) + (Sentimento IA * 0.4) + (Perfil * 0.2)

- Indicadores Técnicos (40%): RSI, MACD, tendência de preço
- Sentimento IA (40%): análise de notícias via Gemini
- Perfil Persona/Carteira (20%): alinhamento com objetivos do investidor
"""

from datetime import date, timedelta
from services.market_data import (
    buscar_historico,
    calcular_indicadores_tecnicos,
    buscar_preco_atual
)
from services.news_scraper import buscar_noticias_ticker, formatar_noticias_para_ia
from services.ai_brain import analisar_sentimento, gerar_recomendacao_ia
from database.crud import (
    criar_acao_planejada,
    listar_ativos_portfolio,
    buscar_persona_por_id,
    buscar_portfolio_por_id
)


def calcular_score_tecnico(indicadores: dict) -> float:
    """
    Normaliza indicadores técnicos para um score de 0 a 100.
    
    Conceito de Finanças:
    - RSI sobrevendido (<30) é POSITIVO para compra → score alto
    - RSI sobrecomprado (>70) é NEGATIVO para compra → score baixo
    - Preço acima da SMA20 = tendência de alta → score alto
    - MACD acima do Signal = momento de compra → score alto
    
    Pesos internos:
    - RSI: 40% (indicador mais confiável individualmente)
    - Tendência SMA: 30%
    - MACD: 30%
    """
    rsi = indicadores.get("rsi", 50)
    preco = indicadores.get("preco_atual", 0)
    sma_20 = indicadores.get("sma_20", preco)
    macd = indicadores.get("macd", 0)
    macd_signal = indicadores.get("macd_signal", 0)

    # --- Score RSI (0 a 100) ---
    # RSI < 30: muito bom para compra (score ~90)
    # RSI = 50: neutro (score ~50)
    # RSI > 70: ruim para compra (score ~10)
    if rsi <= 30:
        score_rsi = 80 + (30 - rsi)  # 80-110, capped at 100
    elif rsi >= 70:
        score_rsi = max(0, 30 - (rsi - 70))  # 0-30
    else:
        score_rsi = 50 + (50 - rsi) * 0.75  # 35-65

    score_rsi = max(0, min(100, score_rsi))

    # --- Score SMA (0 a 100) ---
    # Preço acima da SMA20 = tendência de alta
    if sma_20 > 0:
        desvio = ((preco - sma_20) / sma_20) * 100
        score_sma = 50 + desvio * 5  # Amplifica o desvio
        score_sma = max(0, min(100, score_sma))
    else:
        score_sma = 50

    # --- Score MACD (0 a 100) ---
    # MACD > Signal = momento positivo
    if macd > macd_signal:
        score_macd = 60 + min(40, abs(macd - macd_signal) * 1000)
    else:
        score_macd = 40 - min(40, abs(macd - macd_signal) * 1000)

    score_macd = max(0, min(100, score_macd))

    # Média ponderada
    score_final = (score_rsi * 0.4) + (score_sma * 0.3) + (score_macd * 0.3)

    return round(max(0, min(100, score_final)), 2)


def calcular_score_sentimento(sentimento: dict) -> float:
    """
    Converte o score de sentimento (-1 a 1) para uma escala 0 a 100.
    
    Conceito: Normalização linear simples.
    -1 → 0 (muito negativo)
     0 → 50 (neutro)
    +1 → 100 (muito positivo)
    """
    score = sentimento.get("score", 0)
    # Normaliza de [-1, 1] para [0, 100]
    return round((score + 1) * 50, 2)


def calcular_score_perfil(persona: dict, portfolio: dict, indicadores: dict) -> float:
    """
    Mede o alinhamento entre o ativo e o perfil do investidor.
    
    Conceito de Finanças:
    - Investidor conservador + ativo em queda forte = score baixo (fora do perfil)
    - Investidor arrojado + ativo volátil = score alto (dentro do perfil)
    - Estilo dividendos + FII = score alto
    - Estilo crescimento + ação de crescimento = score alto
    
    Retorna 0 a 100.
    """
    tolerancia = persona.get("tolerancia_risco", 5)
    estilo = persona.get("estilo", "dividendos")
    prazo = portfolio.get("objetivo_prazo", "longo")
    tendencia = indicadores.get("tendencia", "neutra")

    score = 50  # Base neutra

    # --- Alinhamento tendência x tolerância ---
    if tendencia == "alta":
        score += 15  # Ativo subindo é bom para todos
    elif tendencia == "baixa":
        if tolerancia >= 7:
            score += 5  # Arrojado vê oportunidade em quedas
        else:
            score -= 15  # Conservador não gosta de queda

    # --- Alinhamento com estilo ---
    rsi = indicadores.get("rsi", 50)
    if estilo == "dividendos":
        # Dividendos preferem ativos estáveis, RSI perto de 50
        if 40 <= rsi <= 60:
            score += 15
    else:  # crescimento
        # Crescimento gosta de momentum (RSI moderado-alto)
        if 50 <= rsi <= 70:
            score += 15

    # --- Alinhamento com prazo ---
    if prazo == "longo":
        score += 10  # Longo prazo é mais tolerante
    elif prazo == "curto":
        if tendencia == "baixa":
            score -= 10  # Curto prazo não aceita queda

    # --- Bônus por tolerância a risco ---
    # Investidores arrojados recebem score levemente maior
    # (mais dispostos a agir em qualquer cenário)
    score += (tolerancia - 5) * 2

    return round(max(0, min(100, score)), 2)


def gerar_recomendacao_completa(
    ticker: str,
    persona_id: int,
    portfolio_id: int
) -> dict:
    """
    Orquestra TODAS as análises e gera uma recomendação completa.
    
    Conceito de Eng. Software: Facade Pattern
    Este método é a "fachada" que esconde toda a complexidade interna.
    A UI só precisa chamar este método com ticker + IDs.
    
    Fórmula Final:
    Score = (Técnico * 0.4) + (Sentimento * 0.4) + (Perfil * 0.2)
    
    Retorna dict com todos os detalhes da recomendação.
    """
    # 1. Buscar dados da persona e portfolio
    persona = buscar_persona_por_id(persona_id)
    portfolio = buscar_portfolio_por_id(portfolio_id)

    if not persona or not portfolio:
        return {
            "sucesso": False,
            "erro": "Persona ou Portfolio não encontrado",
            "ticker": ticker
        }

    # 2. Buscar dados de mercado e calcular indicadores técnicos
    historico = buscar_historico(ticker, "6mo")
    indicadores = calcular_indicadores_tecnicos(historico)

    # 3. Buscar notícias e analisar sentimento
    noticias = buscar_noticias_ticker(ticker)
    noticias_texto = formatar_noticias_para_ia(noticias)
    sentimento = analisar_sentimento(noticias_texto, ticker)

    # 4. Calcular scores individuais
    score_tecnico = calcular_score_tecnico(indicadores)
    score_sentimento = calcular_score_sentimento(sentimento)
    score_perfil = calcular_score_perfil(persona, portfolio, indicadores)

    # 5. Score final ponderado
    score_final = (
        (score_tecnico * 0.4) +
        (score_sentimento * 0.4) +
        (score_perfil * 0.2)
    )
    score_final = round(score_final, 2)

    # 6. Gerar recomendação detalhada via IA
    recomendacao_ia = gerar_recomendacao_ia(
        ticker=ticker,
        indicadores=indicadores,
        sentimento=sentimento,
        persona_info=persona,
        portfolio_info=portfolio
    )

    # 7. Montar resultado completo
    return {
        "sucesso": True,
        "ticker": ticker,
        "preco_atual": indicadores.get("preco_atual", 0),
        "scores": {
            "tecnico": score_tecnico,
            "sentimento": score_sentimento,
            "perfil": score_perfil,
            "final": score_final
        },
        "indicadores": indicadores,
        "sentimento": sentimento,
        "noticias": noticias[:5],  # Top 5 notícias
        "recomendacao": {
            "acao": recomendacao_ia["acao"],
            "confianca": recomendacao_ia["confianca"],
            "explicacao": recomendacao_ia["explicacao"]
        },
        "persona": persona,
        "portfolio": portfolio
    }


def calcular_proxima_data_acao(frequencia: str, data_referencia: date = None) -> date:
    """
    Calcula a próxima data de ação com base na frequência da persona.
    
    Conceito de Eng. Software: Scheduling (Agendamento)
    A frequência define o intervalo entre revisões da carteira.
    
    Conceito de Finanças:
    - Diário: day traders, operações rápidas
    - Semanal: swing traders, investidores ativos
    - Mensal: buy & hold, investidores passivos
    """
    if data_referencia is None:
        data_referencia = date.today()

    intervalos = {
        "diario": timedelta(days=1),
        "semanal": timedelta(weeks=1),
        "mensal": timedelta(days=30),
    }

    intervalo = intervalos.get(frequencia, timedelta(weeks=1))
    proxima_data = data_referencia + intervalo

    # Se cair no final de semana, avança para segunda
    while proxima_data.weekday() >= 5:  # 5=sab, 6=dom
        proxima_data += timedelta(days=1)

    return proxima_data


def gerar_recomendacoes_portfolio(
    portfolio_id: int,
    persona_id: int
) -> list[dict]:
    """
    Gera recomendações para TODOS os ativos de uma carteira.
    Retorna lista de recomendações completas.
    """
    ativos = listar_ativos_portfolio(portfolio_id)
    persona = buscar_persona_por_id(persona_id)

    if not ativos:
        return []

    recomendacoes = []
    for ativo in ativos:
        rec = gerar_recomendacao_completa(
            ticker=ativo["ticker"],
            persona_id=persona_id,
            portfolio_id=portfolio_id
        )
        if rec.get("sucesso"):
            # Calcular data da próxima ação
            frequencia = persona.get("frequencia_acao", "semanal") if persona else "semanal"
            proxima_data = calcular_proxima_data_acao(frequencia)

            # Salvar ação planejada no banco
            acao_salva = criar_acao_planejada(
                portfolio_id=portfolio_id,
                asset_ticker=ativo["ticker"],
                tipo_acao=rec["recomendacao"]["acao"],
                data_planejada=proxima_data,
                pontuacao=rec["scores"]["final"],
                preco_alvo=rec["preco_atual"],
                explicacao=rec["recomendacao"]["explicacao"]
            )

            rec["acao_planejada"] = acao_salva
            rec["proxima_data"] = str(proxima_data)

        recomendacoes.append(rec)

    return recomendacoes
