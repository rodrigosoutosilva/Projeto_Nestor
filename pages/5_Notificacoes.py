import streamlit as st
import datetime
from database.crud import (
    listar_personas_usuario,
    listar_portfolios_persona,
    buscar_acoes_pendentes_todas,
    buscar_portfolio_por_id,
    atualizar_status_acao
)
from database.models import StatusAcao
from utils.helpers import injetar_css_global

st.set_page_config(page_title="Notificações e Atitudes", page_icon="🔔", layout="wide")
injetar_css_global()

if not st.session_state.get("user"):
    st.warning("Faça login para visualizar suas notificações.")
    st.stop()

user_id = st.session_state.user["id"]

st.title("🔔 Central de Notificações")
st.markdown("Gerencie atitudes sugeridas e delegadas pelas suas estratégias.")
st.markdown("---")

# 1. Filtros
col1, col2 = st.columns(2)

personas = listar_personas_usuario(user_id)
if not personas:
    st.info("Você não possui personas criadas.")
    st.stop()

persona_opcoes = {p["nome"]: p["id"] for p in personas}
with col1:
    persona_selecionada = st.selectbox("Filtrar por Persona:", ["Todas"] + list(persona_opcoes.keys()))

portfolio_opcoes = {}
if persona_selecionada != "Todas":
    portfolios = listar_portfolios_persona(persona_opcoes[persona_selecionada])
    portfolio_opcoes = {p["nome"]: p["id"] for p in portfolios}
    
with col2:
    if persona_selecionada == "Todas":
        portfolio_selecionado = st.selectbox("Filtrar por Carteira:", ["Selecione uma Persona primeiro"], disabled=True)
    else:
        portfolio_selecionado = st.selectbox("Filtrar por Carteira:", ["Todas"] + list(portfolio_opcoes.keys()))

st.markdown("---")

# 2. Coletar e filtrar ações
acoes_todas = buscar_acoes_pendentes_todas() # Traz todas do sistema
hoje = datetime.date.today()

# Filtrar pelas personas do usuário
personas_ids_permitidos = [p["id"] for p in personas]

# Aplicar filtros de interface
acoes_filtradas = []
for a in acoes_todas:
    port = buscar_portfolio_por_id(a["portfolio_id"])
    if not port: continue
    
    # Validação de segurança
    if port["persona_id"] not in personas_ids_permitidos: continue
    
    # Filtro de Persona
    if persona_selecionada != "Todas" and port["persona_id"] != persona_opcoes[persona_selecionada]:
        continue
        
    # Filtro de Carteira
    if persona_selecionada != "Todas" and portfolio_selecionado != "Todas" and a["portfolio_id"] != portfolio_opcoes[portfolio_selecionado]:
        continue
        
    a["_nome_carteira"] = port["nome"]
    acoes_filtradas.append(a)

# 3. Categorização
imediatas = []
futuras = []
abortadas = []

for a in acoes_filtradas:
    try:
        dt_str = str(a["data_planejada"]).split(" ")[0]
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d").date()
    except:
        dt = hoje

    status = a.get("status")
    
    if status == "abortado":
        abortadas.append(a)
    elif status == "planejado":
        if dt <= hoje:
            imediatas.append(a)
        else:
            futuras.append(a)

# 4. Renderização
def renderizar_card(acao, cor, icone, permite_executar=False):
    with st.container():
        st.markdown(f"""
        <div style="border-left: 5px solid {cor}; padding: 15px; border-radius: 5px; background-color: rgba(255,255,255,0.8); margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display:flex; justify-content:space-between;">
                <strong>{icone} {acao['asset_ticker']} ({acao['tipo_acao'].upper()})</strong>
                <span style="color:#666; font-size:0.85em;">📅 Data Alvo: {acao['data_planejada']}</span>
            </div>
            <div style="font-size: 0.9em; margin-top:5px; color:#444;">
                {acao.get('explicacao', 'Sem explicação')}
            </div>
            <div style="font-size: 0.8em; margin-top:5px; color:#888;">
                💼 Carteira: {acao.get('_nome_carteira', '')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        if permite_executar:
            if st.button("Marcar como Executado", key=f"exec_{acao['id']}"):
                atualizar_status_acao(acao['id'], "executado")
                st.rerun()

st.subheader("🚨 Imediatas e Vencidas")
if imediatas:
    for acao in imediatas:
        cor = "#FF3333" if str(acao["data_planejada"]) < str(hoje) else "#FFCC00"
        renderizar_card(acao, cor, "⏰", permite_executar=True)
else:
    st.success("Tudo em dia! Nenhuma atitude imediata pendente.")

st.markdown("<br>", unsafe_allow_html=True)
st.subheader("⏳ Futuras (Mapeadas)")
if futuras:
    for acao in futuras:
        renderizar_card(acao, "#3399FF", "📅", permite_executar=True)
else:
    st.info("Nenhuma atitude delegada para o futuro.")

st.markdown("<br>", unsafe_allow_html=True)
with st.expander("❌ Abortadas pelo Algoritmo (Não fazem mais sentido)"):
    if abortadas:
        for acao in abortadas:
            renderizar_card(acao, "#999999", "🗑️")
    else:
        st.info("Nenhuma ação abortada até o momento.")
