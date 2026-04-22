"""
7_Estatisticas_Mercado.py - Relatório Estatístico

Agrega dados por setor mostrando Mínimos, Máximos, Médias e Modas (ao invés de Medianas).
"""

import streamlit as st
import pandas as pd
import statistics
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.market_data import buscar_dados_fundamentalistas
from services.scoring import TICKERS_POR_SETOR
from utils.helpers import injetar_css_global

st.set_page_config(page_title="Estatísticas de Mercado", page_icon="▪️", layout="wide")
injetar_css_global()

st.markdown("### Estatísticas de Mercado")
st.markdown("*Acompanhe métricas (Mínimo, Máximo, Média e Moda) agregadas por setor no mercado nacional.*")
st.markdown("---")

def _safe_mode(data_list):
    """Calcula a moda de forma segura; se StatisticsError, retorna a média simples como fallback."""
    if not data_list:
        return 0.0
    try:
        return statistics.mode(data_list)
    except statistics.StatisticsError:
        return sum(data_list) / len(data_list)

@st.cache_data(ttl=3600, show_spinner=False)
def gerar_estatisticas_setoriais():
    dados = []
    
    # Progresso simulado para melhorar UX de scraping
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Filtrar chaves reais
    setores_ativos = {k: v for k, v in TICKERS_POR_SETOR.items() if k not in ["acoes"]}
    total_setores = len(setores_ativos)
    
    for i, (setor, tickers) in enumerate(setores_ativos.items()):
        status_text.text(f"Mapeando e indexando setor: {setor.capitalize()}...")
        
        dy_vals = []
        pl_vals = []
        pvp_vals = []
        
        # Guardar referência inversa de valor para ticker para achar quem foi o Min/Max
        ativos_dy = {}
        ativos_pl = {}
        ativos_pvp = {}

        for ticker in tickers:
            try:
                f = buscar_dados_fundamentalistas(ticker)
                
                if f and f.get("dy") is not None:
                    dy_vals.append(float(f["dy"]))
                    ativos_dy[float(f["dy"])] = ticker
                    
                if f and f.get("pl") is not None:
                    pl_vals.append(float(f["pl"]))
                    ativos_pl[float(f["pl"])] = ticker
                    
                if f and f.get("pvp") is not None:
                    pvp_vals.append(float(f["pvp"]))
                    ativos_pvp[float(f["pvp"])] = ticker

            except Exception:
                pass
                
        # --- Cálculo das Estatísticas ---
        def append_indicador(vals, ativos_dict, sigla, formatador="%.2f"):
            if vals:
                v_min = min(vals)
                v_max = max(vals)
                v_avg = sum(vals) / len(vals)
                v_mode = _safe_mode(vals)
                
                sufixo = "%" if sigla == "DY" else "x"
                dados.append({
                    "Setor": setor.capitalize(),
                    "Indicador": sigla,
                    "Mínimo": f"{formatador % v_min}{sufixo} ({ativos_dict[v_min]})",
                    "Máximo": f"{formatador % v_max}{sufixo} ({ativos_dict[v_max]})",
                    "Média": f"{formatador % v_avg}{sufixo}",
                    "Moda": f"{formatador % v_mode}{sufixo}"
                })

        append_indicador(dy_vals, ativos_dy, "DY")
        append_indicador(pl_vals, ativos_pl, "P/L")
        append_indicador(pvp_vals, ativos_pvp, "P/VP")
        
        progress_bar.progress((i + 1) / total_setores)
        
    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(dados)

with st.spinner("Processando base de dados fundamentalista (B3)... Pode levar alguns segundos."):
    df_stats = gerar_estatisticas_setoriais()

if df_stats.empty:
    st.warning("Não foi possível carregar os dados de mercado no momento.")
    st.stop()

# --- INTERFACE EXECUTIVA ---
setores_disp = sorted(df_stats["Setor"].unique().tolist())
filtro_setor = st.selectbox("Filtrar por Setor (Tabela Estatística):", ["Visão Geral de Todos"] + setores_disp)

st.markdown("---")

if filtro_setor == "Visão Geral de Todos":
    st.markdown("#### Tabela de Dispersão Geral")
    st.dataframe(df_stats, use_container_width=True, hide_index=True)
else:
    df_setor = df_stats[df_stats["Setor"] == filtro_setor].copy()
    
    st.markdown(f"#### Indicadores do Setor: {filtro_setor}")
    st.dataframe(df_setor, use_container_width=True, hide_index=True)

st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---")

st.markdown("### Ir para os Detalhes do Ativo")
st.markdown("*Use os tickers descobertos nas colunas de **Mínimo/Máximo** lado a lado da tabela para estudá-los a fundo na central.*")

c_input, c_btn = st.columns([1, 4])
with c_input:
    busca_ticker = st.text_input("Ticker da Ação / Fundo", placeholder="PETR4", key="btn_dt_ticker").strip().upper()
with c_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Inspecionar Ativo", type="primary"):
        if busca_ticker:
            st.session_state['view_asset_ticker'] = busca_ticker
            st.session_state['voltar_para_pagina'] = "pages/7_Estatisticas_Mercado.py"
            st.switch_page("pages/_8_Ativo.py")
        else:
            st.warning("Por favor, digite um Ticker válido antes de pesquisar.")
