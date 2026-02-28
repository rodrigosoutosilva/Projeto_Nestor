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
from services.scoring import calcular_score_tecnico, calcular_score_perfil
from database.crud import (
    criar_acao_planejada,
    listar_ativos_portfolio,
    buscar_persona_por_id,
    buscar_portfolio_por_id
)


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
    
    # Sentimento retorna dicionário com "score" float entre -1.0 e 1.0
    # Normalizamos esse valor para escala 0 a 100
    val_sentimento = sentimento.get("score", 0.0)
    score_sentimento = (val_sentimento + 1.0) * 50
    
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
