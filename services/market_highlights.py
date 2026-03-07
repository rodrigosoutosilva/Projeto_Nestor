"""
market_highlights.py - Destaques do Mercado B3
===============================================

Busca dados de ações populares da B3 via yfinance e retorna rankings:
- Maiores altas do dia
- Maiores quedas do dia
- Melhores dividend yields
- Menor P/L (mais "baratas" em relação ao lucro)

Usa cache do Streamlit para evitar chamadas excessivas.
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


@st.cache_data(show_spinner=False, ttl=300)  # cache de 5 min
def buscar_highlights_mercado(_cache_buster: int = 0) -> Optional[dict]:
    """
    Busca dados de mercado para tickers populares e retorna rankings.

    Usa yf.download() para lote (mais confiável que .info),
    e fast_info para dados fundamentalistas individuais.
    """
    try:
        tickers_sa = [f"{t}.SA" for t in TICKERS_POPULARES]

        # --- Busca preços via yf.download() (método mais confiável) ---
        print(f"[market_highlights] Buscando {len(tickers_sa)} tickers via yf.download...")
        df = yf.download(
            tickers_sa,
            period="5d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )

        if df is None or df.empty:
            print("[market_highlights] yf.download retornou vazio")
            return None

        resultados = []

        for ticker in TICKERS_POPULARES:
            try:
                ticker_sa = f"{ticker}.SA"

                # Extrair preço de fechamento dos últimos 2 dias
                try:
                    if len(TICKERS_POPULARES) > 1 and ticker_sa in df.columns.get_level_values(0):
                        close_series = df[ticker_sa]["Close"].dropna()
                    elif "Close" in df.columns:
                        close_series = df["Close"].dropna()
                    else:
                        continue
                except (KeyError, TypeError):
                    continue

                if close_series is None or len(close_series) < 2:
                    continue

                preco = float(close_series.iloc[-1])
                preco_ant = float(close_series.iloc[-2])

                if preco <= 0:
                    continue

                variacao = ((preco - preco_ant) / preco_ant) * 100 if preco_ant > 0 else 0

                # Dados fundamentalistas via fast_info (rápido)
                dy = 0.0
                pl = None
                nome = ticker
                try:
                    fi = yf.Ticker(ticker_sa).fast_info
                    # DY
                    dy_raw = fi.get("trailingAnnualDividendYield", 0) or fi.get("last_annual_dividend_yield", 0) or 0
                    if dy_raw and float(dy_raw) > 0:
                        dy_val = float(dy_raw)
                        dy = round(dy_val * 100, 2) if dy_val < 1.0 else round(dy_val, 2)
                    # P/E (P/L)
                    pe_raw = fi.get("trailingPE", None) or fi.get("trailing_pe", None)
                    if pe_raw and float(pe_raw) > 0:
                        pl = round(float(pe_raw), 2)
                except Exception:
                    pass  # Dados fundamentalistas são opcionais

                # Tipo de ativo
                tipo_ativo = "Ações"
                if ticker in ["HGLG11", "XPLG11", "MXRF11", "KNRI11", "VISC11"]:
                    tipo_ativo = "FIIs"
                elif len(ticker) == 6 and ticker.endswith("11") and ticker not in ["TAEE11", "KLBN11", "ENGI11", "SANB11", "ALUP11"]:
                    tipo_ativo = "FIIs"

                resultados.append({
                    "ticker": ticker,
                    "nome": nome[:25],
                    "tipo": tipo_ativo,
                    "preco": round(preco, 2),
                    "variacao": round(variacao, 2),
                    "dy": dy,
                    "pl": pl
                })
            except Exception as e:
                print(f"[market_highlights] Erro no ticker {ticker}: {e}")
                continue

        print(f"[market_highlights] {len(resultados)}/{len(TICKERS_POPULARES)} tickers processados com sucesso")

        if not resultados:
            return None

        return {
            "todos_ativos": resultados,
            "maiores_altas": sorted(resultados, key=lambda x: x["variacao"], reverse=True)[:5],
            "maiores_quedas": sorted(resultados, key=lambda x: x["variacao"])[:5],
            "melhores_dy": sorted([r for r in resultados if r["dy"] > 0], key=lambda x: x["dy"], reverse=True)[:5],
            "menor_pl": sorted([r for r in resultados if r["pl"] and r["pl"] > 0], key=lambda x: x["pl"])[:5],
            "total_analisados": len(resultados)
        }
    except Exception as e:
        print(f"[market_highlights] Erro geral: {e}")
        return None
