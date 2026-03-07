"""
app.py - Ponto de Entrada Principal da Aplicação
==================================================

Conceito de Eng. Software: Single Entry Point
Todo o app Streamlit inicia por aqui. Responsabilidades:
1. Inicializar o banco de dados
2. Configurar a API Gemini
3. Gerenciar sessão do usuário (com senha)
4. Prover a navegação lateral (sidebar)
5. Homepage (landing page) para novos visitantes
"""

import streamlit as st
import hashlib
import os
import sys

# Adicionar o diretório raiz ao path para imports funcionarem
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import init_db
from database.crud import (
    listar_usuarios, criar_usuario, buscar_usuario_por_email,
    listar_personas_usuario, listar_portfolios_persona, listar_ativos_portfolio,
    listar_watchlist_usuario
)
from services.ai_brain import configurar_gemini
from services.market_data import buscar_preco_atual
from utils.helpers import formatar_data_br, formatar_moeda, formatar_moeda_md, nome_ativo

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA (Apenas UMA vez e no início do script)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="🏠 Início",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# CSS Customizado - Design premium com gradientes e glassmorphism
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
    
    /* Reset & Base */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f2 50%, #f0f2f5 100%);
        font-family: 'Inter', sans-serif;
    }

    /* Ocultar páginas auxiliares do sidebar */
    [data-testid="stSidebarNav"] a[href*="Carteira_Detalhe"],
    [data-testid="stSidebarNav"] a[href*="Ativo"],
    [data-testid="stSidebarNav"] a[href*="Persona_Detalhe"],
    [data-testid="stSidebarNav"] li:has(a[href*="Carteira_Detalhe"]),
    [data-testid="stSidebarNav"] li:has(a[href*="Ativo"]),
    [data-testid="stSidebarNav"] li:has(a[href*="Persona_Detalhe"]) {
        display: none !important;
    }
    
    /* Renomear "app" para "🏠 Início" no sidebar */
    [data-testid="stSidebarNav"] > ul > li:first-child a span {
        visibility: hidden;
        position: relative;
    }
    [data-testid="stSidebarNav"] > ul > li:first-child a span::after {
        content: "🏠 Início";
        visibility: visible;
        position: absolute;
        left: 0;
    }

    /* ============ HOMEPAGE STYLES ============ */

    /* Hero Section */
    .hero-section {
        text-align: center;
        padding: 1.5rem 1rem 1rem;
    }

    .hero-logo {
        font-size: 3rem;
        margin-bottom: 0.2rem;
        animation: float 3s ease-in-out infinite;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
    }

    .hero-title {
        font-family: 'Inter', sans-serif;
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -1px;
        margin-bottom: 0.3rem;
        line-height: 1.1;
    }

    .hero-slogan {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        font-weight: 300;
        color: #667eea;
        margin-bottom: 0.5rem;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    .hero-description {
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        color: #555;
        max-width: 600px;
        margin: 0 auto 1rem;
        line-height: 1.5;
    }

    /* Feature Cards */
    .feature-card {
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.6);
        border-radius: 16px;
        padding: 1.2rem 1rem;
        text-align: center;
        transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
        height: 100%;
    }

    .feature-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
        border-color: rgba(102, 126, 234, 0.3);
    }

    .feature-icon {
        font-size: 3rem;
        margin-bottom: 0.8rem;
        display: block;
    }

    .feature-card h3 {
        font-family: 'Inter', sans-serif;
        font-size: 1.2rem;
        font-weight: 700;
        color: #333;
        margin-bottom: 0.5rem;
    }

    .feature-card p {
        font-family: 'Inter', sans-serif;
        font-size: 0.95rem;
        color: #666;
        line-height: 1.6;
    }

    /* Steps Section */
    .steps-section {
        text-align: center;
        padding: 2rem 0;
    }

    .section-title {
        font-family: 'Inter', sans-serif;
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }

    .section-subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 1.05rem;
        color: #777;
        margin-bottom: 2rem;
    }

    .step-card {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
        border: 1px solid rgba(102, 126, 234, 0.15);
        border-radius: 20px;
        padding: 2rem 1.5rem;
        text-align: center;
        position: relative;
    }

    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 800;
        font-size: 1rem;
        margin-bottom: 0.5rem;
        font-family: 'Inter', sans-serif;
    }

    .step-card h4 {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        font-weight: 700;
        color: #333;
        margin-bottom: 0.4rem;
    }

    .step-card p {
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        color: #666;
        line-height: 1.5;
    }

    /* Stats Bar */
    .stats-bar {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 1.2rem;
        display: flex;
        justify-content: space-around;
        margin: 1rem 0;
    }

    .stat-item {
        text-align: center;
        color: white;
    }

    .stat-value {
        font-family: 'Inter', sans-serif;
        font-size: 1.6rem;
        font-weight: 800;
        display: block;
    }

    .stat-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        font-weight: 400;
        opacity: 0.85;
    }

    /* Differentials */
    .diff-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid rgba(0,0,0,0.06);
        box-shadow: 0 2px 12px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
    }

    .diff-card:hover {
        box-shadow: 0 6px 24px rgba(102, 126, 234, 0.12);
    }

    .diff-card .diff-icon {
        font-size: 1.8rem;
        margin-bottom: 0.5rem;
        display: block;
    }

    .diff-card h4 {
        font-family: 'Inter', sans-serif;
        font-size: 1rem;
        font-weight: 700;
        color: #333;
        margin-bottom: 0.3rem;
    }

    .diff-card p {
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        color: #777;
        line-height: 1.4;
    }

    /* Footer */
    .footer {
        text-align: center;
        padding: 2rem 0 1rem;
        color: #999;
        font-size: 0.85rem;
        border-top: 1px solid rgba(0,0,0,0.06);
        margin-top: 2rem;
    }

    .footer a {
        color: #667eea;
        text-decoration: none;
    }

    /* ============ APP-WIDE STYLES ============ */

    /* Cards/containers */
    .stMetric {
        background: rgba(255, 255, 255, 0.85);
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f5f7fa 100%);
        border-right: 1px solid rgba(0, 0, 0, 0.08);
    }
    
    /* Botões - gradiente roxo/azul */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* Header customizado */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        color: #555;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Cards de métricas */
    .metric-card {
        background: white;
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
    }
    
    .metric-card h3 {
        color: #666;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Tabelas */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.7);
        border-radius: 8px;
    }
    
    /* Divider */
    hr {
        border-color: rgba(0, 0, 0, 0.08);
    }
    
    /* Score badges */
    .score-high { color: #00C851; font-weight: bold; }
    .score-mid { color: #FFB300; font-weight: bold; }
    .score-low { color: #FF4444; font-weight: bold; }
    
    /* Alerta de ação atrasada */
    .alert-delay {
        background: rgba(255, 68, 68, 0.08);
        border: 1px solid rgba(255, 68, 68, 0.2);
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }

    /* ============ FIX 4: DROPDOWNS NÃO-EDITÁVEIS ============ */
    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        cursor: pointer !important;
        pointer-events: none !important;
    }
    div[data-baseweb="select"] {
        cursor: pointer !important;
    }
    div[data-baseweb="select"] input::placeholder {
        color: #666 !important;
    }

    /* ============ FIX 5: HEADERS E MÉTRICAS ============ */

    /* Headers */
    h1, .main-header {
        font-size: 1.4rem !important;
    }
    h2 {
        font-size: 2rem !important;
    }
    h3 {
        font-size: 1rem !important;
    }
    h4 {
        font-size: 0.9rem !important;
    }

    /* Métricas (st.metric) — valores de destaque */
    [data-testid="stMetricLabel"] {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] > div {
        font-size: 1.82rem !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.82rem !important;
        font-weight: 800 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.72rem !important;
    }

    /* Nomes de carteiras e personas nos cards */
    .metric-card .value {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }

    /* Fonte base — tamanho original */
    .stApp p, .stApp li, .stApp span {
        font-size: 0.88rem;
    }
    .stApp .stCaption, .stApp caption {
        font-size: 0.72rem !important;
    }

    /* Dividers */
    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Inicialização (roda apenas uma vez na sessão)
# ---------------------------------------------------------------------------
@st.cache_resource
def setup():
    """Inicializa banco e configura API. Roda apenas 1x."""
    try:
        init_db()
    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {e}"
        full_tb = traceback.format_exc()
        print(f"[setup] ERRO COMPLETO DE CONEXÃO:\n{full_tb}")
        # Mostra o erro real na UI do Streamlit (não redactado)
        st.error(f"❌ **Erro ao conectar ao banco de dados:**\n\n`{error_msg}`")
        st.code(full_tb, language="text")
        st.info(
            "💡 **Possíveis causas:**\n"
            "- DATABASE_URL incorreta nos Secrets\n"
            "- Banco de dados pausado (Supabase free tier)\n"
            "- Senha ou host incorretos\n"
            "- Firewall bloqueando a conexão"
        )
        st.stop()
    gemini_ok = configurar_gemini()
    return gemini_ok


gemini_configurado = setup()


# ---------------------------------------------------------------------------
# Gerenciamento de Sessão do Usuário
# ---------------------------------------------------------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "home"


def sidebar_info():
    """Mostra informações na sidebar."""
    with st.sidebar:
        st.markdown("### 🧪 EgoLab")
        st.caption("_Teste versões. Invista melhor._")
        st.markdown("---")

        if st.session_state.user:
            user = st.session_state.user
            st.markdown(f"👤 **{user['nome']}**")
            st.markdown(f"📧 {user['email']}")
            st.markdown("---")

            # Status da API
            if gemini_configurado:
                st.success("🧠 Gemini IA: Conectado", icon="✅")
            else:
                st.warning("🧠 Gemini IA: Sem chave API", icon="⚠️")

            st.markdown("---")
            st.markdown("### 📌 Navegação")
            st.markdown("""
            - 📊 **Dashboard** - Visão geral
            - 🧑 **Personas** - Perfis
            - 💼 **Carteiras** - Ativos
            - 🧠 **Recomendações** - IA
            - 📜 **Extrato** - Movimentações
            - 📥 **Onboarding** - Setup
            """)

            # Mini-resumo de patrimônio
            try:
                total_ativos = 0
                total_caixa = 0.0
                for p in listar_personas_usuario(user['id']):
                    for port in listar_portfolios_persona(p['id']):
                        total_caixa += port.get('montante_disponivel', 0)
                        ativos = listar_ativos_portfolio(port['id'])
                        total_ativos += len(ativos)
                if total_ativos > 0 or total_caixa > 0:
                    st.markdown("---")
                    st.markdown("### 💰 Resumo")
                    st.markdown(f"📊 **{total_ativos}** ativos")
                    st.markdown(f"💵 Caixa: **{formatar_moeda_md(total_caixa)}**", unsafe_allow_html=True)
            except Exception:
                pass

            st.markdown("---")
            if st.button("🚪 Trocar Usuário", use_container_width=True):
                st.session_state.user = None
                st.session_state.page = "home"
                st.rerun()
        else:
            st.info("Faça login ou crie uma conta para começar.")


# ---------------------------------------------------------------------------
# HOMEPAGE — Landing Page premium
# ---------------------------------------------------------------------------
def tela_homepage():
    """Homepage / Landing page com design premium."""

    # --- Hero Section ---
    st.markdown("""
    <div class="hero-section">
        <div class="hero-logo">🧪</div>
        <div class="hero-title">EgoLab</div>
        <div class="hero-slogan">Teste versões. Invista melhor.</div>
        <div class="hero-description">
            Crie <strong>múltiplas personas</strong> de investimento, monte 
            <strong>carteiras inteligentes</strong> e receba 
            <strong>recomendações com IA</strong> — tudo em um só lugar.
            Descubra qual versão do seu eu-investidor performa melhor.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- CTA Buttons ---
    col_spacer1, col_cta1, col_cta2, col_spacer2 = st.columns([1, 1.2, 1.2, 1])
    with col_cta1:
        if st.button("🚀 Começar Agora — Grátis", use_container_width=True, key="cta_start"):
            st.session_state.page = "login"
            st.rerun()
    with col_cta2:
        if st.button("🔑 Já tenho conta", use_container_width=True, key="cta_login"):
            st.session_state.page = "login"
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Stats Bar ---
    st.markdown("""
    <div class="stats-bar">
        <div class="stat-item">
            <span class="stat-value">🧑 ∞</span>
            <span class="stat-label">Personas ilimitadas</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">🤖 IA</span>
            <span class="stat-label">Gemini integrado</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">📊 B3</span>
            <span class="stat-label">Dados em tempo real</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">🔒 100%</span>
            <span class="stat-label">Seus dados, seu controle</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Features Section ---
    st.markdown("""
    <div class="steps-section">
        <div class="section-title">O que você pode fazer</div>
        <div class="section-subtitle">Ferramentas poderosas para investidores de todos os perfis</div>
    </div>
    """, unsafe_allow_html=True)

    f1, f2, f3, f4 = st.columns(4)

    with f1:
        st.markdown("""
        <div class="feature-card">
            <span class="feature-icon">🧑</span>
            <h3>Personas de Investimento</h3>
            <p>Crie perfis diferentes — conservador, moderado, arrojado — e teste estratégias em paralelo sem risco.</p>
        </div>
        """, unsafe_allow_html=True)

    with f2:
        st.markdown("""
        <div class="feature-card">
            <span class="feature-icon">💼</span>
            <h3>Carteiras Inteligentes</h3>
            <p>Monte carteiras com ações e FIIs da B3. Configure setores, prazo e meta de dividendos.</p>
        </div>
        """, unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div class="feature-card">
            <span class="feature-icon">🧠</span>
            <h3>Recomendações com IA</h3>
            <p>O Gemini analisa cada ativo com indicadores técnicos e fundamentalistas, gerando ações com score 0-100.</p>
        </div>
        """, unsafe_allow_html=True)

    with f4:
        st.markdown("""
        <div class="feature-card">
            <span class="feature-icon">📊</span>
            <h3>Dashboard em Tempo Real</h3>
            <p>Veja patrimônio, lucro/prejuízo, gráficos de distribuição e histórico de preços ao vivo.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- How it works ---
    st.markdown("""
    <div class="steps-section">
        <div class="section-title">Como Funciona</div>
        <div class="section-subtitle">3 passos simples para começar a investir com inteligência</div>
    </div>
    """, unsafe_allow_html=True)

    s1, s2, s3 = st.columns(3)

    with s1:
        st.markdown("""
        <div class="step-card">
            <div class="step-number">1</div>
            <h4>Crie suas Personas</h4>
            <p>Defina perfis de investimento com tolerância a risco, estilo (dividendos, crescimento ou equilibrado) e frequência de revisão.</p>
        </div>
        """, unsafe_allow_html=True)

    with s2:
        st.markdown("""
        <div class="step-card">
            <div class="step-number">2</div>
            <h4>Monte Carteiras</h4>
            <p>Adicione ações e FIIs da B3. Escolha setores, horizonte de investimento e aporte inicial. O sistema calcula metas automaticamente.</p>
        </div>
        """, unsafe_allow_html=True)

    with s3:
        st.markdown("""
        <div class="step-card">
            <div class="step-number">3</div>
            <h4>Receba Recomendações IA</h4>
            <p>O Gemini analisa cada ativo com dados reais do mercado e gera sugestões de compra, venda ou manutenção com explicações detalhadas.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # --- Differentials ---
    st.markdown("""
    <div class="steps-section">
        <div class="section-title">Por que o EgoLab?</div>
        <div class="section-subtitle">Diferenciais que fazem a diferença</div>
    </div>
    """, unsafe_allow_html=True)

    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.markdown("""
        <div class="diff-card">
            <span class="diff-icon">⚡</span>
            <h4>Onboarding Inteligente</h4>
            <p>Setup guiado que cria personas e carteiras em minutos com ajuda da IA.</p>
        </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown("""
        <div class="diff-card">
            <span class="diff-icon">📜</span>
            <h4>Extrato Completo</h4>
            <p>Rastreie cada movimentação: aportes, compras, vendas e dividendos recebidos.</p>
        </div>
        """, unsafe_allow_html=True)

    with d3:
        st.markdown("""
        <div class="diff-card">
            <span class="diff-icon">🔄</span>
            <h4>Máquina de Estados</h4>
            <p>Ações planejadas passam por estados (planejado → executado) com alertas de atraso.</p>
        </div>
        """, unsafe_allow_html=True)

    with d4:
        st.markdown("""
        <div class="diff-card">
            <span class="diff-icon">📰</span>
            <h4>Notícias do Mercado</h4>
            <p>Monitoramento de notícias relevantes para seus ativos, integrado às recomendações.</p>
        </div>
        """, unsafe_allow_html=True)

    # --- Final CTA ---
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    col_spacer3, col_final_cta, col_spacer4 = st.columns([1, 2, 1])
    with col_final_cta:
        st.markdown("""
        <div style="text-align: center; padding: 1.5rem 0;">
            <div class="section-title" style="font-size: 1.6rem;">Pronto para testar suas estratégias?</div>
            <div class="section-subtitle">Crie sua conta gratuita e comece agora</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🚀 Criar Minha Conta Gratuita", use_container_width=True, key="cta_bottom"):
            st.session_state.page = "login"
            st.rerun()

    # --- Footer ---
    st.markdown("""
    <div class="footer">
        <p>🧪 <strong>EgoLab</strong> — Teste versões. Invista melhor.</p>
        <p>Feito com ❤️ usando Streamlit, Gemini IA e dados da B3</p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Tela de Login/Cadastro (COM SENHA)
# ---------------------------------------------------------------------------
def tela_login():
    """Tela inicial: login ou criação de conta com senha."""
    st.markdown('<p class="main-header">🧪 EgoLab</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Teste versões. Invista melhor.</p>',
        unsafe_allow_html=True
    )

    # Botão voltar para homepage
    if st.button("← Voltar para a Homepage", key="btn_back_home"):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🔑 Entrar")
        email_login = st.text_input("Email:", key="login_email", placeholder="seu@email.com")
        senha_login = st.text_input("Senha:", key="login_senha", type="password")

        if st.button("▶️ Entrar", use_container_width=True, key="btn_login"):
            if not email_login or not senha_login:
                st.error("Preencha email e senha!")
            else:
                user = buscar_usuario_por_email(email_login)
                if user is None:
                    st.error("Email não encontrado! Crie uma conta ao lado →")
                else:
                    senha_hash = hashlib.sha256(senha_login.encode()).hexdigest()
                    if user.get("senha") == senha_hash:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Senha incorreta! ❌")

    with col2:
        st.markdown("### ✨ Criar Conta")
        nome = st.text_input("Nome completo:", key="reg_nome")
        email = st.text_input("Email:", key="reg_email")
        senha = st.text_input("Senha:", key="reg_senha", type="password")
        senha_confirma = st.text_input("Confirmar senha:", key="reg_senha2", type="password")

        if st.button("🚀 Criar Conta", use_container_width=True, key="btn_register"):
            if not nome or not email or not senha:
                st.error("Preencha todos os campos!")
            elif senha != senha_confirma:
                st.error("As senhas não coincidem! ❌")
            elif len(senha) < 4:
                st.error("Senha deve ter no mínimo 4 caracteres!")
            elif buscar_usuario_por_email(email):
                st.error("Email já cadastrado!")
            else:
                user = criar_usuario(nome, email, senha)
                st.session_state.user = user
                st.success(f"Conta criada com sucesso! Bem-vindo, {nome}! 🎉")
                st.rerun()


# ---------------------------------------------------------------------------
# Dashboard Rápido (Página Inicial após Login)
# ---------------------------------------------------------------------------
def tela_principal():
    """Tela principal com resumo rápido após login."""
    user = st.session_state.user

    st.markdown(f'<p class="main-header">Olá, {user["nome"]}! 👋</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Bem-vindo ao EgoLab — seu laboratório de estratégias de investimento</p>',
        unsafe_allow_html=True
    )

    # Buscar dados do usuário
    personas = listar_personas_usuario(user["id"])

    if not personas:
        st.markdown("---")
        st.markdown("### 🚀 Primeiros Passos")
        st.info(
            "Você ainda não configurou nenhuma **Persona** de investimento. "
            "Vá para a página **📥 Onboarding** no menu lateral para começar, "
            "ou crie uma Persona manualmente na página **🧑 Personas**."
        )
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Ir para Onboarding Inteligente", use_container_width=True):
                st.switch_page("pages/5_📥_Onboarding.py")
        with col2:
            if st.button("🧑 Criar Persona Manualmente", use_container_width=True):
                st.switch_page("pages/2_🧑_Personas.py")
    else:
        # Métricas rápidas
        total_personas = len(personas)
        total_portfolios = 0
        total_ativos = 0

        for p in personas:
            portfolios = listar_portfolios_persona(p["id"])
            total_portfolios += len(portfolios)
            for port in portfolios:
                ativos = listar_ativos_portfolio(port["id"])
                total_ativos += len(ativos)

        # CSS local para botões de link nas caixinhas
        st.markdown("""<style>
        div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
            background: none !important; border: none !important;
            color: #667eea !important; padding: 0 4px !important;
            box-shadow: none !important; font-size: 0.82rem !important;
        }
        div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
            text-decoration: underline !important; background: none !important;
        }
        </style>""", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown(f"#### 🧑 Personas ({total_personas})")
                for p in personas:
                    n_ports = len(listar_portfolios_persona(p["id"]))
                    c_pn, c_pb = st.columns([4, 2])
                    with c_pn:
                        st.markdown(f"**{p['nome']}** — {n_ports} carteira(s)")
                    with c_pb:
                        if st.button("Ver detalhes →", key=f"hp_p_{p['id']}"):
                            st.session_state.view_persona_id = p["id"]
                            st.switch_page("pages/_9_🧑_Persona_Detalhe.py")
        with col2:
            with st.container(border=True):
                st.markdown(f"#### 💼 Carteiras ({total_portfolios})")
                for p in personas:
                    for port in listar_portfolios_persona(p["id"]):
                        n_ats = len(listar_ativos_portfolio(port["id"]))
                        c_cn, c_cb = st.columns([4, 2])
                        with c_cn:
                            st.markdown(f"**{port['nome']}** — {n_ats} ativo(s)")
                        with c_cb:
                            if st.button("Ver detalhes →", key=f"hp_c_{port['id']}"):
                                st.session_state.view_portfolio_id = port["id"]
                                st.switch_page("pages/_7_📂_Carteira_Detalhe.py")

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 🔍 Pesquisa de Ativos
    # -----------------------------------------------------------------------
    st.markdown("### 🔍 Pesquisar Ativos")
    st.caption("Busque por código (PETR4) ou nome (Petrobras, Itaú, Vale...)")
    
    col_search, col_btn = st.columns([5, 1])
    with col_search:
        ticker_busca = st.text_input(
            "Digite o código ou nome do ativo", 
            placeholder="Ex: PETR4, Petrobras, Itaú, Vale...", 
            label_visibility="collapsed"
        ).strip()
    with col_btn:
        buscar_direto = st.button("Buscar 🔎", use_container_width=True, type="primary")
    
    if buscar_direto and ticker_busca:
        from utils.helpers import buscar_ativos_por_nome
        resultados = buscar_ativos_por_nome(ticker_busca)
        
        if resultados:
            st.caption(f"📋 {len(resultados)} resultado(s) encontrado(s):")
            cols_res = st.columns(min(len(resultados), 4))
            for i, r in enumerate(resultados[:4]):
                with cols_res[i]:
                    if st.button(f"📄 {r['ticker']}\n{r['nome']}", key=f"sr_{r['ticker']}", use_container_width=True):
                        st.session_state.view_asset_ticker = r['ticker']
                        st.switch_page("pages/_8_📄_Ativo.py")
        else:
            # Tentar buscar diretamente como ticker se não obteve resultado fuzzy
            st.session_state.view_asset_ticker = ticker_busca.upper()
            st.switch_page("pages/_8_📄_Ativo.py")
            
    elif buscar_direto:
        st.toast("Digite um código ou nome válido primeiro", icon="⚠️")
                
    st.markdown("---")

    # -----------------------------------------------------------------------
    # 📈 Destaques do Mercado (Highlights da Bolsa)
    # -----------------------------------------------------------------------
    from services.market_highlights import buscar_highlights_mercado
    from database.crud import adicionar_watchlist

    c_tit1, c_tit2 = st.columns([5, 1])
    with c_tit1:
        st.markdown("### 📈 Destaques do Mercado")
        st.caption("Rankings de ações populares da B3")
    with c_tit2:
        if st.button("🔄 Atualizar Painel", use_container_width=True, key="btn_refresh_destaques", help="Puxa cotações em tempo real da B3"):
            buscar_highlights_mercado.clear()
            st.rerun()

    with st.spinner("🔄 Carregando destaques do mercado..."):
        highlights = buscar_highlights_mercado(_cache_buster=1)

    if highlights:
        # Mostrar toasts de watchlist pendentes (após rerun do popover)
        for key in list(st.session_state.keys()):
            if key.startswith("_wl_added_") and st.session_state[key]:
                ticker_added = key.replace("_wl_added_", "")
                st.toast(f"✅ {ticker_added} adicionado à watchlist!", icon="👀")
                del st.session_state[key]
        
        # Pre-load user portfolios mappings for the quick actions
        todas_carteiras = []
        for p in personas:
            ports = listar_portfolios_persona(p["id"])
            for pt in ports:
                todas_carteiras.append({"id": pt["id"], "nome": f"{pt['nome']} ({p['nome']})"})
                
        # Filtro de Ações ou FIIs
        filtro_destaques = st.radio(
            "Filtrar rankigs por tipo:",
            ["Todos", "Ações", "FIIs"],
            horizontal=True,
            key="filtro_destaques"
        )

        def filtrar_lista(lista):
            if filtro_destaques == "Todos":
                return lista
            return [x for x in lista if x.get("tipo") == filtro_destaques]

        h1, h2, h3, h4 = st.columns(4)

        def _renderizar_card_destaque(item, cor_variacao, prefix, label_extra=""):
            with st.container(border=True):
                col_texto, col_info, col_acao = st.columns([5, 1.5, 1.5])
                with col_texto:
                    lbl = f"<br>{label_extra}" if label_extra else ""
                    st.markdown(
                        f"**{item['ticker']}** "
                        f"<span style='color:{cor_variacao};font-weight:700'>"
                        f"{'+' if item.get('variacao', 0) >= 0 else ''}{item.get('variacao', 0):.2f}%</span><br>"
                        f"<span style='font-size:0.9em'>{formatar_moeda_md(item['preco'])}</span> {lbl}",
                        unsafe_allow_html=True
                    )
                with col_info:
                    if st.button("ℹ️", key=f"hi_info_{prefix}_{item['ticker']}", help="Ver detalhes do ativo"):
                        st.session_state.view_asset_ticker = item['ticker']
                        st.switch_page("pages/_8_📄_Ativo.py")
                with col_acao:
                    with st.popover("⚙️"):
                        if not todas_carteiras:
                            st.warning("Crie carteira.")
                        else:
                            st.markdown(f"**{item['ticker']}**")
                            opt_ports = {c["id"]: c["nome"] for c in todas_carteiras}
                            sel_port = st.selectbox("Carteira:", list(opt_ports.keys()), format_func=lambda x: opt_ports[x], key=f"sel_port_{prefix}_{item['ticker']}")
                            
                            c_w, c_o = st.columns(2)
                            with c_w:
                                if st.button("👀 Monitorar", key=f"btn_w_{prefix}_{item['ticker']}"):
                                    adicionar_watchlist(sel_port, item['ticker'], manual=True)
                                    st.session_state[f"_wl_added_{item['ticker']}"] = True
                                    st.rerun()
                            with c_o:
                                if st.button("🛒 Operar", key=f"btn_op_{prefix}_{item['ticker']}"):
                                    st.session_state.view_portfolio_id = sel_port
                                    st.switch_page("pages/_7_📂_Carteira_Detalhe.py")

        # Refazendo o ranking no frontend (para permitir filtros ricos sobre toda a base cacheada)
        base_ativos = filtrar_lista(highlights.get("todos_ativos", []))
        
        m_altas = sorted(base_ativos, key=lambda x: x["variacao"], reverse=True)[:5]
        m_quedas = sorted(base_ativos, key=lambda x: x["variacao"])[:5]
        com_dy = [r for r in base_ativos if r.get("dy") and r["dy"] > 0]
        m_dy = sorted(com_dy, key=lambda x: x["dy"], reverse=True)[:5]
        com_pl = [r for r in base_ativos if r.get("pl") and r["pl"] > 0]
        m_pl = sorted(com_pl, key=lambda x: x["pl"])[:5]

        with h1:
            st.markdown("#### 🟢 Maiores Altas")
            for item in m_altas:
                cor = "#00C851" if item["variacao"] >= 0 else "#FF4444"
                _renderizar_card_destaque(item, cor, "hi")
            if not m_altas:
                st.caption(f"Sem dados para {filtro_destaques}")

        with h2:
            st.markdown("#### 🔴 Maiores Quedas")
            for item in m_quedas:
                cor = "#00C851" if item["variacao"] >= 0 else "#FF4444"
                _renderizar_card_destaque(item, cor, "lo")
            if not m_quedas:
                st.caption(f"Sem dados para {filtro_destaques}")

        with h3:
            st.markdown("#### 💰 Melhores DY")
            for item in m_dy:
                extra = f"<span style='color:#667eea;font-size:0.85em'>DY {item['dy']:.2f}%</span>"
                _renderizar_card_destaque(item, "#333", "dy", extra)
            if not m_dy:
                st.caption(f"Sem dados para {filtro_destaques}")

        with h4:
            st.markdown("#### 📊 Menor P/L")
            for item in m_pl:
                extra = f"<span style='color:#764ba2;font-size:0.85em'>P/L {item['pl']:.1f}</span>"
                _renderizar_card_destaque(item, "#333", "pl", extra)
            if not m_pl:
                st.caption(f"Sem dados para {filtro_destaques}")

        st.caption(f"📊 {len(base_ativos)} ativos filtrados de um total de {highlights['total_analisados']}")
    else:
        st.info("⏳ Não foi possível carregar os destaques do mercado. Tente novamente em instantes.")

    st.markdown("---")

    # Verificar ações atrasadas
    from services.state_machine import verificar_acoes_atrasadas
    atrasadas = verificar_acoes_atrasadas()

    if atrasadas:
        st.markdown("### ⚠️ Ações Atrasadas")
        st.warning(
            f"Você tem **{len(atrasadas)} ação(ões) planejada(s) atrasada(s)**! "
            "Vá até a página **🧠 Recomendações** para revisar."
        )
        for a in atrasadas[:3]:
            st.markdown(
                f'<div class="alert-delay">'
                f'⚠️ <b>{a["asset_ticker"]}</b> - {a["tipo_acao"].upper()} '
                f'planejado para {formatar_data_br(a["data_planejada"])} ({a["dias_atraso"]} dias de atraso)'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    # -----------------------------------------------------------------------
    # 👁️ Ativos Monitorados (Global Watchlist)
    # -----------------------------------------------------------------------
    st.markdown("### 👁️ Ativos Monitorados")
    
    watchlist_global = listar_watchlist_usuario(user["id"])
    
    if watchlist_global:
        # Extrair filtros únicos
        personas_unicas = sorted(list(set([w["persona_nome"] for w in watchlist_global])))
        carteiras_unicas = sorted(list(set([w["portfolio_nome"] for w in watchlist_global])))
        
        col_f1, col_f2 = st.columns(2)
        filtro_persona = col_f1.multiselect("Filtrar por Persona", options=personas_unicas)
        filtro_carteira = col_f2.multiselect("Filtrar por Carteira", options=carteiras_unicas)
        
        # Aplicar filtros
        wl_filtrada = watchlist_global
        if filtro_persona:
            wl_filtrada = [w for w in wl_filtrada if w["persona_nome"] in filtro_persona]
        if filtro_carteira:
            wl_filtrada = [w for w in wl_filtrada if w["portfolio_nome"] in filtro_carteira]
            
        if wl_filtrada:
            for w in wl_filtrada:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"**{w['ticker']}** - {nome_ativo(w['ticker'])}")
                        st.caption(f"Monitorado em: {w['portfolio_nome']} ({w['persona_nome']})")
                    with c2:
                        p = buscar_preco_atual(w['ticker'])
                        preco_val = p.get("preco_atual", 0) if isinstance(p, dict) else 0
                        st.markdown(f"**Preço Atual:** {formatar_moeda_md(preco_val)}", unsafe_allow_html=True)
                    with c3:
                        if st.button("📄 Info", key=f"global_w_{w['id']}", use_container_width=True):
                            st.session_state.view_asset_ticker = w['ticker']
                            st.switch_page("pages/_8_📄_Ativo.py")
        else:
            st.info("Nenhum ativo corresponde aos filtros selecionados.")
    else:
        st.info("Você ainda não está monitorando nenhum ativo. Adicione através da página da Carteira ou do Ativo.")
        
    st.markdown("---")

    # Lista de Personas
    st.markdown("### 🧑 Suas Personas")
    for p in personas:
        with st.expander(f"**{p['nome']}** (Risco: {p['tolerancia_risco']}/10 | Estilo: {p['estilo'].capitalize()})"):
            portfolios = listar_portfolios_persona(p["id"])
            if portfolios:
                for port in portfolios:
                    montante_txt = f" | Caixa: {formatar_moeda_md(port['montante_disponivel'])}" if port.get('montante_disponivel') else ""
                    st.markdown(f"💼 **{port['nome']}** — Prazo: {port['objetivo_prazo']} | Meta DY: {port['meta_dividendos']}%{montante_txt}", unsafe_allow_html=True)
            else:
                st.info("Nenhuma carteira nesta persona.")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
sidebar_info()

if st.session_state.user is not None:
    tela_principal()
elif st.session_state.page == "login":
    tela_login()
else:
    tela_homepage()
