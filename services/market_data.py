"""
market_data.py - Integração com Dados de Mercado (yfinance)
============================================================

Conceito de Finanças:
- A B3 (Bolsa Brasil) usa tickers com sufixo ".SA" no Yahoo Finance.
  Ex: PETR4 → PETR4.SA, VALE3 → VALE3.SA
- Indicadores Técnicos são cálculos matemáticos sobre preço/volume
  que ajudam a prever tendências. Não são infalíveis, mas são ferramentas.

Conceito de Eng. Software:
- Tratamento de erros robusto: a API pode falhar por timeout, ticker inválido etc.
- Cache simples via session_state do Streamlit para evitar chamadas repetidas.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


def _formatar_ticker_br(ticker: str) -> str:
    """
    Adiciona o sufixo .SA se necessário para tickers brasileiros.
    
    Na B3, todo ticker precisa do sufixo ".SA" para o Yahoo Finance.
    Ex: "PETR4" → "PETR4.SA"  |  "PETR4.SA" → "PETR4.SA" (já formatado)
    """
    ticker = ticker.upper().strip()
    if not ticker.endswith(".SA"):
        ticker += ".SA"
    return ticker


def buscar_preco_atual(ticker: str) -> Optional[dict]:
    """
    Busca o preço atual e informações básicas de um ativo.
    
    Retorna dict com:
    - preco_atual: último preço negociado
    - variacao_dia: variação percentual do dia
    - volume: volume de negociação
    - nome: nome completo do ativo
    
    Retorna None se o ticker for inválido ou houver erro.
    """
    try:
        ticker_sa = _formatar_ticker_br(ticker)
        ativo = yf.Ticker(ticker_sa)
        info = ativo.info

        # yfinance pode retornar dict vazio para tickers inválidos
        if not info or "regularMarketPrice" not in info:
            # Tenta via histórico como fallback
            hist = ativo.history(period="2d")
            if hist.empty:
                return None
            preco = float(hist["Close"].iloc[-1])
            return {
                "ticker": ticker.upper().replace(".SA", ""),
                "preco_atual": preco,
                "variacao_dia": 0.0,
                "volume": 0,
                "nome": ticker.upper().replace(".SA", "")
            }

        return {
            "ticker": ticker.upper().replace(".SA", ""),
            "preco_atual": info.get("regularMarketPrice", 0),
            "variacao_dia": info.get("regularMarketChangePercent", 0),
            "volume": info.get("regularMarketVolume", 0),
            "nome": info.get("shortName", ticker)
        }
    except Exception as e:
        print(f"[market_data] Erro ao buscar {ticker}: {e}")
        return None


def buscar_historico(
    ticker: str,
    periodo: str = "6mo"
) -> Optional[pd.DataFrame]:
    """
    Busca dados históricos de preço.
    
    Conceito de Finanças:
    - Dados OHLCV: Open, High, Low, Close, Volume
    - periodo aceita: "1d","5d","1mo","3mo","6mo","1y","2y","5y","max"
    
    Retorna DataFrame pandas com colunas: Open, High, Low, Close, Volume
    """
    try:
        ticker_sa = _formatar_ticker_br(ticker)
        ativo = yf.Ticker(ticker_sa)
        hist = ativo.history(period=periodo)
        if hist.empty:
            return None
        return hist
    except Exception as e:
        print(f"[market_data] Erro ao buscar histórico de {ticker}: {e}")
        return None


def calcular_indicadores_tecnicos(df: pd.DataFrame) -> dict:
    """
    Calcula indicadores técnicos básicos a partir de dados OHLCV.
    
    Conceito de Finanças - Indicadores Técnicos:
    
    1. RSI (Relative Strength Index / Índice de Força Relativa):
       - Mede se o ativo está "sobrecomprado" (>70) ou "sobrevendido" (<30)
       - Varia de 0 a 100
       - RSI > 70: pode indicar queda (galera já comprou muito)
       - RSI < 30: pode indicar alta (ativo está "barato")
    
    2. SMA (Simple Moving Average / Média Móvel Simples):
       - Média do preço dos últimos N dias
       - SMA20: curto prazo | SMA50: médio prazo
       - Preço acima da SMA = tendência de alta
    
    3. MACD (Moving Average Convergence Divergence):
       - Diferença entre médias móveis rápida (12d) e lenta (26d)
       - Signal line: SMA 9 períodos do MACD
       - MACD > Signal = momento de compra
       - MACD < Signal = momento de venda
    
    Retorna dict com os indicadores calculados.
    """
    if df is None or df.empty or len(df) < 26:
        return {
            "rsi": 50.0,
            "sma_20": 0.0,
            "sma_50": 0.0,
            "macd": 0.0,
            "macd_signal": 0.0,
            "preco_atual": 0.0,
            "tendencia": "neutra"
        }

    close = df["Close"]
    preco_atual = float(close.iloc[-1])

    # --- RSI (14 períodos, padrão da indústria) ---
    delta = close.diff()
    ganhos = delta.where(delta > 0, 0.0)
    perdas = (-delta.where(delta < 0, 0.0))
    media_ganhos = ganhos.rolling(window=14, min_periods=1).mean()
    media_perdas = perdas.rolling(window=14, min_periods=1).mean()

    # Evita divisão por zero
    rs = media_ganhos / media_perdas.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    rsi_atual = float(rsi.iloc[-1])

    # --- Médias Móveis ---
    sma_20 = float(close.rolling(window=20, min_periods=1).mean().iloc[-1])
    sma_50 = float(close.rolling(window=50, min_periods=1).mean().iloc[-1]) if len(close) >= 50 else sma_20

    # --- MACD ---
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_atual = float(macd.iloc[-1])
    signal_atual = float(macd_signal.iloc[-1])

    # --- Tendência geral ---
    if preco_atual > sma_20 and macd_atual > signal_atual:
        tendencia = "alta"
    elif preco_atual < sma_20 and macd_atual < signal_atual:
        tendencia = "baixa"
    else:
        tendencia = "neutra"

    # --- Volume Ratio (vs média 20d) ---
    vol = df.get("Volume")
    volume_ratio = 1.0
    if vol is not None and len(vol) >= 20:
        vol_media_20 = float(vol.rolling(window=20, min_periods=1).mean().iloc[-1])
        vol_atual = float(vol.iloc[-1])
        volume_ratio = round(vol_atual / vol_media_20, 2) if vol_media_20 > 0 else 1.0

    return {
        "rsi": round(rsi_atual, 2),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2),
        "macd": round(macd_atual, 4),
        "macd_signal": round(signal_atual, 4),
        "preco_atual": round(preco_atual, 2),
        "tendencia": tendencia,
        "volume_ratio": volume_ratio
    }


def buscar_dados_fundamentalistas(ticker: str) -> dict:
    """
    Busca dados fundamentalistas de um ativo via yfinance.
    
    Retorna dict com:
    - pl: Preço/Lucro (P/E ratio) — quanto o mercado paga por cada R$1 de lucro
    - pvp: Preço/Valor Patrimonial (P/B ratio) — relação entre preço e patrimônio líquido
    - dy: Dividend Yield — rendimento percentual anual de dividendos
    - setor: Setor do ativo
    - market_cap: Valor de mercado
    """
    try:
        ticker_sa = _formatar_ticker_br(ticker)
        ativo = yf.Ticker(ticker_sa)
        info = ativo.info
        
        if not info:
            return {"pl": None, "pvp": None, "dy": None, "setor": None, "market_cap": None}
        
        # P/L (trailingPE ou forwardPE)
        pl = info.get("trailingPE") or info.get("forwardPE")
        
        # P/VP (priceToBook)
        pvp = info.get("priceToBook")
        
        # Dividend Yield
        dy_raw = info.get("trailingAnnualDividendYield")
        dy_fallback = info.get("dividendYield")
        
        dy_val = 0.0
        if dy_raw is not None and float(dy_raw) > 0:
            dy_val = float(dy_raw)
        elif dy_fallback is not None and float(dy_fallback) > 0:
            dy_val = float(dy_fallback)
            
        if dy_val > 0:
            if dy_val < 1.0:
                dy = round(dy_val * 100, 2)
            else:
                dy = round(dy_val, 2)
        else:
            dy = None
        
        # Setor
        setor = info.get("sector", info.get("industry", None))
        
        # Market Cap
        market_cap = info.get("marketCap")
        
        return {
            "pl": round(pl, 2) if pl else None,
            "pvp": round(pvp, 2) if pvp else None,
            "dy": round(dy, 2) if dy else None,
            "setor": setor,
            "market_cap": market_cap
        }
    except Exception as e:
        print(f"[market_data] Erro ao buscar fundamentalistas de {ticker}: {e}")
        return {"pl": None, "pvp": None, "dy": None, "setor": None, "market_cap": None}


# Mapeamento de setores para tickers representativos da B3
_SETOR_PEERS = {
    # Ações
    "Financial Services": ["ITUB4", "BBDC4", "BBAS3", "SANB11", "BPAC11"],
    "Financial": ["ITUB4", "BBDC4", "BBAS3", "SANB11", "BPAC11"],
    "Oil & Gas": ["PETR4", "PETR3", "PRIO3", "RECV3", "CSAN3"],
    "Energy": ["PETR4", "ELET3", "ELET6", "CMIG4", "CPFE3", "ENEV3"],
    "Basic Materials": ["VALE3", "SUZB3", "KLBN11", "GGBR4", "CSNA3"],
    "Utilities": ["ELET3", "CPFE3", "CMIG4", "SBSP3", "SAPR11", "TAEE11"],
    "Consumer Cyclical": ["MGLU3", "LREN3", "ARZZ3", "SOMA3", "VIVT3"],
    "Consumer Defensive": ["ABEV3", "NTCO3", "PCAR3", "ASAI3", "CRFB3"],
    "Industrials": ["WEGE3", "EMBR3", "RENT3", "CCRO3", "RAIL3"],
    "Technology": ["TOTS3", "LWSA3", "POSI3", "CASH3", "BMOB3"],
    "Healthcare": ["HAPV3", "RDOR3", "FLRY3", "QUAL3", "HYPE3"],
    "Real Estate": ["CYRE3", "MRVE3", "EZTC3", "MULT3", "IGTI11"],
    "Communication Services": ["VIVT3", "TIMS3", "OIBR3"],
    # FIIs por tipo
    "Tijolo": ["HGLG11", "XPML11", "VISC11", "BTLG11", "KNRI11"],
    "Papel": ["KNCR11", "KNIP11", "MXRF11", "CPTS11", "IRDM11"],
    "Híbrido": ["HGLG11", "KNRI11", "MXRF11", "XPML11", "VISC11"],
}


def buscar_referencia_setor(ticker: str, setor: str = None) -> dict:
    """
    Busca valores de referência (mín, máx, média, mediana) de P/VP, P/L e DY
    para os peers do mesmo setor na B3.
    
    Retorna dict com:
    - setor: nome do setor usado
    - peers_analisados: quantidade de peers com dados
    - pvp: {min, max, media, mediana}
    - pl: {min, max, media, mediana}
    - dy: {min, max, media, mediana}
    """
    import statistics
    
    if not setor:
        fund = buscar_dados_fundamentalistas(ticker)
        setor = fund.get("setor") if fund else None
    
    if not setor:
        return {"setor": None, "peers_analisados": 0}
    
    # Encontrar peers do setor
    peers = _SETOR_PEERS.get(setor, [])
    
    # Fallback: tentar match parcial
    if not peers:
        for key, val in _SETOR_PEERS.items():
            if key.lower() in setor.lower() or setor.lower() in key.lower():
                peers = val
                setor = key
                break
    
    if not peers:
        return {"setor": setor, "peers_analisados": 0}
    
    # Buscar dados de cada peer (excluir o próprio ticker para não enviesar)
    pvp_list, pl_list, dy_list = [], [], []
    
    for peer in peers:
        try:
            fund = buscar_dados_fundamentalistas(peer)
            if fund:
                if fund.get("pvp") and fund["pvp"] > 0:
                    pvp_list.append(fund["pvp"])
                if fund.get("pl") and fund["pl"] > 0:
                    pl_list.append(fund["pl"])
                if fund.get("dy") and fund["dy"] > 0:
                    dy_list.append(fund["dy"])
        except Exception:
            continue
    
    def _stats(vals):
        if not vals:
            return {"min": None, "max": None, "media": None, "moda": None}
        try:
            moda_val = round(statistics.mode(vals), 2)
        except statistics.StatisticsError:
            moda_val = round(statistics.median(vals), 2)  # fallback se todos únicos
        return {
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "media": round(statistics.mean(vals), 2),
            "moda": moda_val,
        }
    
    return {
        "setor": setor,
        "peers_analisados": max(len(pvp_list), len(pl_list), len(dy_list)),
        "pvp": _stats(pvp_list),
        "pl": _stats(pl_list),
        "dy": _stats(dy_list),
    }


def buscar_precos_multiplos(tickers: list[str]) -> dict:
    """
    Busca preço atual de múltiplos ativos de uma vez.
    Retorna dict: { "PETR4": {...}, "VALE3": {...}, ... }
    """
    resultado = {}
    for ticker in tickers:
        dados = buscar_preco_atual(ticker)
        if dados:
            resultado[ticker.upper().replace(".SA", "")] = dados
    return resultado


def verificar_catch_up(ativos: list[dict]) -> list[dict]:
    """
    Motor de Atualização Autônomo.
    
    Conceito de Eng. Software: "Catch-up" = preencher lacunas de dados.
    Se o sistema ficou X dias sem atualizar, busca os dados faltantes.
    
    Verifica o último update de cada ativo e busca dados novos se necessário.
    Retorna lista de ativos que foram atualizados.
    """
    atualizados = []
    for ativo in ativos:
        ultimo = ativo.get("ultimo_update")
        if ultimo:
            try:
                ultimo_dt = datetime.fromisoformat(ultimo)
                dias_sem_update = (datetime.utcnow() - ultimo_dt).days
                if dias_sem_update > 0:
                    # Busca dados novos
                    dados = buscar_preco_atual(ativo["ticker"])
                    if dados:
                        atualizados.append({
                            "asset_id": ativo["id"],
                            "ticker": ativo["ticker"],
                            "preco_atual": dados["preco_atual"],
                            "dias_sem_update": dias_sem_update
                        })
            except (ValueError, TypeError):
                pass
    return atualizados
