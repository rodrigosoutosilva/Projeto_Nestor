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
    ticker_clean = ticker.upper().strip().replace(".SA", "")
    try:
        ticker_sa = _formatar_ticker_br(ticker)
        ativo = yf.Ticker(ticker_sa)

        # Tentativa 1: fast_info (mais rápido e confiável em versões recentes)
        try:
            fi = ativo.fast_info
            preco = fi.get("lastPrice", 0) or fi.get("last_price", 0)
            if not preco:
                preco = fi.get("regularMarketPrice", 0)
            if preco and preco > 0:
                return {
                    "ticker": ticker_clean,
                    "preco_atual": float(preco),
                    "variacao_dia": 0.0,
                    "volume": int(fi.get("lastVolume", 0) or fi.get("last_volume", 0) or 0),
                    "nome": ticker_clean
                }
        except Exception as e:
            print(f"[market_data] fast_info falhou para {ticker}: {e}")

        # Tentativa 2: info completo
        try:
            info = ativo.info
            if info and "regularMarketPrice" in info and info["regularMarketPrice"]:
                return {
                    "ticker": ticker_clean,
                    "preco_atual": info.get("regularMarketPrice", 0),
                    "variacao_dia": info.get("regularMarketChangePercent", 0),
                    "volume": info.get("regularMarketVolume", 0),
                    "nome": info.get("shortName", ticker_clean)
                }
        except Exception as e:
            print(f"[market_data] info falhou para {ticker}: {e}")

        # Tentativa 3: histórico como último recurso
        try:
            hist = ativo.history(period="5d")
            if not hist.empty:
                preco = float(hist["Close"].iloc[-1])
                return {
                    "ticker": ticker_clean,
                    "preco_atual": preco,
                    "variacao_dia": 0.0,
                    "volume": int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0,
                    "nome": ticker_clean
                }
        except Exception as e:
            print(f"[market_data] history falhou para {ticker}: {e}")

        print(f"[market_data] Nenhum método funcionou para {ticker}")
        return None
    except Exception as e:
        print(f"[market_data] Erro geral ao buscar {ticker}: {e}")
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
    Busca dados fundamentalistas completos de um ativo via yfinance.
    
    Retorna dict com indicadores de valuation, rentabilidade, endividamento,
    margens, crescimento, dividendos e dados de mercado.
    """
    campos_vazios = {
        "pl": None, "pvp": None, "dy": None, "setor": None, "market_cap": None,
        "roe": None, "roa": None, "divida_pl": None, "liquidez_corrente": None,
        "payout": None, "margem_liquida": None, "margem_operacional": None,
        "margem_bruta": None, "crescimento_receita": None, "crescimento_lucro": None,
        "ebitda": None, "ev_ebitda": None, "fluxo_caixa_livre": None, "beta": None,
        "consenso_analistas": None, "preco_alvo_medio": None, "preco_alvo_min": None,
        "preco_alvo_max": None, "peg_ratio": None, "var_52_semanas": None,
        "dy_medio_5_anos": None, "dividend_rate": None, "industria": None,
        "preco_sobre_vendas": None, "num_analistas": None,
    }
    try:
        ticker_sa = _formatar_ticker_br(ticker)
        ativo = yf.Ticker(ticker_sa)
        info = ativo.info
        
        if not info:
            return campos_vazios
        
        def _safe_float(key, fallback_key=None):
            val = info.get(key)
            if val is None and fallback_key:
                val = info.get(fallback_key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
            return None

        def _safe_pct(key, fallback_key=None):
            """Retorna valor como percentual (multiplica por 100 se < 1)."""
            val = _safe_float(key, fallback_key)
            if val is not None:
                return round(val * 100, 2) if abs(val) < 1.0 else round(val, 2)
            return None
        
        # --- Valuation ---
        pl = _safe_float("trailingPE", "forwardPE")
        pvp = _safe_float("priceToBook")
        
        # Dividend Yield
        dy_val = _safe_float("dividendYield", "trailingAnnualDividendYield")
        if dy_val is not None and dy_val > 0:
            dy = round(dy_val * 100, 2) if dy_val < 1.0 else round(dy_val, 2)
        else:
            dy = None
        
        # Setor e Indústria
        setor = info.get("sector", info.get("industry", None))
        industria = info.get("industry", None)
        
        return {
            # Valuation
            "pl": round(pl, 2) if pl else None,
            "pvp": round(pvp, 2) if pvp else None,
            "dy": round(dy, 2) if dy else None,
            "ev_ebitda": round(_safe_float("enterpriseToEbitda"), 2) if _safe_float("enterpriseToEbitda") else None,
            "peg_ratio": round(_safe_float("trailingPegRatio"), 2) if _safe_float("trailingPegRatio") else None,
            "preco_sobre_vendas": round(_safe_float("priceToSalesTrailing12Months"), 2) if _safe_float("priceToSalesTrailing12Months") else None,
            
            # Rentabilidade
            "roe": _safe_pct("returnOnEquity"),
            "roa": _safe_pct("returnOnAssets"),
            
            # Endividamento e Liquidez
            "divida_pl": round(_safe_float("debtToEquity"), 2) if _safe_float("debtToEquity") else None,
            "liquidez_corrente": round(_safe_float("currentRatio"), 2) if _safe_float("currentRatio") else None,
            
            # Margens
            "margem_liquida": _safe_pct("profitMargins"),
            "margem_operacional": _safe_pct("operatingMargins"),
            "margem_bruta": _safe_pct("grossMargins"),
            
            # Crescimento
            "crescimento_receita": _safe_pct("revenueGrowth"),
            "crescimento_lucro": _safe_pct("earningsGrowth"),
            
            # Dividendos
            "payout": _safe_pct("payoutRatio"),
            "dividend_rate": round(_safe_float("dividendRate"), 2) if _safe_float("dividendRate") else None,
            "dy_medio_5_anos": round(_safe_float("fiveYearAvgDividendYield"), 2) if _safe_float("fiveYearAvgDividendYield") else None,
            
            # Mercado
            "market_cap": info.get("marketCap"),
            "ebitda": info.get("ebitda"),
            "fluxo_caixa_livre": info.get("freeCashflow"),
            "beta": round(_safe_float("beta"), 3) if _safe_float("beta") else None,
            "var_52_semanas": _safe_pct("52WeekChange"),
            
            # Analistas
            "consenso_analistas": info.get("recommendationKey"),
            "preco_alvo_medio": round(_safe_float("targetMeanPrice"), 2) if _safe_float("targetMeanPrice") else None,
            "preco_alvo_min": round(_safe_float("targetLowPrice"), 2) if _safe_float("targetLowPrice") else None,
            "preco_alvo_max": round(_safe_float("targetHighPrice"), 2) if _safe_float("targetHighPrice") else None,
            "num_analistas": info.get("numberOfAnalystOpinions"),
            
            # Setor
            "setor": setor,
            "industria": industria,
        }
    except Exception as e:
        print(f"[market_data] Erro ao buscar fundamentalistas de {ticker}: {e}")
        return campos_vazios


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
    Busca valores de referência (mín, máx, média, mediana) para TODOS os
    indicadores numéricos dos peers do mesmo setor.
    
    Retorna dict com:
    - setor: nome do setor usado
    - peers_analisados: quantidade de peers com dados
    - pl: {min, max, media, moda}
    - roe: {min, max, media, moda}
    ... (para todos os demais indicadores)
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
    
    # Dicionário para armazenar as listas de valores de cada indicador
    import collections
    indicadores_listas = collections.defaultdict(list)
    indicadores_peers = collections.defaultdict(list)
    
    for peer in peers:
        try:
            fund = buscar_dados_fundamentalistas(peer)
            if not fund: continue
            
            for key, val in fund.items():
                if val is not None and isinstance(val, (int, float)):
                    # Lógica de filtragem: evitar distorções graves (ex: PL ou PVP negativos dependendo do critério)
                    if key in ("pl", "pvp") and val <= 0:
                        continue
                    indicadores_listas[key].append(val)
                    indicadores_peers[key].append((val, peer))
        except Exception:
            continue
    
    def _stats(vals, vals_with_peers):
        if not vals:
            return {"min": None, "max": None, "media": None, "moda": None, "min_ativo": None, "max_ativo": None}
        try:
            moda_val = round(statistics.mode(vals), 2)
        except statistics.StatisticsError:
            moda_val = round(statistics.median(vals), 2)  # fallback se todos únicos
            
        min_val = min(vals)
        max_val = max(vals)
        
        min_ativo = next((p for v, p in vals_with_peers if v == min_val), None)
        max_ativo = next((p for v, p in vals_with_peers if v == max_val), None)
            
        return {
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "media": round(statistics.mean(vals), 2),
            "moda": moda_val,
            "min_ativo": min_ativo,
            "max_ativo": max_ativo
        }
    
    # Retorno final
    max_peers_analisados = max([len(v) for v in indicadores_listas.values()] + [0])
    
    resultado = {
        "setor": setor,
        "peers_analisados": max_peers_analisados,
    }
    
    for key, vals in indicadores_listas.items():
        vals_with_peers = indicadores_peers.get(key, [])
        resultado[key] = _stats(vals, vals_with_peers)
        
    return resultado


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
