"""
models.py - Modelos do Banco de Dados (ORM)
============================================

Aqui definimos as "tabelas" do banco de dados como classes Python.
Cada classe = uma tabela. Cada atributo = uma coluna.

Conceito de Finanças:
- Persona: perfil de investidor (conservador, moderado, arrojado)
- Portfolio (Carteira): conjunto de ativos com um objetivo específico
- Asset (Ativo): ação ou FII individual dentro de uma carteira
- PlannedAction: sugestão gerada pelo algoritmo de IA

Conceito de Eng. Software:
- ORM: mapeamento objeto-relacional, evita SQL puro
- Relationships: SQLAlchemy gerencia as FK automaticamente
- Cascade: ao deletar uma Persona, deleta seus Portfolios (integridade)
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    Text, ForeignKey, Boolean, Enum as SAEnum
)
from sqlalchemy.orm import relationship, declarative_base
import enum

# ---------------------------------------------------------------------------
# Base declarativa: todas as classes de modelo herdam dela
# ---------------------------------------------------------------------------
Base = declarative_base()


# ===========================================================================
# ENUMS - Tipos enumerados para campos com valores fixos
# ===========================================================================

class FrequenciaAcao(str, enum.Enum):
    """
    Com que frequência a persona quer revisar sua carteira.
    
    Conceito de Finanças:
    - Diário: day trader ou investidor muito ativo
    - Semanal: investidor ativo, acompanha o mercado de perto
    - Mensal: investidor de longo prazo, buy and hold
    """
    DIARIO = "diario"
    SEMANAL = "semanal"
    MENSAL = "mensal"


class EstiloInvestimento(str, enum.Enum):
    """
    Conceito de Finanças:
    - Dividendos: foco em receber renda passiva (TAEE11, BBAS3...)
    - Crescimento: foco em valorização do preço (WEGE3, MGLU3...)
    - Equilibrado: mix de renda passiva e valorização
    """
    DIVIDENDOS = "dividendos"
    CRESCIMENTO = "crescimento"
    EQUILIBRADO = "equilibrado"


class FrequenciaAporte(str, enum.Enum):
    """
    Frequência dos aportes periódicos automáticos.
    """
    SEMANAL = "semanal"
    QUINZENAL = "quinzenal"
    MENSAL = "mensal"


class TipoAtivo(str, enum.Enum):
    """Tipo de ativo que a carteira aceita."""
    ACOES = "acoes"


class TipoAcao(str, enum.Enum):
    """Tipo de ação sugerida pelo algoritmo."""
    COMPRA = "compra"
    VENDA = "venda"
    MANTER = "manter"


class StatusAcao(str, enum.Enum):
    """
    Máquina de Estados das ações planejadas.
    
    Conceito de Eng. Software: State Machine (Máquina de Estados)
    Cada ação planejada passa por estados bem definidos:
    
    PLANEJADO → EXECUTADO (usuário confirmou)
    PLANEJADO → REVISAO_NECESSARIA (atrasou, preço mudou)
    PLANEJADO → IGNORADO (usuário descartou)
    REVISAO_NECESSARIA → EXECUTADO (após recálculo)
    REVISAO_NECESSARIA → IGNORADO (descartou)
    """
    PLANEJADO = "planejado"
    EXECUTADO = "executado"
    REVISAO_NECESSARIA = "revisao_necessaria"
    IGNORADO = "ignorado"


class TipoTransacao(str, enum.Enum):
    """
    Tipos de movimentação financeira na carteira.

    Conceito de Finanças:
    - APORTE: dinheiro novo entrando na carteira
    - RETIRADA: dinheiro retirado da carteira
    - COMPRA: compra de ativo (debita caixa, adiciona/atualiza ativo)
    - VENDA: venda de ativo (credita caixa, reduz/remove ativo)
    - DIVIDENDO: provento recebido de um ativo (credita caixa)
    """
    APORTE = "aporte"
    RETIRADA = "retirada"
    COMPRA = "compra"
    VENDA = "venda"
    DIVIDENDO = "dividendo"


class OrigemTransacao(str, enum.Enum):
    """
    Rastreabilidade: de onde veio esta transação?

    Conceito de Eng. Software: Auditoria / Proveniência
    Saber se uma transação foi sugerida pela IA ou feita manualmente
    permite analisar a qualidade das recomendações ao longo do tempo.
    """
    MANUAL = "manual"          # Usuário registrou por conta própria
    RECOMENDACAO_IA = "ia"     # Seguiu sugestão da IA
    ONBOARDING = "onboarding"  # Criada no onboarding automático
    SEED = "seed"              # Dados de teste/seed
    SISTEMA = "sistema"        # Criada automaticamente pelo sistema


# ===========================================================================
# MODELOS
# ===========================================================================

class User(Base):
    """
    Tabela de usuários.
    Relacionamento: 1 User → N Personas (um investidor pode ter vários perfis)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    senha = Column(String(255), nullable=False, default="")  # Hash da senha
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento: acessa user.personas para ver todas as personas
    personas = relationship(
        "Persona",
        back_populates="user",
        cascade="all, delete-orphan"  # Deletar user → deleta personas
    )

    def __repr__(self):
        return f"<User(id={self.id}, nome='{self.nome}')>"


class Persona(Base):
    """
    Persona de investimento - representa um perfil/estratégia.
    
    Conceito de Finanças: Um mesmo investidor pode ter perfis diferentes.
    Ex: "Aposentadoria" (conservador, dividendos) e "Especulação" (arrojado, crescimento).
    
    Tolerância a risco (0-10):
    - 0-3: Conservador (prefere renda fixa, ações de dividendos)
    - 4-6: Moderado (mix diversificado de ações)
    - 7-10: Arrojado (ações de crescimento, small caps)
    """
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    frequencia_acao = Column(
        SAEnum(FrequenciaAcao),
        default=FrequenciaAcao.SEMANAL
    )
    tolerancia_risco = Column(Integer, default=5)  # 0 a 10
    estilo = Column(
        SAEnum(EstiloInvestimento),
        default=EstiloInvestimento.DIVIDENDOS
    )

    # Relacionamentos
    user = relationship("User", back_populates="personas")
    portfolios = relationship(
        "Portfolio",
        back_populates="persona",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Persona(id={self.id}, nome='{self.nome}', risco={self.tolerancia_risco})>"


class Portfolio(Base):
    """
    Carteira de investimentos - vinculada a uma Persona.
    
    Conceito de Finanças:
    - objetivo_prazo: "curto" (<1 ano), "medio" (1-5 anos), "longo" (>5 anos)
    - meta_dividendos: calculado automaticamente com base no perfil
    - tipo_ativo: tipo de ativos aceitos na carteira
    - setores_preferidos: setores de interesse (bancos, petróleo, etc.)
    - montante_disponivel: caixa disponível para investimento
    - aporte_periodico: valor do aporte periódico automático
    - frequencia_aporte: frequência do aporte (semanal, quinzenal, mensal)
    - frequencia_manuseio: frequência de revisão da carteira (≤ persona)
    """
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    nome = Column(String(100), nullable=False)
    objetivo_prazo = Column(String(20), default="longo")  # curto, medio, longo
    meta_dividendos = Column(Float, default=6.0)  # % ao ano (auto-calculado)
    tipo_ativo = Column(
        SAEnum(TipoAtivo),
        default=TipoAtivo.ACOES
    )
    setores_preferidos = Column(String(500), default="")  # Ex: "bancos,petroleo,logistica"
    montante_disponivel = Column(Float, default=0.0)  # Caixa em R$ disponível
    aporte_periodico = Column(Float, default=0.0)  # Valor do aporte periódico em R$
    frequencia_aporte = Column(String(20), default="")  # semanal, quinzenal, mensal ou ""
    frequencia_manuseio = Column(
        SAEnum(FrequenciaAcao),
        nullable=True  # None = herda da persona
    )
    taxa_saldo_negativo = Column(Float, default=10.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamentos
    persona = relationship("Persona", back_populates="portfolios")
    assets = relationship(
        "Asset",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )
    transactions = relationship(
        "Transaction",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )
    planned_actions = relationship(
        "PlannedAction",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )
    watchlist_items = relationship(
        "WatchlistItem",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )
    pending_orders = relationship(
        "PendingOrder",
        back_populates="portfolio",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Portfolio(id={self.id}, nome='{self.nome}')>"


class Asset(Base):
    """
    Ativo individual dentro de uma carteira.
    
    Conceito de Finanças:
    - ticker: código do ativo na B3 (ex: PETR4, VALE3, HGLG11)
    - preco_medio: preço médio de compra (usado para calcular lucro/prejuízo)
    - quantidade: número de cotas/ações possuídas
    
    Conceito de Eng. Software:
    - preco_medio é Float e não Decimal por simplicidade. Em produção, use Decimal.
    """
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    data_posicao = Column(Date, default=date.today)
    preco_medio = Column(Float, nullable=False)
    quantidade = Column(Integer, nullable=False)
    ultimo_update = Column(DateTime, default=datetime.utcnow)

    # Relacionamento
    portfolio = relationship("Portfolio", back_populates="assets")

    def __repr__(self):
        return f"<Asset(ticker='{self.ticker}', qtd={self.quantidade}, pm={self.preco_medio})>"


class PlannedAction(Base):
    """
    Ação planejada/sugerida pelo algoritmo de IA.
    
    Conceito de Eng. Software: Máquina de Estados
    Cada registro passa por transições de estado bem definidas:
    
    ┌──────────┐     ┌───────────┐     ┌──────────┐
    │ PLANEJADO│────►│ EXECUTADO │     │ IGNORADO │
    └────┬─────┘     └───────────┘     └──────────┘
         │                                   ▲
         │           ┌───────────────┐       │
         └──────────►│ REVISÃO NECES.│───────┘
                     └───────┬───────┘
                             │
                     ┌───────▼───────┐
                     │  EXECUTADO    │
                     └───────────────┘
    
    Conceito de Finanças:
    - pontuacao: score 0-100 calculado pelo motor de recomendação
    - preco_alvo: preço-alvo original da sugestão (antes de possível revisão)
    - preco_revisado: novo preço após recálculo por atraso
    """
    __tablename__ = "planned_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    asset_ticker = Column(String(10), nullable=False)
    tipo_acao = Column(SAEnum(TipoAcao), nullable=False)
    data_planejada = Column(Date, nullable=False)
    data_executada = Column(Date, nullable=True)
    status = Column(
        SAEnum(StatusAcao),
        default=StatusAcao.PLANEJADO
    )
    pontuacao = Column(Float, default=0.0)  # Score 0-100
    preco_alvo = Column(Float, nullable=True)
    preco_revisado = Column(Float, nullable=True)
    explicacao = Column(Text, nullable=True)  # Texto gerado pela IA
    explicacao_revisao = Column(Text, nullable=True)  # Texto da revisão
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento
    portfolio = relationship("Portfolio", back_populates="planned_actions")

    def __repr__(self):
        return (
            f"<PlannedAction(ticker='{self.asset_ticker}', "
            f"tipo='{self.tipo_acao}', status='{self.status}')>"
        )


class Transaction(Base):
    """
    Registro de movimentação financeira na carteira.

    Conceito de Finanças:
    Cada transação impacta o montante_disponivel da carteira:
    - APORTE: +valor no caixa
    - RETIRADA: -valor do caixa
    - COMPRA: -valor do caixa (quantidade × preço_unitário)
    - VENDA: +valor no caixa (quantidade × preço_unitário)
    - DIVIDENDO: +valor no caixa (provento recebido)

    Conceito de Eng. Software: Event Sourcing simplificado
    Ao registrar cada movimentação, podemos reconstruir o saldo
    a qualquer momento somando as transações.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    tipo = Column(SAEnum(TipoTransacao), nullable=False)
    ticker = Column(String(10), nullable=True)  # Somente para compra/venda/dividendo
    quantidade = Column(Integer, nullable=True)  # Somente para compra/venda
    preco_unitario = Column(Float, nullable=True)  # Somente para compra/venda
    valor = Column(Float, nullable=False)  # Valor total da transação em R$
    descricao = Column(String(500), nullable=True)  # Nota/observação livre
    origem = Column(SAEnum(OrigemTransacao), default=OrigemTransacao.MANUAL)  # Rastreabilidade
    data = Column(Date, default=date.today, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento
    portfolio = relationship("Portfolio", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(tipo='{self.tipo}', valor={self.valor}, ticker='{self.ticker}')>"


class WatchlistItem(Base):
    """
    Item na lista de monitoramento (watchlist) de uma carteira.
    Pode ter sido adicionado manualmente ou sugerido pela IA/algoritmo.
    """
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    adicionado_manualmente = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relacionamento
    portfolio = relationship("Portfolio", back_populates="watchlist_items")

    def __repr__(self):
        return f"<WatchlistItem(ticker='{self.ticker}', manual={self.adicionado_manualmente})>"


class Observation(Base):
    """
    Observação/nota de texto associada a uma Persona ou Portfolio.
    Usa entity_type + entity_id para vincular de forma polimórfica.
    """
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False)  # "persona" ou "portfolio"
    entity_id = Column(Integer, nullable=False)
    texto = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Observation(tipo='{self.entity_type}', entity={self.entity_id})>"


class StatusOrdem(str, enum.Enum):
    """Status de uma ordem pendente."""
    PENDENTE = "pendente"
    EXECUTADA = "executada"
    CANCELADA = "cancelada"


class PendingOrder(Base):
    """
    Ordem pendente de compra/venda condicional.
    Executa automaticamente quando o ativo atinge o preco_alvo.
    - Compra: executa quando preço atual <= preco_alvo
    - Venda: executa quando preço atual >= preco_alvo
    """
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker = Column(String(10), nullable=False)
    tipo = Column(String(10), nullable=False)  # "compra" ou "venda"
    quantidade = Column(Integer, nullable=False)
    preco_alvo = Column(Float, nullable=False)
    status = Column(String(20), default="pendente")  # pendente, executada, cancelada
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

    # Relacionamento
    portfolio = relationship("Portfolio", back_populates="pending_orders")

    def __repr__(self):
        return f"<PendingOrder(ticker='{self.ticker}', tipo='{self.tipo}', alvo={self.preco_alvo})>"
