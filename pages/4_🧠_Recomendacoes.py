"""
🧠 Recomendações - Motor de IA e Ações Planejadas
====================================================

Esta página é o coração operacional do sistema:
1. Gera recomendações via IA (Gemini + indicadores técnicos + sentimento)
2. Mostra scores com contexto (X de 100) e interpretação visual
3. Exibe indicadores técnicos com explicações detalhadas
4. Gerencia ações planejadas com máquina de estados
5. Detecta e processa atrasos automaticamente
6. Datas no formato brasileiro (dd/mm/aaaa)
"""

import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.crud import (
    listar_personas_usuario, listar_portfolios_persona,
    listar_ativos_portfolio, listar_acoes_portfolio,
    registrar_transacao, adicionar_ativo, atualizar_ativo,
    buscar_persona_por_id, buscar_portfolio_por_id
)
from services.recommendation import gerar_recomendacoes_portfolio, gerar_recomendacao_completa
from services.ai_brain import gerar_sugestoes_compra
from services.state_machine import (
    verificar_acoes_atrasadas, processar_atrasos,
    executar_acao, ignorar_acao, obter_resumo_estados
)
from utils.helpers import (
    formatar_moeda, formatar_data_br,
    interpretar_score, emoji_status, emoji_acao,
    explicar_rsi, explicar_tendencia,
    nome_ativo
)

st.set_page_config(page_title="🧠 Recomendações", page_icon="🧠", layout="wide")

# Verificar login
if "user" not in st.session_state or st.session_state.user is None:
    st.warning("⚠️ Faça login na página principal primeiro.")
    st.stop()

user = st.session_state.user

st.markdown("# 🧠 Motor de Recomendações")
st.markdown("*Análises inteligentes com IA para seus investimentos*")
st.markdown("---")

# Buscar personas e portfolios
personas = listar_personas_usuario(user["id"])

if not personas:
    st.warning("Crie uma Persona e Carteira primeiro.")
    st.stop()

# ---------------------------------------------------------------------------
# Seleção de Persona e Carteira
# ---------------------------------------------------------------------------
col_sel1, col_sel2 = st.columns(2)

with col_sel1:
    persona_nomes = [p["nome"] for p in personas]
    persona_idx = st.selectbox("Persona:", range(len(personas)),
                               format_func=lambda i: persona_nomes[i])
    persona = personas[persona_idx]

portfolios = listar_portfolios_persona(persona["id"])

if not portfolios:
    st.warning(f"A persona '{persona['nome']}' não tem carteiras. Crie uma em 💼 Carteiras.")
    st.stop()

with col_sel2:
    port_nomes = [p["nome"] for p in portfolios]
    port_idx = st.selectbox("Carteira:", range(len(portfolios)),
                            format_func=lambda i: port_nomes[i])
    portfolio = portfolios[port_idx]

st.markdown("---")

# ---------------------------------------------------------------------------
# Verificar Atrasos (automático)
# ---------------------------------------------------------------------------
atrasadas = verificar_acoes_atrasadas()
if atrasadas:
    st.markdown("### ⚠️ Ações Atrasadas Detectadas")
    st.warning(f"**{len(atrasadas)}** ação(ões) ultrapassaram a data planejada!")

    for a in atrasadas:
        st.markdown(
            f"- **{a['asset_ticker']}**: {a['tipo_acao'].upper()} planejado para "
            f"{formatar_data_br(a['data_planejada'])} ({a['dias_atraso']} dias de atraso)"
        )

    if st.button("🔄 Recalcular Todas as Ações Atrasadas", use_container_width=True):
        with st.spinner("🧠 IA recalculando com preços atuais..."):
            resultados = processar_atrasos()

        if resultados:
            st.success(f"✅ {len(resultados)} ação(ões) recalculada(s)!")
            for r in resultados:
                urgencia_icon = emoji_urgencia(r["urgencia"])
                st.markdown(f"""
                ---
                {urgencia_icon} **{r['ticker']}**
                - Ação original: {r['tipo_original'].upper()}
                - Preço original: {formatar_moeda(r['preco_original'])}
                - Preço atual: {formatar_moeda(r['preco_atual'])} ({r['variacao']:+.2f}%)
                - **Nova recomendação: {r['nova_recomendacao'].upper()}**
                - 💬 {r['explicacao']}
                """)
        else:
            st.info("Nenhuma ação pôde ser recalculada.")

    st.markdown("---")


# ---------------------------------------------------------------------------
# Função auxiliar que exibe score com contexto
# ---------------------------------------------------------------------------
def _mostrar_score_com_contexto(label: str, valor: float, col):
    """Exibe um score com contexto visual (X de 100, emoji, cor)."""
    info = interpretar_score(valor)
    with col:
        st.metric(label, f"{valor:.0f}/100")
        st.markdown(f"{info['emoji']} **{info['texto']}**")


# ---------------------------------------------------------------------------
# Função auxiliar (definida ANTES de ser chamada)
# ---------------------------------------------------------------------------
def _mostrar_recomendacao(rec):
    """Exibe um card de recomendação com detalhes explicativos."""
    if not rec.get("sucesso"):
        return

    ticker = rec["ticker"]
    scores = rec["scores"]
    recom = rec["recomendacao"]
    acao_emoji = emoji_acao(recom["acao"])

    # Card visual
    with st.container():
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            st.markdown(f"### {acao_emoji} {ticker}")
            st.markdown(f"**{formatar_moeda(rec['preco_atual'])}**")
            st.markdown(f"Ação: **{recom['acao'].upper()}**")

        with col2:
            st.markdown("**📊 Scores** *(cada score vai de 0 a 100)*")
            score_col1, score_col2, score_col3, score_col4 = st.columns(4)
            _mostrar_score_com_contexto("Técnico", scores['tecnico'], score_col1)
            _mostrar_score_com_contexto("Sentimento", scores['sentimento'], score_col2)
            _mostrar_score_com_contexto("Perfil", scores['perfil'], score_col3)
            _mostrar_score_com_contexto("⭐ Final", scores['final'], score_col4)

        with col3:
            conf_info = interpretar_score(recom['confianca'])
            st.markdown(f"**Confiança:** {recom['confianca']:.0f}% {conf_info['emoji']}")
            st.progress(recom["confianca"] / 100)
            if rec.get("proxima_data"):
                st.markdown(f"📅 Próxima ação: {formatar_data_br(rec['proxima_data'])}")

        st.markdown("**💬 Análise da IA:**")
        st.info(recom["explicacao"])

        # Indicadores Técnicos DETALHADOS
        with st.expander("📈 Indicadores Técnicos (com explicações)"):
            ind = rec.get("indicadores", {})
            
            st.markdown("##### O que são indicadores técnicos?")
            st.markdown(
                "Indicadores técnicos são ferramentas matemáticas baseadas no histórico de preços. "
                "Eles ajudam a identificar tendências e pontos de entrada/saída."
            )
            st.markdown("---")

            # RSI
            rsi_val = ind.get('rsi', 0)
            st.markdown(f"**🔄 RSI (Índice de Força Relativa)**")
            st.markdown(explicar_rsi(rsi_val))
            st.markdown(
                "ℹ️ *RSI mede a velocidade e magnitude dos movimentos de preço nos últimos 14 dias. "
                "Escala: 0-100. Abaixo de 30 = oportunidade de compra. Acima de 70 = possível venda.*"
            )
            st.progress(min(rsi_val / 100, 1.0))
            st.markdown("---")

            # SMA (Médias Móveis)
            sma_20 = ind.get('sma_20', 0)
            sma_50 = ind.get('sma_50', 0)
            preco = ind.get('preco_atual', 0)
            st.markdown(f"**📊 Médias Móveis (SMA)**")
            st.markdown(explicar_tendencia(
                ind.get('tendencia', 'neutra'), preco, sma_20
            ))
            st.markdown(f"- SMA 20 (curto prazo): {formatar_moeda(sma_20)}")
            st.markdown(f"- SMA 50 (médio prazo): {formatar_moeda(sma_50)}")
            st.markdown(
                "ℹ️ *SMA = Simple Moving Average. Quando o preço está acima da SMA, "
                "geralmente indica tendência de alta. SMA20 é mais sensível, SMA50 mais estável.*"
            )
            st.markdown("---")

            # MACD
            macd_val = ind.get('macd', 0)
            macd_signal = ind.get('macd_signal', 0)
            if macd_val and macd_signal:
                diferenca = macd_val - macd_signal
                if diferenca > 0:
                    macd_txt = f"📈 **Positivo** — MACD ({macd_val:.4f}) acima do Signal ({macd_signal:.4f}): momento de compra"
                else:
                    macd_txt = f"📉 **Negativo** — MACD ({macd_val:.4f}) abaixo do Signal ({macd_signal:.4f}): momento de venda"
            else:
                macd_txt = "⚖️ MACD indisponível"
            
            st.markdown(f"**📉 MACD (Convergência/Divergência)**")
            st.markdown(macd_txt)
            st.markdown(
                "ℹ️ *MACD compara duas médias móveis. Quando o MACD cruza acima do Signal, "
                "é sinal de compra. Quando cruza abaixo, sinal de venda.*"
            )

        # Sentimento
        with st.expander("📰 Análise de Sentimento"):
            sent = rec.get("sentimento", {})
            score_sent = sent.get('score', 0)
            
            # Interpretar score de sentimento
            if score_sent > 0.3:
                sent_emoji = "🟢"
                sent_txt = "Positivo"
            elif score_sent < -0.3:
                sent_emoji = "🔴"
                sent_txt = "Negativo"
            else:
                sent_emoji = "🟡"
                sent_txt = "Neutro"
            
            st.markdown(f"**Score:** {score_sent:+.2f} (escala: -1.0 a +1.0) | {sent_emoji} {sent_txt}")
            st.markdown(
                "ℹ️ *O score de sentimento analisa notícias recentes usando IA. "
                "-1.0 = muito negativo, 0 = neutro, +1.0 = muito positivo.*"
            )
            st.markdown(f"**Resumo:** {sent.get('resumo', 'N/A')}")
            
            noticias = rec.get("noticias", [])
            if noticias:
                st.markdown("**📰 Notícias recentes:**")
                for n in noticias:
                    st.markdown(f"- [{n['titulo']}]({n['link']}) — {formatar_data_br(n.get('data', ''))}")


# ---------------------------------------------------------------------------
# Gerar Novas Recomendações
# ---------------------------------------------------------------------------
st.markdown("### 🎯 Gerar Recomendações")

ativos = listar_ativos_portfolio(portfolio["id"])

if not ativos:
    st.info("Esta carteira não tem ativos. Adicione ativos em 💼 Carteiras.")
else:
    st.markdown(f"**Ativos na carteira:** {', '.join(a['ticker'] for a in ativos)}")
    
    # Mostrar montante disponível
    if portfolio.get("montante_disponivel", 0) > 0:
        st.markdown(f"💰 **Caixa disponível:** {formatar_moeda(portfolio['montante_disponivel'])}")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        gerar_todos = st.button(
            "🚀 Gerar Recomendações para Todos",
            use_container_width=True
        )

    with col_btn2:
        ticker_especifico = st.selectbox(
            "Ou analise um ativo específico:",
            [""] + [a["ticker"] for a in ativos]
        )
        gerar_um = st.button("🔍 Analisar", use_container_width=True) if ticker_especifico else False

    if gerar_todos:
        with st.spinner("🧠 Analisando todos os ativos... Isso pode levar alguns minutos."):
            try:
                recomendacoes = gerar_recomendacoes_portfolio(
                    portfolio_id=portfolio["id"],
                    persona_id=persona["id"]
                )
            except Exception as e:
                recomendacoes = []
                st.error(f"⚠️ Erro ao gerar recomendações: {str(e)}")

        if recomendacoes:
            st.success(f"✅ {len(recomendacoes)} recomendação(ões) gerada(s)!")
            for rec in recomendacoes:
                _mostrar_recomendacao(rec)
        elif not recomendacoes:
            st.warning("Nenhuma recomendação gerada. Tente novamente em alguns instantes.")

    if gerar_um and ticker_especifico:
        with st.spinner(f"🧠 Analisando {ticker_especifico}..."):
            try:
                rec = gerar_recomendacao_completa(
                    ticker=ticker_especifico,
                    persona_id=persona["id"],
                    portfolio_id=portfolio["id"]
                )
            except Exception as e:
                rec = {"sucesso": False, "erro": str(e)}
                st.error(f"⚠️ Erro: {str(e)}")

        if rec.get("sucesso"):
            _mostrar_recomendacao(rec)
        else:
            st.error(f"Erro: {rec.get('erro', 'Desconhecido')}")

st.markdown("---")

# ---------------------------------------------------------------------------
# Histórico de Ações Planejadas
# ---------------------------------------------------------------------------
st.markdown("### 📋 Ações Planejadas")

# Resumo de estados
resumo = obter_resumo_estados(portfolio["id"])
col_r1, col_r2, col_r3, col_r4 = st.columns(4)
with col_r1:
    st.metric("📋 Planejadas", resumo["planejado"])
with col_r2:
    st.metric("✅ Executadas", resumo["executado"])
with col_r3:
    st.metric("⚠️ Em Revisão", resumo["revisao_necessaria"])
with col_r4:
    st.metric("❌ Ignoradas", resumo["ignorado"])

# Filtro de status
filtro = st.selectbox(
    "Filtrar por status:",
    ["todos", "planejado", "executado", "revisao_necessaria", "ignorado"],
    format_func=lambda x: {
        "todos": "📊 Todos",
        "planejado": "📋 Planejados",
        "executado": "✅ Executados",
        "revisao_necessaria": "⚠️ Em Revisão",
        "ignorado": "❌ Ignorados"
    }.get(x, x)
)

# Listar ações
if filtro == "todos":
    acoes = listar_acoes_portfolio(portfolio["id"])
else:
    acoes = listar_acoes_portfolio(portfolio["id"], status=filtro)

if acoes:
    for acao in acoes:
        status_emoji = emoji_status(acao["status"])
        tipo_emoji = emoji_acao(acao["tipo_acao"])

        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                score_info = interpretar_score(acao['pontuacao'])
                st.markdown(
                    f"{status_emoji} {tipo_emoji} **{acao['asset_ticker']}** — "
                    f"{acao['tipo_acao'].upper()} | "
                    f"Score: {acao['pontuacao']:.0f}/100 {score_info['emoji']} | "
                    f"Data: {formatar_data_br(acao['data_planejada'])}"
                )

                if acao.get("explicacao"):
                    explicacao_txt = acao['explicacao']
                    if len(explicacao_txt) > 200:
                        explicacao_txt = explicacao_txt[:200] + "..."
                    st.markdown(f"💬 _{explicacao_txt}_")

                if acao.get("explicacao_revisao"):
                    st.markdown(f"🔄 **Revisão:** _{acao['explicacao_revisao']}_")

                if acao.get("preco_alvo"):
                    preco_txt = f"Preço original: {formatar_moeda(acao['preco_alvo'])}"
                    if acao.get("preco_revisado"):
                        preco_txt += f" → Revisado: {formatar_moeda(acao['preco_revisado'])}"
                    st.markdown(preco_txt)

            # Botões de ação (só para pendentes)
            if acao["status"] in ("planejado", "revisao_necessaria"):
                with col2:
                    if st.button("✅ Executei", key=f"exec_{acao['id']}"):
                        executar_acao(acao["id"])
                        st.toast("Ação marcada como executada! ✅")
                        st.rerun()

                with col3:
                    if st.button("❌ Ignorar", key=f"ign_{acao['id']}"):
                        ignorar_acao(acao["id"])
                        st.toast("Ação ignorada.")
                        st.rerun()

            st.markdown("---")
else:
    st.info("Nenhuma ação encontrada com esse filtro.")

# ---------------------------------------------------------------------------
# Sugestões de Compra via IA
# ---------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 💡 Sugestões de Compra")
st.markdown(
    "*A IA analisa seu perfil e carteira atual para sugerir novos ativos "
    "ou reforço de posições existentes, respeitando seu caixa disponível.*"
)

montante_disp = portfolio.get("montante_disponivel", 0)
st.markdown(f"💰 **Caixa disponível:** {formatar_moeda(montante_disp)}")

if montante_disp <= 0:
    st.warning("⚠️ Sem caixa disponível. Registre um aporte na página 📜 Extrato para receber sugestões.")
else:
    if st.button("💡 Gerar Sugestões de Compra", use_container_width=True, key="btn_sugestoes"):
        with st.spinner("🧠 A IA está analisando oportunidades para sua carteira..."):
            try:
                persona_info = buscar_persona_por_id(persona["id"])
                portfolio_info = buscar_portfolio_por_id(portfolio["id"])
                resultado = gerar_sugestoes_compra(
                    ativos_atuais=ativos,
                    persona_info=persona_info,
                    portfolio_info=portfolio_info
                )
            except Exception as e:
                resultado = {"sucesso": False, "resumo": str(e), "sugestoes": []}

        if resultado.get("sucesso") and resultado.get("sugestoes"):
            st.success(f"✅ {len(resultado['sugestoes'])} sugestão(ões) encontrada(s)!")
            st.info(f"💬 {resultado['resumo']}")

            # Guardar sugestões no session_state para os botões funcionarem
            st.session_state["sugestoes_compra"] = resultado["sugestoes"]

    # Renderizar sugestões (inclusive após rerun)
    if "sugestoes_compra" in st.session_state and st.session_state["sugestoes_compra"]:
        for i, sug in enumerate(st.session_state["sugestoes_compra"]):
            tipo_badge = "🆕" if "novo" in sug.get("tipo", "").lower() else "🔄"
            valor_est = sug.get("valor_total", 0)
            qtd = sug.get("quantidade", 0)
            preco = sug.get("preco_estimado", 0)
            ticker = sug.get("ticker", "")
            nome = nome_ativo(ticker)

            col_s1, col_s2 = st.columns([4, 1])
            with col_s1:
                st.markdown(
                    f"{tipo_badge} **{ticker}** — _{nome}_ | "
                    f"{sug.get('tipo', 'Novo')} | "
                    f"Qtd: {qtd} | "
                    f"Preço est.: {formatar_moeda(preco)} | "
                    f"Total: {formatar_moeda(valor_est)}"
                )
                if sug.get("motivo"):
                    st.markdown(f"   💬 _{sug['motivo']}_")
            with col_s2:
                if st.button("✅ Seguir", key=f"seguir_sug_{i}", use_container_width=True):
                    # Executar a compra sugerida
                    try:
                        # Checar caixa
                        port_atualizado = buscar_portfolio_por_id(portfolio["id"])
                        caixa = port_atualizado.get("montante_disponivel", 0)
                        if valor_est > caixa:
                            st.error(f"Caixa insuficiente! Disponível: {formatar_moeda(caixa)}")
                        else:
                            # Verificar se ativo já existe
                            ativos_atuais = listar_ativos_portfolio(portfolio["id"])
                            existente = next((a for a in ativos_atuais if a["ticker"] == ticker), None)

                            if existente:
                                qtd_antiga = existente["quantidade"]
                                pm_antigo = existente["preco_medio"]
                                nova_qtd = qtd_antiga + qtd
                                novo_pm = ((pm_antigo * qtd_antiga) + (preco * qtd)) / nova_qtd
                                atualizar_ativo(existente["id"], quantidade=nova_qtd, preco_medio=round(novo_pm, 2))
                            else:
                                adicionar_ativo(portfolio["id"], ticker, preco, qtd)

                            registrar_transacao(
                                portfolio_id=portfolio["id"],
                                tipo="compra",
                                valor=valor_est,
                                ticker=ticker,
                                quantidade=qtd,
                                preco_unitario=preco,
                                descricao=f"Sugestão IA: {sug.get('motivo', 'Compra sugerida')}",
                                origem="ia"
                            )
                            st.toast(f"Compra de {qtd}x {ticker} ({nome}) executada! 🚀")
                            st.session_state["sugestoes_compra"] = None
                            st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao executar: {e}")
    elif "sugestoes_compra" not in st.session_state:
        st.caption("Clique no botão acima para gerar sugestões personalizadas.")
