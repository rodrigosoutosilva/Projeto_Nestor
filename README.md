# 🧪 EgoLab — Teste versões. Invista melhor.

Plataforma inteligente de monitoramento e recomendação de investimentos brasileiros (Ações da B3) com IA via Google Gemini.

## 🚀 Instalação

### 1. Criar ambiente virtual (recomendado)
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Configurar chave da API
Crie um arquivo `.env` na raiz do projeto (ou edite o existente):
```env
GEMINI_API_KEY=sua_chave_aqui
```
Obtenha gratuitamente em: [aistudio.google.com](https://aistudio.google.com)

### 4. Executar
```bash
streamlit run app.py
```

## 📁 Estrutura do Projeto

```
invest_platform/
├── app.py                  # Entrada principal + Homepage
├── .env                    # Chaves de API (não commitar!)
├── database/
│   ├── models.py           # Modelos SQLAlchemy
│   ├── connection.py       # Engine e sessão
│   └── crud.py             # Operações CRUD
├── services/
│   ├── market_data.py      # yfinance (preços e indicadores)
│   ├── news_scraper.py     # Google News RSS
│   ├── ai_brain.py         # Gemini API
│   ├── scoring.py          # Motor de pontuação
│   ├── recommendation.py   # Recomendações com IA
│   ├── state_machine.py    # Máquina de estados
│   ├── order_checker.py    # Verificador de ordens
│   └── excel_export.py     # Exportação de relatórios
├── pages/                  # Páginas Streamlit
│   ├── 1_Analise_de_Desempenho.py
│   ├── 2_Personas.py
│   ├── 3_Carteiras.py
│   ├── 4_Calendario.py
│   ├── 6_Gestao_Financeira.py
│   ├── 7_Estatisticas_Mercado.py
│   ├── _7_Carteira_Detalhe.py
│   ├── _8_Ativo.py
│   └── _9_Persona_Detalhe.py
└── utils/
    └── helpers.py          # Funções auxiliares
```

## 🧠 Como Funciona

**Fórmula de Pontuação:**
```
Score = (Indicadores Técnicos × 0.4) + (Sentimento IA × 0.4) + (Perfil Investidor × 0.2)
```

**Máquina de Estados:**
```
PLANEJADO → EXECUTADO (usuário confirma)
PLANEJADO → REVISÃO (atrasou - IA recalcula com preço atual)
PLANEJADO → IGNORADO (usuário descarta)
```

## 📦 Tecnologias
- **Interface:** Streamlit + Plotly
- **Banco:** SQLite / PostgreSQL via SQLAlchemy
- **Dados:** yfinance (gratuito)
- **IA:** Google Gemini API (gratuito)
- **Notícias:** Google News RSS
