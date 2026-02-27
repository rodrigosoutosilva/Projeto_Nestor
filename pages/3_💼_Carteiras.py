"""
💼 Carteiras - Gestão de Portfolios e Ativos
==============================================

Melhorias v2:
- Confirmação de exclusão (carteira e ativos)
- Edição de carteira (nome, montante, setores)
- Compra/venda manual com impacto no caixa
- Export CSV dos ativos
- Navegação "Gerar Recomendações →"
- Toasts para feedback
- "Data da Posição" (renomeado de "Data da Compra")
"""

import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    criar_portfolio, deletar_portfolio, atualizar_portfolio,
    listar_ativos_portfolio, adicionar_ativo, deletar_ativo, atualizar_ativo,
    buscar_persona_por_id, registrar_transacao
)
from utils.helpers import (
    parsear_csv_ativos, formatar_moeda, formatar_data_br,
    calcular_meta_dividendos_auto,
    SETORES_ACOES, SETORES_FIIS
)
from services.market_data import buscar_preco_atual
from datetime import date

# Mapeamento de frequência para ordenação (menor valor = mais frequente)
FREQ_ORDEM = {"diario": 1, "semanal": 2, "mensal": 3}
FREQ_LABELS = {
    "diario": "📅 Diário",
    "semanal": "📆 Semanal",
    "mensal": "🗓️ Mensal"
}

def frequencias_permitidas(freq_persona: str) -> list:
    """
    Retorna as frequências de manuseio permitidas para a carteira.
    A carteira pode ter frequência menor ou igual à da persona.
    (Menor frequência = valor maior no FREQ_ORDEM)
    """
    nivel_persona = FREQ_ORDEM.get(freq_persona, 2)
    return [f for f, n in FREQ_ORDEM.items() if n >= nivel_persona]

st.set_page_config(page_title="💼 Carteiras", page_icon="💼", layout="wide")

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("# 💼 Gestão de Carteiras e Ativos")
st.markdown("*Gerencie seus portfolios, registre operações e acompanhe seu caixa*")
st.markdown("---")

# Estado para confirmações
if "confirmar_excluir_port" not in st.session_state:
    st.session_state.confirmar_excluir_port = None
if "confirmar_excluir_ativo" not in st.session_state:
    st.session_state.confirmar_excluir_ativo = None

# Buscar personas
personas = listar_personas_usuario(user["id"])

if not personas:
    st.warning("Crie uma **Persona** antes de criar uma carteira. Vá para 🧑 Personas.")
    st.stop()

# ---------------------------------------------------------------------------
# Selecionar Persona
# ---------------------------------------------------------------------------
persona_nomes = [f"{p['nome']} (Risco: {p['tolerancia_risco']}/10)" for p in personas]
persona_idx = st.selectbox("Selecione a Persona:", range(len(personas)),
                           format_func=lambda i: persona_nomes[i])
persona_selecionada = personas[persona_idx]

st.markdown("---")

# ---------------------------------------------------------------------------
# Criar Nova Carteira
# ---------------------------------------------------------------------------
with st.expander("➕ Criar Nova Carteira", expanded=False):
    with st.form("form_nova_carteira"):
        col1, col2 = st.columns(2)

        with col1:
            nome_cart = st.text_input(
                "Nome da Carteira",
                placeholder="Ex: Ações Blue Chip, FIIs Renda, Long & Short..."
            )
            objetivo = st.selectbox(
                "Objetivo de Prazo",
                options=["curto", "medio", "longo"],
                format_func=lambda x: {
                    "curto": "🏃 Curto Prazo (< 1 ano)",
                    "medio": "🚶 Médio Prazo (1-5 anos)",
                    "longo": "🧘 Longo Prazo (> 5 anos)"
                }[x],
                index=2
            )

        with col2:
            tipo = st.selectbox(
                "Tipo de Ativo",
                options=["acoes", "fiis", "misto"],
                format_func=lambda x: {
                    "acoes": "📈 Ações",
                    "fiis": "🏢 FIIs",
                    "misto": "🔀 Misto (Ações + FIIs)"
                }[x],
                index=2
            )
            montante = st.number_input(
                "💰 Montante inicial (R$)",
                min_value=0.0, max_value=10_000_000.0, value=1000.0, step=100.0,
                help="Montante em reais que você pode alocar nesta carteira. "
                     "Isso ajuda a IA a não sugerir compras que você não pode bancar."
            )

        # --- Aportes periódicos ---
        st.markdown("**💸 Aportes Periódicos** *(opcional — configure aportes recorrentes)*")
        col_ap1, col_ap2 = st.columns(2)
        with col_ap1:
            aporte_valor = st.number_input(
                "Valor do aporte periódico (R$)",
                min_value=0.0, max_value=1_000_000.0, value=0.0, step=50.0,
                help="Valor em reais que você pretende aportar recorrentemente."
            )
        with col_ap2:
            freq_aporte_opcoes = ["", "semanal", "quinzenal", "mensal"]
            freq_aporte_labels = {
                "": "— Sem aporte periódico —",
                "semanal": "📆 Semanal",
                "quinzenal": "📆 Quinzenal",
                "mensal": "🗓️ Mensal"
            }
            freq_aporte = st.selectbox(
                "Frequência do aporte",
                options=freq_aporte_opcoes,
                format_func=lambda x: freq_aporte_labels[x]
            )

        # --- Frequência de manuseio ---
        st.markdown("**⏱️ Frequência de manuseio** *(com que frequência você revisa esta carteira)*")
        freqs_permitidas = frequencias_permitidas(persona_selecionada["frequencia_acao"])
        freq_manuseio_opcoes = [""] + freqs_permitidas
        freq_manuseio_labels = {
            "": f"🔄 Herdar da persona ({FREQ_LABELS.get(persona_selecionada['frequencia_acao'], persona_selecionada['frequencia_acao'])})",
            **FREQ_LABELS
        }
        freq_manuseio = st.selectbox(
            "Frequência de revisão da carteira",
            options=freq_manuseio_opcoes,
            format_func=lambda x: freq_manuseio_labels.get(x, x),
            help=f"Deve ser igual ou menos frequente que a da persona ({persona_selecionada['frequencia_acao']}). "
                 "Ex: se a persona é diária, a carteira pode ser diária, semanal ou mensal."
        )

        # Setores preferidos
        st.markdown("**🏭 Setores de preferência** *(opcional — ajuda a IA a sugerir ativos)*")

        setores_selecionados = []

        if tipo in ("acoes", "misto"):
            st.markdown("**Ações:**")
            cols_setores = st.columns(3)
            for i, (chave, label) in enumerate(SETORES_ACOES):
                with cols_setores[i % 3]:
                    if st.checkbox(label, key=f"setor_a_{chave}"):
                        setores_selecionados.append(chave)

        if tipo in ("fiis", "misto"):
            st.markdown("**FIIs:**")
            cols_fiis = st.columns(2)
            for i, (chave, label) in enumerate(SETORES_FIIS):
                with cols_fiis[i % 2]:
                    if st.checkbox(label, key=f"setor_f_{chave}"):
                        setores_selecionados.append(chave)

        # Meta DY automática
        meta_dy_auto = calcular_meta_dividendos_auto(
            tolerancia_risco=persona_selecionada["tolerancia_risco"],
            estilo=persona_selecionada["estilo"],
            objetivo_prazo=objetivo
        )
        st.info(
            f"📊 **Meta de dividendos calculada automaticamente: {meta_dy_auto}% ao ano** "
            f"— baseada no seu perfil ({persona_selecionada['estilo'].capitalize()}, "
            f"risco {persona_selecionada['tolerancia_risco']}/10, prazo {objetivo})"
        )

        submitted = st.form_submit_button("✅ Criar Carteira", use_container_width=True)
        if submitted:
            if not nome_cart:
                st.error("O nome da carteira é obrigatório!")
            elif aporte_valor > 0 and not freq_aporte:
                st.error("Se definiu um valor de aporte, selecione a frequência!")
            else:
                setores_str = ",".join(setores_selecionados)
                result = criar_portfolio(
                    persona_id=persona_selecionada["id"],
                    nome=nome_cart,
                    objetivo_prazo=objetivo,
                    meta_dividendos=meta_dy_auto,
                    tipo_ativo=tipo,
                    setores_preferidos=setores_str,
                    montante_disponivel=montante,
                    aporte_periodico=aporte_valor,
                    frequencia_aporte=freq_aporte,
                    frequencia_manuseio=freq_manuseio
                )
                # Registrar aporte inicial se montante > 0
                if montante > 0:
                    registrar_transacao(
                        portfolio_id=result["id"],
                        tipo="aporte",
                        valor=montante,
                        descricao="Aporte inicial ao criar carteira"
                    )
                st.toast(f"Carteira **{nome_cart}** criada! 🎉")
                st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Listar Carteiras da Persona
# ---------------------------------------------------------------------------
st.markdown(f"### 💼 Carteiras de '{persona_selecionada['nome']}'")

portfolios = listar_portfolios_persona(persona_selecionada["id"])

if not portfolios:
    st.info("Nenhuma carteira nesta persona. Crie uma acima.")
else:
    for port in portfolios:
        tipo_emoji = {"acoes": "📈", "fiis": "🏢", "misto": "🔀"}.get(port["tipo_ativo"], "📊")
        montante_txt = f" | 💰 {formatar_moeda(port['montante_disponivel'])}" if port.get('montante_disponivel') else ""
        aporte_txt = ""
        if port.get('aporte_periodico') and port['aporte_periodico'] > 0:
            freq_label = {"semanal": "sem", "quinzenal": "quinz", "mensal": "mês"}.get(port.get('frequencia_aporte', ''), '')
            aporte_txt = f" | 💸 {formatar_moeda(port['aporte_periodico'])}/{freq_label}"
        freq_txt = ""
        if port.get('frequencia_manuseio'):
            freq_txt = f" | ⏱️ {port['frequencia_manuseio'].capitalize()}"

        with st.expander(
            f"{tipo_emoji} **{port['nome']}** — "
            f"Prazo: {port['objetivo_prazo']} | "
            f"Meta DY: {port['meta_dividendos']}% | "
            f"Tipo: {port['tipo_ativo']}{montante_txt}{aporte_txt}{freq_txt}"
        ):
            # Setores preferidos
            if port.get("setores_preferidos"):
                setores_list = port["setores_preferidos"].split(",")
                st.markdown(f"🏭 **Setores:** {', '.join(s.capitalize() for s in setores_list)}")

            # --- Editar Carteira ---
            with st.expander("✏️ Editar Carteira"):
                with st.form(f"form_edit_port_{port['id']}"):
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        edit_nome = st.text_input("Nome:", value=port["nome"], key=f"edit_pname_{port['id']}")
                    with col_e2:
                        edit_montante = st.number_input(
                            "Montante disponível (R$):",
                            value=float(port.get("montante_disponivel", 0)),
                            min_value=0.0, step=100.0,
                            key=f"edit_pmnt_{port['id']}"
                        )

                    # Editar aportes periódicos
                    col_ea1, col_ea2 = st.columns(2)
                    with col_ea1:
                        edit_aporte = st.number_input(
                            "💸 Aporte periódico (R$):",
                            value=float(port.get("aporte_periodico", 0)),
                            min_value=0.0, step=50.0,
                            key=f"edit_aporte_{port['id']}"
                        )
                    with col_ea2:
                        freq_aporte_edit_opcoes = ["", "semanal", "quinzenal", "mensal"]
                        freq_aporte_edit_labels = {
                            "": "— Sem aporte periódico —",
                            "semanal": "📆 Semanal",
                            "quinzenal": "📆 Quinzenal",
                            "mensal": "🗓️ Mensal"
                        }
                        current_freq = port.get("frequencia_aporte", "")
                        edit_freq_aporte = st.selectbox(
                            "Frequência do aporte:",
                            options=freq_aporte_edit_opcoes,
                            index=freq_aporte_edit_opcoes.index(current_freq) if current_freq in freq_aporte_edit_opcoes else 0,
                            format_func=lambda x: freq_aporte_edit_labels.get(x, x),
                            key=f"edit_freq_aporte_{port['id']}"
                        )

                    # Editar frequência de manuseio
                    freqs_edit = frequencias_permitidas(persona_selecionada["frequencia_acao"])
                    freq_manuseio_edit_opcoes = [""] + freqs_edit
                    freq_manuseio_edit_labels = {
                        "": f"🔄 Herdar da persona ({FREQ_LABELS.get(persona_selecionada['frequencia_acao'], '')})",
                        **FREQ_LABELS
                    }
                    current_manuseio = port.get("frequencia_manuseio", "")
                    edit_freq_manuseio = st.selectbox(
                        "⏱️ Frequência de manuseio:",
                        options=freq_manuseio_edit_opcoes,
                        index=freq_manuseio_edit_opcoes.index(current_manuseio) if current_manuseio in freq_manuseio_edit_opcoes else 0,
                        format_func=lambda x: freq_manuseio_edit_labels.get(x, x),
                        key=f"edit_freq_man_{port['id']}"
                    )

                    if st.form_submit_button("💾 Salvar", use_container_width=True):
                        atualizar_portfolio(
                            port["id"],
                            nome=edit_nome,
                            montante_disponivel=edit_montante,
                            aporte_periodico=edit_aporte,
                            frequencia_aporte=edit_freq_aporte,
                            frequencia_manuseio=edit_freq_manuseio
                        )
                        st.toast("Carteira atualizada! ✅")
                        st.rerun()

            # --- Listar ativos ---
            ativos = listar_ativos_portfolio(port["id"])

            if ativos:
                st.markdown("#### 📊 Ativos na Carteira")

                # Export CSV
                df_export = pd.DataFrame([{
                    "Ticker": a["ticker"],
                    "Qtd": a["quantidade"],
                    "Preço Médio": a["preco_medio"],
                    "Data Posição": formatar_data_br(a["data_posicao"])
                } for a in ativos])

                st.download_button(
                    "📤 Exportar CSV",
                    df_export.to_csv(index=False).encode("utf-8"),
                    f"carteira_{port['nome']}.csv",
                    "text/csv",
                    key=f"export_{port['id']}"
                )

                for ativo in ativos:
                    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                    with col1:
                        st.markdown(f"**{ativo['ticker']}**")
                    with col2:
                        st.markdown(f"Qtd: {ativo['quantidade']}")
                    with col3:
                        st.markdown(f"PM: {formatar_moeda(ativo['preco_medio'])}")
                    with col4:
                        st.markdown(f"📅 {formatar_data_br(ativo['data_posicao'])}")
                    with col5:
                        if st.session_state.confirmar_excluir_ativo == ativo["id"]:
                            c1, c2 = st.columns(2)
                            with c1:
                                if st.button("✅", key=f"conf_da_{ativo['id']}"):
                                    deletar_ativo(ativo["id"])
                                    st.session_state.confirmar_excluir_ativo = None
                                    st.toast(f"Ativo {ativo['ticker']} removido.")
                                    st.rerun()
                            with c2:
                                if st.button("❌", key=f"canc_da_{ativo['id']}"):
                                    st.session_state.confirmar_excluir_ativo = None
                                    st.rerun()
                        else:
                            if st.button("🗑️", key=f"del_ativo_{ativo['id']}"):
                                st.session_state.confirmar_excluir_ativo = ativo["id"]
                                st.rerun()
            else:
                st.info("Nenhum ativo ainda. Adicione abaixo.")

            st.markdown("---")

            # --- Registrar Compra/Venda Manual ---
            st.markdown("#### 🛒 Registrar Compra ou Venda")
            st.markdown("*Registre operações realizadas — o caixa será atualizado automaticamente*")

            with st.form(f"form_operacao_{port['id']}"):
                col_op1, col_op2 = st.columns(2)
                with col_op1:
                    tipo_op = st.radio(
                        "Tipo de operação:",
                        ["🟢 Compra", "🔴 Venda"],
                        key=f"tipo_op_{port['id']}",
                        horizontal=True
                    )
                with col_op2:
                    op_ticker = st.text_input("Ticker:", placeholder="PETR4", key=f"op_ticker_{port['id']}")

                col_op3, col_op4, col_op5 = st.columns(3)
                with col_op3:
                    op_qtd = st.number_input("Quantidade:", min_value=1, value=100, key=f"op_qtd_{port['id']}")
                with col_op4:
                    op_preco = st.number_input("Preço unitário (R$):", min_value=0.01, value=10.0, step=0.01, key=f"op_preco_{port['id']}")
                with col_op5:
                    op_data = st.date_input("Data:", value=date.today(), key=f"op_data_{port['id']}")

                if st.form_submit_button("✅ Registrar Operação", use_container_width=True):
                    if not op_ticker:
                        st.error("Informe o ticker!")
                    else:
                        valor_total = op_qtd * op_preco
                        is_compra = "Compra" in tipo_op

                        if is_compra:
                            # Checar se tem caixa suficiente
                            caixa_atual = port.get("montante_disponivel", 0)
                            if valor_total > caixa_atual:
                                st.error(f"Caixa insuficiente! Disponível: {formatar_moeda(caixa_atual)}, necessário: {formatar_moeda(valor_total)}")
                                st.stop()

                            # Verificar se ativo já existe na carteira
                            ticker_upper = op_ticker.upper().strip()
                            ativo_existente = next((a for a in ativos if a["ticker"] == ticker_upper), None)

                            if ativo_existente:
                                # Atualizar preço médio ponderado e quantidade
                                qtd_antiga = ativo_existente["quantidade"]
                                pm_antigo = ativo_existente["preco_medio"]
                                nova_qtd = qtd_antiga + op_qtd
                                novo_pm = ((pm_antigo * qtd_antiga) + (op_preco * op_qtd)) / nova_qtd
                                atualizar_ativo(ativo_existente["id"], quantidade=nova_qtd, preco_medio=round(novo_pm, 2))
                            else:
                                adicionar_ativo(
                                    portfolio_id=port["id"],
                                    ticker=ticker_upper,
                                    preco_medio=op_preco,
                                    quantidade=op_qtd,
                                    data_posicao=op_data
                                )

                            registrar_transacao(
                                portfolio_id=port["id"],
                                tipo="compra",
                                valor=valor_total,
                                ticker=ticker_upper,
                                quantidade=op_qtd,
                                preco_unitario=op_preco,
                                descricao=f"Compra manual de {op_qtd}x {ticker_upper}",
                                data_transacao=op_data
                            )
                            st.toast(f"Compra de {op_qtd}x {ticker_upper} registrada! 🟢")

                        else:  # Venda
                            ticker_upper = op_ticker.upper().strip()
                            ativo_existente = next((a for a in ativos if a["ticker"] == ticker_upper), None)

                            if not ativo_existente:
                                st.error(f"Ativo {ticker_upper} não encontrado na carteira!")
                                st.stop()
                            if op_qtd > ativo_existente["quantidade"]:
                                st.error(f"Você só possui {ativo_existente['quantidade']} unidades de {ticker_upper}!")
                                st.stop()

                            nova_qtd = ativo_existente["quantidade"] - op_qtd
                            if nova_qtd == 0:
                                deletar_ativo(ativo_existente["id"])
                            else:
                                atualizar_ativo(ativo_existente["id"], quantidade=nova_qtd)

                            registrar_transacao(
                                portfolio_id=port["id"],
                                tipo="venda",
                                valor=valor_total,
                                ticker=ticker_upper,
                                quantidade=op_qtd,
                                preco_unitario=op_preco,
                                descricao=f"Venda manual de {op_qtd}x {ticker_upper}",
                                data_transacao=op_data
                            )
                            st.toast(f"Venda de {op_qtd}x {ticker_upper} registrada! 🔴")

                        st.rerun()

            st.markdown("---")

            # --- Adicionar ativo (inserção direta) ---
            st.markdown("#### ➕ Inserir Posição Existente")
            st.markdown("*Para ativos que você já possui e quer apenas registrar na plataforma*")
            with st.form(f"form_ativo_{port['id']}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    ticker = st.text_input("Ticker", placeholder="PETR4",
                                          key=f"ticker_{port['id']}")
                with col2:
                    qtd = st.number_input("Quantidade", min_value=1, value=100,
                                         key=f"qtd_{port['id']}")
                with col3:
                    pm = st.number_input("Preço Médio (R$)", min_value=0.01,
                                        value=10.0, step=0.01,
                                        key=f"pm_{port['id']}")
                with col4:
                    data = st.date_input("Data da Posição", value=date.today(),
                                        key=f"data_{port['id']}")

                if st.form_submit_button("➕ Inserir", use_container_width=True):
                    if not ticker:
                        st.error("Informe o ticker!")
                    else:
                        adicionar_ativo(
                            portfolio_id=port["id"],
                            ticker=ticker,
                            preco_medio=pm,
                            quantidade=qtd,
                            data_posicao=data
                        )
                        st.toast(f"Ativo {ticker.upper()} inserido! ✅")
                        st.rerun()

            # Upload CSV
            st.markdown("#### 📥 Upload via CSV")
            st.markdown("Formato: `ticker,quantidade,preco_medio,data_posicao`")
            uploaded = st.file_uploader(
                "Selecione o arquivo CSV",
                type=["csv"],
                key=f"csv_{port['id']}"
            )

            if uploaded:
                conteudo = uploaded.getvalue().decode("utf-8")
                ativos_csv = parsear_csv_ativos(conteudo)

                if ativos_csv:
                    st.markdown(f"**{len(ativos_csv)} ativos encontrados no CSV:**")
                    for a in ativos_csv:
                        st.markdown(
                            f"- {a['ticker']} | Qtd: {a['quantidade']} | "
                            f"PM: {formatar_moeda(a['preco_medio'])} | "
                            f"Data: {formatar_data_br(a['data_posicao'])}"
                        )

                    if st.button(
                        "✅ Importar Todos",
                        key=f"import_{port['id']}",
                        use_container_width=True
                    ):
                        for a in ativos_csv:
                            adicionar_ativo(
                                portfolio_id=port["id"],
                                ticker=a["ticker"],
                                preco_medio=a["preco_medio"],
                                quantidade=a["quantidade"],
                                data_posicao=a["data_posicao"]
                            )
                        st.toast(f"{len(ativos_csv)} ativos importados! 🎉")
                        st.rerun()
                else:
                    st.error("Nenhum ativo válido encontrado no CSV.")

            st.markdown("---")

            # Navegação contextual
            if ativos:
                if st.button(
                    "🧠 Gerar Recomendações para esta Carteira →",
                    key=f"nav_rec_{port['id']}",
                    use_container_width=True
                ):
                    st.switch_page("pages/4_🧠_Recomendacoes.py")

            st.markdown("---")

            # Botão excluir carteira (com confirmação)
            if st.session_state.confirmar_excluir_port == port["id"]:
                st.error(f"⚠️ Excluir carteira **{port['nome']}** e todos os seus ativos?")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("✅ Sim, excluir", key=f"conf_dp_{port['id']}", use_container_width=True):
                        deletar_portfolio(port["id"])
                        st.session_state.confirmar_excluir_port = None
                        st.toast(f"Carteira {port['nome']} excluída.")
                        st.rerun()
                with col_c2:
                    if st.button("❌ Cancelar", key=f"canc_dp_{port['id']}", use_container_width=True):
                        st.session_state.confirmar_excluir_port = None
                        st.rerun()
            else:
                if st.button(
                    f"🗑️ Excluir Carteira '{port['nome']}'",
                    key=f"del_port_{port['id']}",
                    type="secondary"
                ):
                    st.session_state.confirmar_excluir_port = port["id"]
                    st.rerun()
