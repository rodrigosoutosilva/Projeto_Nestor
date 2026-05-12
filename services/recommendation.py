"""
recommendation.py - Motor de Recomendação e Agendamento
========================================================

Orquestra todos os serviços (market_data, news_scraper, ai_brain, scoring)
para gerar uma recomendação completa e coerente.
"""

from datetime import date, timedelta
from services.market_data import (
    buscar_historico,
    calcular_indicadores_tecnicos,
    buscar_preco_atual,
    buscar_dados_completos
)
from services.news_scraper import buscar_noticias_ticker, formatar_noticias_para_ia
from services.ai_brain import analisar_sentimento, gerar_recomendacao_ia
from services.scoring import pontuar_ativo
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
    Retorna dict com todos os detalhes da recomendação.
    """
    persona = buscar_persona_por_id(persona_id)
    portfolio = buscar_portfolio_por_id(portfolio_id)

    if not persona or not portfolio:
        return {
            "sucesso": False,
            "erro": "Persona ou Portfolio não encontrado",
            "ticker": ticker
        }

    # Verifica se já está na carteira para usar o PM correto
    ativos_carteira = listar_ativos_portfolio(portfolio_id)
    ativo_ext = next((a for a in ativos_carteira if a["ticker"] == ticker), None)
    pm_atual = ativo_ext["preco_medio"] if ativo_ext else 0.0

    # 1. Obtém pontuação base (que agora já traz os indicadores embutidos)
    score_data = pontuar_ativo(ticker, persona, portfolio, pm_atual=pm_atual)
    indicadores = score_data.get("indicadores", {})
    score_final = score_data.get("score", 50)
    acao_sugerida = score_data.get("acao", "manter")

    # 2. Buscar notícias e analisar sentimento
    noticias = buscar_noticias_ticker(ticker)
    noticias_texto = formatar_noticias_para_ia(noticias)
    sentimento = analisar_sentimento(noticias_texto, ticker)
    val_sentimento = sentimento.get("score", 0.0)
    score_sentimento = (val_sentimento + 1.0) * 50

    # 3. Gerar recomendação detalhada via IA (baseada nos novos fundamentos)
    recomendacao_ia = gerar_recomendacao_ia(
        ticker=ticker,
        indicadores=indicadores,
        sentimento=sentimento,
        persona_info=persona,
        portfolio_info=portfolio
    )

    # Combina as ações. Se o circuito breaker deu VENDA, mantemos VENDA.
    acao_final = recomendacao_ia["acao"]
    if acao_sugerida == "venda":
        acao_final = "venda"
        
    return {
        "sucesso": True,
        "ticker": ticker,
        "preco_atual": indicadores.get("preco_atual", 0),
        "scores": {
            "algoritmo": score_final,
            "sentimento": score_sentimento,
            "final": score_final  # Mantemos o score do algoritmo como principal
        },
        "indicadores": indicadores,
        "sentimento": sentimento,
        "noticias": noticias[:5],  # Top 5 notícias
        "recomendacao": {
            "acao": acao_final,
            "confianca": recomendacao_ia["confianca"],
            "explicacao": recomendacao_ia["explicacao"]
        },
        "persona": persona,
        "portfolio": portfolio
    }

def calcular_proxima_data_acao(frequencia: str, data_referencia: date = None) -> date:
    if data_referencia is None:
        data_referencia = date.today()

    intervalos = {
        "diario": timedelta(days=1),
        "semanal": timedelta(weeks=1),
        "mensal": timedelta(days=30),
    }

    intervalo = intervalos.get(frequencia, timedelta(weeks=1))
    proxima_data = data_referencia + intervalo

    while proxima_data.weekday() >= 5:
        proxima_data += timedelta(days=1)

    return proxima_data

def gerar_recomendacoes_portfolio(
    portfolio_id: int,
    persona_id: int
) -> list[dict]:
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
            frequencia = persona.get("frequencia_acao", "semanal") if persona else "semanal"
            proxima_data = calcular_proxima_data_acao(frequencia)

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
