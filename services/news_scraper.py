"""
news_scraper.py - Scraping de Notícias via Google News RSS
==========================================================

Conceito de Eng. Software:
- RSS (Really Simple Syndication): formato XML para feeds de notícias
- Usamos feedparser para parsear o XML de forma segura
- Google News agrega notícias de múltiplas fontes

Conceito de Finanças:
- Notícias influenciam diretamente o preço de ativos
- Análise de sentimento de notícias é parte da análise fundamentalista moderna
- "Compre no boato, venda no fato" - ditado do mercado
"""

import feedparser
from datetime import datetime
from typing import Optional
from urllib.parse import quote


def buscar_noticias_google(
    query: str,
    max_resultados: int = 10,
    idioma: str = "pt-BR"
) -> list[dict]:
    """
    Busca notícias do Google News RSS por query.
    
    Parâmetros:
    - query: termo de busca (ex: "PETR4 petrobras")
    - max_resultados: máximo de notícias retornadas
    - idioma: filtro de idioma (pt-BR para português)
    
    Retorna lista de dicts com: titulo, link, data, fonte
    """
    try:
        # URL do RSS do Google News com filtro de idioma e região Brasil
        url = (
            f"https://news.google.com/rss/search?"
            f"q={quote(query)}&hl={idioma}&gl=BR&ceid=BR:{idioma[:2]}"
        )

        feed = feedparser.parse(url)

        noticias = []
        for entry in feed.entries[:max_resultados]:
            # Extrair a fonte real (Google News coloca no final do título)
            titulo = entry.get("title", "")
            fonte = ""
            if " - " in titulo:
                partes = titulo.rsplit(" - ", 1)
                titulo = partes[0]
                fonte = partes[1] if len(partes) > 1 else ""

            # Parsear data de publicação
            data_pub = entry.get("published", "")
            try:
                data_formatada = datetime.strptime(
                    data_pub, "%a, %d %b %Y %H:%M:%S %Z"
                ).strftime("%d/%m/%Y %H:%M")
            except (ValueError, TypeError):
                data_formatada = data_pub

            noticias.append({
                "titulo": titulo,
                "link": entry.get("link", ""),
                "data": data_formatada,
                "fonte": fonte,
                "resumo": entry.get("summary", "")
            })

        return noticias

    except Exception as e:
        print(f"[news_scraper] Erro ao buscar notícias para '{query}': {e}")
        return []


def buscar_noticias_ticker(ticker: str, max_resultados: int = 8) -> list[dict]:
    """
    Busca notícias específicas de um ticker/ativo brasileiro.
    
    Estratégia de busca: combina o ticker com termos relacionados
    para melhorar a relevância dos resultados.
    
    Ex: PETR4 → busca "PETR4 Petrobras ação bolsa"
    """
    # Mapeamento de tickers populares para nomes de empresas
    # Isso melhora a busca no Google News
    empresa_map = {
        "PETR4": "Petrobras", "PETR3": "Petrobras",
        "VALE3": "Vale mineração", "ITUB4": "Itaú Unibanco",
        "BBDC4": "Bradesco", "BBAS3": "Banco do Brasil",
        "ABEV3": "Ambev", "WEGE3": "WEG",
        "RENT3": "Localiza", "LREN3": "Lojas Renner",
        "MGLU3": "Magazine Luiza", "SUZB3": "Suzano",
        "JBSS3": "JBS", "GGBR4": "Gerdau",
        "CSNA3": "CSN Siderurgia", "CPLE6": "Copel",
        "TAEE11": "Taesa", "HGLG11": "CSHG Logística",
        "MXRF11": "Maxi Renda", "XPML11": "XP Malls",
        "VISC11": "Vinci Shopping", "KNRI11": "Kinea Renda",
        "HGBS11": "Hedge Brasil Shopping",
    }

    ticker_upper = ticker.upper().replace(".SA", "")
    nome_empresa = empresa_map.get(ticker_upper, "")

    # Query combinada para melhores resultados
    query = f"{ticker_upper} {nome_empresa} ação bolsa mercado".strip()

    return buscar_noticias_google(query, max_resultados)


def formatar_noticias_para_ia(noticias: list[dict]) -> str:
    """
    Formata notícias em texto para enviar ao Gemini para análise.
    
    Conceito de Eng. Software: Preparação de dados (data preprocessing)
    Antes de enviar para a IA, formatamos os dados de forma estruturada
    para que o modelo consiga extrair melhor as informações.
    """
    if not noticias:
        return "Nenhuma notícia recente encontrada para este ativo."

    texto = "NOTÍCIAS RECENTES:\n\n"
    for i, noticia in enumerate(noticias, 1):
        texto += f"{i}. [{noticia['data']}] {noticia['titulo']}"
        if noticia.get("fonte"):
            texto += f" (Fonte: {noticia['fonte']})"
        texto += "\n"

    return texto
