"""
market_highlights.py - Destaques do Mercado B3
===============================================

Busca dados de ações populares da B3 via yfinance e retorna rankings:
- Maiores altas do dia
- Maiores quedas do dia
- Melhores dividend yields
- Menor P/L (mais "baratas" em relação ao lucro)

Usa cache de 5 minutos para não sobrecarregar a API.
"""

import yfinance as yf
import streamlit as st
from typing import Optional


# Tickers populares da B3 para monitoramento
TICKERS_POPULARES = [
    # Ações - Blue Chips
    "PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "WEGE3",
    "ABEV3", "B3SA3", "RENT3", "SUZB3", "JBSS3", "GGBR4",
    "CSNA3", "MGLU3", "LREN3", "RADL3", "HAPV3", "TOTS3",
    "ENEV3", "PRIO3", "CPLE6", "TAEE11", "ELET3", "VIVT3",
    # FIIs populares
    "HGLG11", "XPLG11", "MXRF11", "KNRI11", "VISC11"
]


@st.cache_data(ttl=300, show_spinner=False)
def buscar_highlights_mercado() -> Optional[dict]:
    """
    Busca dados de mercado para tickers populares e retorna rankings.
    Cache de 5 minutos para performance.
    
    Retorna dict com 4 listas rankeadas (top 5 cada):
    - maiores_altas: maiores variações positivas do dia
    - maiores_quedas: maiores variações negativas do dia
    - melhores_dy: maiores dividend yields
    - menor_pl: menor P/L (price-to-earnings)
    """
    try:
        # Buscar dados de todos os tickers de uma vez
        tickers_sa = " ".join(f"{t}.SA" for t in TICKERS_POPULARES)
        dados = yf.Tickers(tickers_sa)
        
        resultados = []
        
        for ticker in TICKERS_POPULARES:
            try:
                ticker_sa = f"{ticker}.SA"
                info = dados.tickers[ticker_sa].info
                
                if not info:
                    continue
                
                preco = info.get("regularMarketPrice") or info.get("currentPrice", 0)
                if not preco or preco == 0:
                    continue
                
                variacao = info.get("regularMarketChangePercent", 0) or 0
                dy = info.get("dividendYield", 0) or 0
                pl = info.get("trailingPE") or info.get("forwardPE")
                nome = info.get("shortName", ticker)
                
                resultados.append({
                    "ticker": ticker,
                    "nome": nome[:25] if nome else ticker,
                    "preco": preco,
                    "variacao": round(variacao, 2),
                    "dy": round(dy * 100, 2) if dy and dy < 1 else round(dy, 2) if dy else 0,
                    "pl": round(pl, 2) if pl and pl > 0 else None
                })
            except Exception:
                continue
        
        if not resultados:
            return None
        
        # Ranquear
        maiores_altas = sorted(
            resultados, key=lambda x: x["variacao"], reverse=True
        )[:5]
        
        maiores_quedas = sorted(
            resultados, key=lambda x: x["variacao"]
        )[:5]
        
        # Apenas os que têm DY > 0
        com_dy = [r for r in resultados if r["dy"] and r["dy"] > 0]
        melhores_dy = sorted(com_dy, key=lambda x: x["dy"], reverse=True)[:5]
        
        # Apenas os que têm P/L positivo
        com_pl = [r for r in resultados if r["pl"] and r["pl"] > 0]
        menor_pl = sorted(com_pl, key=lambda x: x["pl"])[:5]
        
        return {
            "maiores_altas": maiores_altas,
            "maiores_quedas": maiores_quedas,
            "melhores_dy": melhores_dy,
            "menor_pl": menor_pl,
            "total_analisados": len(resultados)
        }
    except Exception as e:
        print(f"[market_highlights] Erro ao buscar highlights: {e}")
        return None
