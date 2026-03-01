"""
📥 Onboarding Inteligente - Configuração Inicial
==================================================

Fluxo step-by-step estilo chatbot para novos investidores:
1. Perguntas sobre perfil de risco
2. Objetivos de investimento
3. Sugestão de carteira inicial via IA
4. Criação automática de Persona + Portfolio + Assets
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    criar_persona, criar_portfolio, adicionar_ativo,
    listar_personas_usuario
)
from services.ai_brain import gerar_sugestao_onboarding, configurar_gemini
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_moeda, calcular_meta_dividendos_auto

st.set_page_config(page_title="📥 Onboarding", page_icon="📥", layout="wide")

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

# ---------------------------------------------------------------------------
# Inicializar estado do onboarding
# ---------------------------------------------------------------------------
if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 0
if "onboarding_respostas" not in st.session_state:
    st.session_state.onboarding_respostas = {}
if "onboarding_sugestao" not in st.session_state:
    st.session_state.onboarding_sugestao = None
if "onboarding_completo" not in st.session_state:
    st.session_state.onboarding_completo = False

step = st.session_state.onboarding_step
respostas = st.session_state.onboarding_respostas


def avancar():
    st.session_state.onboarding_step += 1


def voltar():
    st.session_state.onboarding_step = max(0, st.session_state.onboarding_step - 1)


# ---------------------------------------------------------------------------
# Header com progresso
# ---------------------------------------------------------------------------
st.markdown("### 📥 Onboarding Inteligente")
st.markdown("*Vamos montar sua carteira ideal com a ajuda da IA*")

total_steps = 6
progress = min(step / total_steps, 1.0)
st.progress(progress)
st.markdown(f"**Passo {min(step + 1, total_steps)}/{total_steps}**")
st.markdown("---")

# ---------------------------------------------------------------------------
# PASSO 0: Boas-vindas
# ---------------------------------------------------------------------------
if step == 0:
    st.markdown("### 👋 Bem-vindo ao Onboarding!")
    st.markdown("""
    Vou te fazer algumas perguntas para entender seu **perfil de investidor** 
    e sugerir uma **carteira inicial diversificada** usando Inteligência Artificial.
    
    O processo leva cerca de **2 minutos**. Ao final, criaremos automaticamente:
    - 🧑 Uma **Persona** com seu perfil
    - 💼 Uma **Carteira** com ativos sugeridos pela IA
    
    Pronto para começar?
    """)

    if st.button("🚀 Vamos lá!", use_container_width=True):
        avancar()
        st.rerun()

# ---------------------------------------------------------------------------
# PASSO 1: Nome da Persona
# ---------------------------------------------------------------------------
elif step == 1:
    st.markdown("### 🧑 Como você quer chamar este perfil?")
    st.markdown("_Você pode ter vários perfis depois. Este é só o primeiro._")

    nome = st.text_input(
        "Nome da Persona:",
        value=respostas.get("nome_persona", ""),
        placeholder="Ex: Minha Carteira Principal, Aposentadoria, Especulação..."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            voltar()
            st.rerun()
    with col2:
        if st.button("Próximo ➡️", use_container_width=True):
            if not nome:
                st.error("Por favor, dê um nome ao perfil.")
            else:
                respostas["nome_persona"] = nome
                avancar()
                st.rerun()

# ---------------------------------------------------------------------------
# PASSO 2: Tolerância a Risco
# ---------------------------------------------------------------------------
elif step == 2:
    st.markdown("### 📊 Qual sua tolerância a risco?")
    st.markdown("""
    _Imagine que você investiu R$ 10.000 e no mês seguinte
    seu investimento caiu para R$ 8.000 (-20%). O que você faria?_
    """)

    opcao_risco = st.radio(
        "Escolha:",
        [
            "😰 Venderia tudo imediatamente (não suporto perder dinheiro)",
            "😟 Ficaria preocupado, mas esperaria um tempo",
            "🤔 Manteria a posição e aguardaria a recuperação",
            "😎 Compraria mais, aproveitando o preço baixo",
            "🤑 Investiria três vezes mais, amo risco!"
        ],
        index=respostas.get("opcao_risco_idx", 2)
    )

    mapa_risco = {
        "😰": 1, "😟": 3, "🤔": 5, "😎": 7, "🤑": 10
    }
    tolerancia = mapa_risco.get(opcao_risco.split()[0], 5)

    st.markdown(f"**Tolerância a risco: {tolerancia}/10**")

    if tolerancia <= 3:
        st.success("🟢 Perfil **Conservador** — Prioriza segurança e renda fixa")
    elif tolerancia <= 6:
        st.info("🟡 Perfil **Moderado** — Equilibra risco e retorno")
    else:
        st.warning("🔴 Perfil **Arrojado** — Aceita alta volatilidade por maiores ganhos")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            voltar()
            st.rerun()
    with col2:
        if st.button("Próximo ➡️", use_container_width=True):
            respostas["tolerancia_risco"] = tolerancia
            respostas["opcao_risco_idx"] = [
                "😰", "😟", "🤔", "😎", "🤑"
            ].index(opcao_risco.split()[0])
            avancar()
            st.rerun()

# ---------------------------------------------------------------------------
# PASSO 3: Estilo e Objetivo
# ---------------------------------------------------------------------------
elif step == 3:
    st.markdown("### 🎯 Qual seu objetivo principal?")

    estilo = st.radio(
        "O que é mais importante para você?",
        [
            "💰 Receber renda passiva mensal (dividendos, FIIs)",
            "🚀 Valorizar o patrimônio ao longo do tempo (crescimento)",
            "⚖️ Equilibrar renda passiva e valorização (mix)"
        ],
        index={"dividendos": 0, "crescimento": 1, "equilibrado": 2}.get(respostas.get("estilo", "dividendos"), 0)
    )
    estilo_valor = {"💰": "dividendos", "🚀": "crescimento", "⚖": "equilibrado"}.get(estilo[:2], "dividendos")

    st.markdown("---")
    st.markdown("### ⏳ Qual seu prazo de investimento?")

    prazo = st.radio(
        "Quando você pretende usar esse dinheiro?",
        [
            "🏃 Curto prazo — menos de 1 ano",
            "🚶 Médio prazo — 1 a 5 anos",
            "🧘 Longo prazo — mais de 5 anos"
        ],
        index={"curto": 0, "medio": 1, "longo": 2}.get(respostas.get("objetivo_prazo", "longo"), 2)
    )
    prazo_valor = {"🏃": "curto", "🚶": "medio", "🧘": "longo"}.get(prazo[:2], "longo")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            voltar()
            st.rerun()
    with col2:
        if st.button("Próximo ➡️", use_container_width=True):
            respostas["estilo"] = estilo_valor
            respostas["objetivo_prazo"] = prazo_valor
            avancar()
            st.rerun()

# ---------------------------------------------------------------------------
# PASSO 4: Detalhes Financeiros
# ---------------------------------------------------------------------------
elif step == 4:
    st.markdown("### 💵 Detalhes financeiros")

    col1, col2 = st.columns(2)
    with col1:
        valor = st.number_input(
            "💰 Valor disponível para investir (R$):",
            min_value=100.0, max_value=10_000_000.0,
            value=float(respostas.get("valor_disponivel", 5000)),
            step=500.0,
            help="Quanto você pretende investir nesta carteira? "
                 "Isso ajuda a IA a sugerir quantidades compatíveis."
        )

    # Meta de dividendos calculada automaticamente
    meta_dy = calcular_meta_dividendos_auto(
        tolerancia_risco=respostas.get("tolerancia_risco", 5),
        estilo=respostas.get("estilo", "dividendos"),
        objetivo_prazo=respostas.get("objetivo_prazo", "longo")
    )
    st.info(
        f"📊 **Meta de dividendos calculada automaticamente: {meta_dy}% ao ano** "
        f"\u2014 baseada no seu perfil ({respostas.get('estilo', 'dividendos').capitalize()}, "
        f"risco {respostas.get('tolerancia_risco', 5)}/10, "
        f"prazo {respostas.get('objetivo_prazo', 'longo')})"
    )

    frequencia = st.selectbox(
        "Com que frequência quer revisar a carteira?",
        [
            ("semanal", "📆 Semanal — Ideal para a maioria"),
            ("diario", "📅 Diário — Para investidores muito ativos"),
            ("mensal", "🗓️ Mensal — Para quem prefere buy & hold"),
        ],
        format_func=lambda x: x[1],
        index=0
    )

    tipo_ativo = st.radio(
        "Que tipo de ativo você quer na carteira?",
        [
            "📈 Apenas Ações",
            "🏢 Apenas FIIs (Fundos Imobiliários)",
            "🔀 Misto (Ações + FIIs — **Recomendado**)"
        ],
        index=2
    )
    tipo_map = {"📈": "acoes", "🏢": "fiis", "🔀": "misto"}
    tipo_valor = tipo_map.get(tipo_ativo[:2], "misto")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            voltar()
            st.rerun()
    with col2:
        if st.button("🧠 Gerar Sugestão via IA ➡️", use_container_width=True):
            respostas["valor_disponivel"] = valor
            respostas["meta_dividendos"] = meta_dy
            respostas["frequencia"] = frequencia[0]
            respostas["tipo_ativo"] = tipo_valor

            with st.spinner("🧠 O Gemini está analisando seu perfil e montando uma carteira ideal..."):
                configurar_gemini()
                sugestao = gerar_sugestao_onboarding(respostas)
                st.session_state.onboarding_sugestao = sugestao

            avancar()
            st.rerun()

# ---------------------------------------------------------------------------
# PASSO 5: Sugestão da IA + Confirmação
# ---------------------------------------------------------------------------
elif step == 5:
    st.markdown("### 🧠 Sugestão da IA")

    sugestao = st.session_state.onboarding_sugestao

    if not sugestao or not sugestao.get("ativos"):
        st.error("Erro ao gerar sugestão. Tente novamente.")
        if st.button("⬅️ Voltar", use_container_width=True):
            voltar()
            st.rerun()
        st.stop()

    st.success(f"**Resumo:** {sugestao['resumo']}")

    st.markdown("#### 📊 Ativos Sugeridos")

    valor_total = respostas.get("valor_disponivel", 5000)

    for ativo in sugestao["ativos"]:
        ticker = ativo.get("ticker", "")
        tipo = ativo.get("tipo", "Ação")
        alocacao = ativo.get("alocacao", 0)
        motivo = ativo.get("motivo", "")
        valor_alocado = valor_total * (alocacao / 100) if alocacao > 0 else 0

        # Buscar preço atual
        preco_info = buscar_preco_atual(ticker)
        preco = preco_info["preco_atual"] if preco_info else 0

        col1, col2, col3, col4 = st.columns([2, 1, 1, 3])
        with col1:
            st.markdown(f"**{ticker}** ({tipo})")
        with col2:
            st.markdown(f"Alocação: {alocacao}%")
        with col3:
            if preco > 0:
                qtd_sugerida = int(valor_alocado / preco)
                st.markdown(f"~{qtd_sugerida} cotas")
                ativo["_preco"] = preco
                ativo["_qtd"] = max(1, qtd_sugerida)
            else:
                st.markdown("Preço: N/A")
                ativo["_preco"] = 0
                ativo["_qtd"] = 0
        with col4:
            st.markdown(f"_{motivo}_")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar e Refazer", use_container_width=True):
            voltar()
            st.rerun()

    with col2:
        if st.button(
            "✅ Confirmar e Criar Carteira",
            use_container_width=True,
            type="primary"
        ):
            with st.spinner("Criando sua carteira..."):
                # 1. Criar Persona
                persona = criar_persona(
                    user_id=user["id"],
                    nome=respostas.get("nome_persona", "Minha Carteira"),
                    frequencia=respostas.get("frequencia", "semanal"),
                    tolerancia_risco=respostas.get("tolerancia_risco", 5),
                    estilo=respostas.get("estilo", "dividendos")
                )

                # 2. Criar Portfolio
                portfolio = criar_portfolio(
                    persona_id=persona["id"],
                    nome=f"Carteira {respostas.get('nome_persona', 'Inicial')}",
                    objetivo_prazo=respostas.get("objetivo_prazo", "longo"),
                    meta_dividendos=respostas.get("meta_dividendos", 6.0),
                    tipo_ativo=respostas.get("tipo_ativo", "misto"),
                    montante_disponivel=respostas.get("valor_disponivel", 0)
                )

                # 3. Adicionar ativos sugeridos
                ativos_adicionados = 0
                for ativo in sugestao["ativos"]:
                    preco = ativo.get("_preco", 0)
                    qtd = ativo.get("_qtd", 0)
                    if preco > 0 and qtd > 0:
                        adicionar_ativo(
                            portfolio_id=portfolio["id"],
                            ticker=ativo["ticker"],
                            preco_medio=preco,
                            quantidade=qtd
                        )
                        ativos_adicionados += 1

            st.session_state.onboarding_completo = True
            st.session_state.onboarding_step = 6
            st.rerun()

# ---------------------------------------------------------------------------
# PASSO 6: Conclusão
# ---------------------------------------------------------------------------
elif step >= 6:
    st.balloons()
    st.markdown("### 🎉 Parabéns! Sua carteira foi criada!")

    st.markdown(f"""
    **Resumo do que foi criado:**
    
    - 🧑 **Persona:** {respostas.get('nome_persona', '')}
    - 📊 **Tolerância a Risco:** {respostas.get('tolerancia_risco', 5)}/10
    - 💰 **Estilo:** {respostas.get('estilo', 'dividendos').capitalize()}
    - ⏳ **Prazo:** {respostas.get('objetivo_prazo', 'longo').capitalize()}
    
    **Próximos passos:**
    1. Vá para **📊 Dashboard** para ver sua carteira
    2. Acesse **🧠 Recomendações** para gerar análises da IA
    3. Adicione mais ativos manualmente em **💼 Carteiras**
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Ir para o Dashboard", use_container_width=True):
            st.switch_page("pages/1_📊_Dashboard.py")
    with col2:
        if st.button("🔄 Fazer outro Onboarding", use_container_width=True):
            st.session_state.onboarding_step = 0
            st.session_state.onboarding_respostas = {}
            st.session_state.onboarding_sugestao = None
            st.session_state.onboarding_completo = False
            st.rerun()
