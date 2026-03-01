import streamlit as st
import pandas as pd
from datetime import date
from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    listar_acoes_portfolio, listar_transacoes_portfolio
)
from utils.helpers import formatar_moeda, nome_ativo

st.set_page_config(page_title="Calendário de Movimentos", page_icon="📅", layout="wide")

if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

st.header("📅 Calendário de Movimentos")
st.markdown("Visualize suas operações planejadas e executadas organizadas cronologicamente.")

personas = listar_personas_usuario(st.session_state.user['id'])
if not personas:
    st.info("Nenhuma persona encontrada. Crie uma para começar.")
    st.stop()

# --- FILTROS ---
c1, c2, c3 = st.columns(3)
with c1:
    op_personas = {p["id"]: p["nome"] for p in personas}
    p_id = st.selectbox("Persona", ["Todas"] + list(op_personas.keys()), format_func=lambda x: "Todas" if x == "Todas" else op_personas[x])

portfolios = []
if p_id != "Todas":
    portfolios = listar_portfolios_persona(p_id)
else:
    for p in personas:
        portfolios.extend(listar_portfolios_persona(p["id"]))

with c2:
    if portfolios:
        op_ports = {pt["id"]: pt["nome"] for pt in portfolios}
        port_id = st.selectbox("Carteira", ["Todas"] + list(op_ports.keys()), format_func=lambda x: "Todas" if x == "Todas" else op_ports[x])
    else:
        port_id = "Todas"
        st.selectbox("Carteira", ["Nenhuma carteira"])
        
with c3:
    mes_opcoes = ["Todos", "Este Mês", "Próximo Mês"]
    filtro_mes = st.selectbox("Período", mes_opcoes)

# --- COLETAR DADOS ---
movimentos = [] # lista de dicionários com data, tipo (planejado/executado), descricao, valor, carteira

portfolios_filtrados = [port_id] if port_id != "Todas" else [pt["id"] for pt in portfolios]

for pid in portfolios_filtrados:
    port_nome = next(pt["nome"] for pt in portfolios if pt["id"] == pid)
    
    # Pendentes
    acoes = listar_acoes_portfolio(pid, status="planejado")
    for a in acoes:
        movimentos.append({
            "Data": a["data_planejada"],
            "Status": "⏳ Planejado",
            "Ativo": f"{a['asset_ticker']} - {nome_ativo(a['asset_ticker'])}",
            "Operação": a["tipo_acao"].upper(),
            "Valor": formatar_moeda(a.get("caixa_necessario") or 0),
            "Carteira": port_nome,
            "Info": a["explicacao"]
        })
        
    # Executadas
    transacoes = listar_transacoes_portfolio(pid)
    for t in transacoes:
        movimentos.append({
            "Data": pd.to_datetime(t["data"]).date() if isinstance(t["data"], str) else t["data"],
            "Status": "✅ Executado",
            "Ativo": f"{t['ticker']} - {nome_ativo(t['ticker'])}" if t['ticker'] else "-",
            "Operação": t["tipo"].upper(),
            "Valor": formatar_moeda(t["valor"]),
            "Carteira": port_nome,
            "Info": t["descricao"]
        })

# --- APLICAR FILTROS DE TEMPO E ORDENAR ---
df = pd.DataFrame(movimentos)

if not df.empty:
    df["Data_Obj"] = pd.to_datetime(df["Data"])
    hoje = date.today()
    
    if filtro_mes == "Este Mês":
        df = df[(df["Data_Obj"].dt.year == hoje.year) & (df["Data_Obj"].dt.month == hoje.month)]
    elif filtro_mes == "Próximo Mês":
        next_month = hoje.month + 1 if hoje.month < 12 else 1
        next_year = hoje.year if hoje.month < 12 else hoje.year + 1
        df = df[(df["Data_Obj"].dt.year == next_year) & (df["Data_Obj"].dt.month == next_month)]
        
    df = df.sort_values(by="Data_Obj", ascending=False).drop(columns=["Data_Obj"])

# --- EXIBIR ---
if not df.empty:
    st.markdown(f"**Total de movimentos encontrados:** {len(df)}")
    
    st.dataframe(
        df,
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Status": st.column_config.TextColumn("Status"),
            "Operação": st.column_config.TextColumn("Operação"),
            "Ativo": st.column_config.TextColumn("Ativo"),
            "Valor": st.column_config.TextColumn("Valor Estimado/Real"),
            "Carteira": st.column_config.TextColumn("Carteira"),
            "Info": st.column_config.TextColumn("Detalhes", width="large"),
        },
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Nenhum movimento encontrado para os filtros selecionados.")
