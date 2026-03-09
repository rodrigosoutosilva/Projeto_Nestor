"""
crud.py - Operações CRUD (Create, Read, Update, Delete)
========================================================

Conceito de Eng. Software: Padrão Repository
Centraliza todo acesso a dados em um único lugar.
Vantagens:
- UI não precisa conhecer SQL
- Fácil de testar (mock do repository)
- Mudou o banco? Só muda aqui.
"""

from datetime import date, datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import (
    User, Persona, Portfolio, Asset, PlannedAction, Transaction, WatchlistItem,
    Observation, PendingOrder,
    StatusAcao, FrequenciaAcao, EstiloInvestimento, TipoAtivo, TipoAcao,
    TipoTransacao, OrigemTransacao, FrequenciaAporte
)
from database.connection import get_session


# ===========================================================================
# USER
# ===========================================================================

def criar_usuario(nome: str, email: str, senha: str = "") -> User:
    """Cria um novo usuário no banco."""
    import hashlib
    senha_hash = hashlib.sha256(senha.encode()).hexdigest() if senha else ""
    with get_session() as session:
        user = User(nome=nome, email=email, senha=senha_hash)
        session.add(user)
        session.flush()
        user_id = user.id
        user_nome = user.nome
    return {"id": user_id, "nome": user_nome, "email": email, "senha": senha_hash}


def buscar_usuario_por_email(email: str) -> Optional[dict]:
    """Busca usuário pelo email. Retorna None se não encontrar."""
    with get_session() as session:
        user = session.query(User).filter(User.email == email).first()
        if user:
            return {"id": user.id, "nome": user.nome, "email": user.email, "senha": user.senha}
        return None


def listar_usuarios() -> list[dict]:
    """Retorna todos os usuários."""
    with get_session() as session:
        users = session.query(User).all()
        return [{"id": u.id, "nome": u.nome, "email": u.email, "senha": u.senha} for u in users]


def buscar_usuario_por_id(user_id: int) -> Optional[dict]:
    """Busca usuário por ID."""
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            return {"id": user.id, "nome": user.nome, "email": user.email, "senha": user.senha}
        return None


# ===========================================================================
# PERSONA
# ===========================================================================

def criar_persona(
    user_id: int,
    nome: str,
    frequencia: str = "semanal",
    tolerancia_risco: int = 5,
    estilo: str = "dividendos"
) -> dict:
    """
    Cria uma nova persona de investimento.
    
    Parâmetros:
    - frequencia: "diario", "semanal" ou "mensal"
    - tolerancia_risco: 0 (ultra conservador) a 10 (ultra arrojado)
    - estilo: "dividendos" ou "crescimento"
    """
    with get_session() as session:
        persona = Persona(
            user_id=user_id,
            nome=nome,
            frequencia_acao=FrequenciaAcao(frequencia),
            tolerancia_risco=tolerancia_risco,
            estilo=EstiloInvestimento(estilo)
        )
        session.add(persona)
        session.flush()
        return {
            "id": persona.id,
            "user_id": user_id,
            "nome": nome,
            "frequencia_acao": frequencia,
            "tolerancia_risco": tolerancia_risco,
            "estilo": estilo
        }


def listar_personas_usuario(user_id: int) -> list[dict]:
    """Lista todas as personas de um usuário."""
    with get_session() as session:
        personas = session.query(Persona).filter(
            Persona.user_id == user_id
        ).all()
        return [{
            "id": p.id,
            "user_id": p.user_id,
            "nome": p.nome,
            "frequencia_acao": p.frequencia_acao.value if p.frequencia_acao else "semanal",
            "tolerancia_risco": p.tolerancia_risco,
            "estilo": p.estilo.value if p.estilo else "dividendos"
        } for p in personas]


def buscar_persona_por_id(persona_id: int) -> Optional[dict]:
    """Busca uma persona por ID."""
    with get_session() as session:
        p = session.query(Persona).filter(Persona.id == persona_id).first()
        if p:
            return {
                "id": p.id,
                "user_id": p.user_id,
                "nome": p.nome,
                "frequencia_acao": p.frequencia_acao.value if p.frequencia_acao else "semanal",
                "tolerancia_risco": p.tolerancia_risco,
                "estilo": p.estilo.value if p.estilo else "dividendos"
            }
        return None


def atualizar_persona(persona_id: int, **kwargs) -> bool:
    """Atualiza campos de uma persona."""
    with get_session() as session:
        persona = session.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return False
        for key, value in kwargs.items():
            if key == "frequencia_acao":
                value = FrequenciaAcao(value)
            elif key == "estilo":
                value = EstiloInvestimento(value)
            setattr(persona, key, value)
        return True


def deletar_persona(persona_id: int) -> bool:
    """Deleta uma persona e todas suas carteiras (cascade)."""
    with get_session() as session:
        persona = session.query(Persona).filter(Persona.id == persona_id).first()
        if not persona:
            return False
        session.delete(persona)
        return True


# ===========================================================================
# PORTFOLIO (CARTEIRA)
# ===========================================================================

def criar_portfolio(
    persona_id: int,
    nome: str,
    objetivo_prazo: str = "longo",
    meta_dividendos: float = 6.0,
    tipo_ativo: str = "misto",
    setores_preferidos: str = "",
    montante_disponivel: float = 0.0,
    aporte_periodico: float = 0.0,
    frequencia_aporte: str = "",
    frequencia_manuseio: str = ""
) -> dict:
    """
    Cria uma nova carteira vinculada a uma persona.
    
    Conceito de Finanças:
    - objetivo_prazo: horizonte do investimento (curto/medio/longo)
    - meta_dividendos: calculado automaticamente com base no perfil
    - setores_preferidos: setores de interesse separados por vírgula
    - montante_disponivel: caixa em R$ disponível para investimento
    - aporte_periodico: valor em R$ do aporte periódico
    - frequencia_aporte: frequência dos aportes (semanal/quinzenal/mensal)
    - frequencia_manuseio: frequência de revisão da carteira (≤ persona)
    """
    with get_session() as session:
        portfolio = Portfolio(
            persona_id=persona_id,
            nome=nome,
            objetivo_prazo=objetivo_prazo,
            meta_dividendos=meta_dividendos,
            tipo_ativo=TipoAtivo(tipo_ativo),
            setores_preferidos=setores_preferidos,
            montante_disponivel=montante_disponivel,
            aporte_periodico=aporte_periodico,
            frequencia_aporte=frequencia_aporte,
            frequencia_manuseio=FrequenciaAcao(frequencia_manuseio) if frequencia_manuseio else None
        )
        session.add(portfolio)
        session.flush()
        return {
            "id": portfolio.id,
            "persona_id": persona_id,
            "nome": nome,
            "objetivo_prazo": objetivo_prazo,
            "meta_dividendos": meta_dividendos,
            "tipo_ativo": tipo_ativo,
            "setores_preferidos": setores_preferidos,
            "montante_disponivel": montante_disponivel,
            "aporte_periodico": aporte_periodico,
            "frequencia_aporte": frequencia_aporte,
            "frequencia_manuseio": frequencia_manuseio
        }


def listar_portfolios_persona(persona_id: int) -> list[dict]:
    """Lista todas as carteiras de uma persona."""
    with get_session() as session:
        portfolios = session.query(Portfolio).filter(
            Portfolio.persona_id == persona_id
        ).all()
        return [{
            "id": p.id,
            "persona_id": p.persona_id,
            "nome": p.nome,
            "objetivo_prazo": p.objetivo_prazo,
            "meta_dividendos": p.meta_dividendos,
            "tipo_ativo": p.tipo_ativo.value if p.tipo_ativo else "misto",
            "setores_preferidos": p.setores_preferidos or "",
            "montante_disponivel": p.montante_disponivel or 0.0,
            "aporte_periodico": p.aporte_periodico or 0.0,
            "frequencia_aporte": p.frequencia_aporte or "",
            "frequencia_manuseio": p.frequencia_manuseio.value if p.frequencia_manuseio else "",
            "created_at": str(p.created_at) if p.created_at else None
        } for p in portfolios]


def buscar_portfolio_por_id(portfolio_id: int) -> Optional[dict]:
    """Busca uma carteira por ID."""
    with get_session() as session:
        p = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if p:
            return {
                "id": p.id,
                "persona_id": p.persona_id,
                "nome": p.nome,
                "objetivo_prazo": p.objetivo_prazo,
                "meta_dividendos": p.meta_dividendos,
                "tipo_ativo": p.tipo_ativo.value if p.tipo_ativo else "misto",
                "setores_preferidos": p.setores_preferidos or "",
                "montante_disponivel": p.montante_disponivel or 0.0,
                "aporte_periodico": p.aporte_periodico or 0.0,
                "frequencia_aporte": p.frequencia_aporte or "",
                "frequencia_manuseio": p.frequencia_manuseio.value if p.frequencia_manuseio else "",
                "created_at": str(p.created_at) if p.created_at else None
            }
        return None


def atualizar_portfolio(portfolio_id: int, **kwargs) -> bool:
    """Atualiza campos de uma carteira (nome, montante, setores, etc.)."""
    with get_session() as session:
        portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            return False
        for key, value in kwargs.items():
            if key == "tipo_ativo":
                value = TipoAtivo(value)
            elif key == "frequencia_manuseio":
                value = FrequenciaAcao(value) if value else None
            setattr(portfolio, key, value)
        return True


def deletar_portfolio(portfolio_id: int) -> bool:
    """Deleta uma carteira e seus ativos (cascade)."""
    with get_session() as session:
        portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if not portfolio:
            return False
        session.delete(portfolio)
        return True


# ===========================================================================
# ASSET (ATIVO)
# ===========================================================================

def adicionar_ativo(
    portfolio_id: int,
    ticker: str,
    preco_medio: float,
    quantidade: int,
    data_posicao: Optional[date] = None
) -> dict:
    """
    Adiciona um ativo a uma carteira.
    
    Conceito de Finanças:
    - ticker: código na B3. Ações têm 4 letras + número (PETR4).
      FIIs têm 4 letras + "11" (HGLG11).
    - preco_medio: se comprou em diferentes momentos, é a média ponderada.
    """
    with get_session() as session:
        asset = Asset(
            portfolio_id=portfolio_id,
            ticker=ticker.upper().strip(),
            preco_medio=preco_medio,
            quantidade=quantidade,
            data_posicao=data_posicao or date.today()
        )
        session.add(asset)
        session.flush()
        return {
            "id": asset.id,
            "portfolio_id": portfolio_id,
            "ticker": asset.ticker,
            "preco_medio": preco_medio,
            "quantidade": quantidade,
            "data_posicao": str(asset.data_posicao)
        }


def listar_ativos_portfolio(portfolio_id: int) -> list[dict]:
    """Lista todos os ativos de uma carteira."""
    with get_session() as session:
        assets = session.query(Asset).filter(
            Asset.portfolio_id == portfolio_id
        ).all()
        return [{
            "id": a.id,
            "portfolio_id": a.portfolio_id,
            "ticker": a.ticker,
            "preco_medio": a.preco_medio,
            "quantidade": a.quantidade,
            "data_posicao": str(a.data_posicao) if a.data_posicao else None,
            "ultimo_update": str(a.ultimo_update) if a.ultimo_update else None
        } for a in assets]


def atualizar_ativo(asset_id: int, **kwargs) -> bool:
    """Atualiza campos de um ativo."""
    with get_session() as session:
        asset = session.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            return False
        for key, value in kwargs.items():
            setattr(asset, key, value)
        asset.ultimo_update = datetime.utcnow()
        return True


def deletar_ativo(asset_id: int) -> bool:
    """Remove um ativo da carteira."""
    with get_session() as session:
        asset = session.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            return False
        session.delete(asset)
        return True


# ===========================================================================
# PLANNED ACTIONS (AÇÕES PLANEJADAS)
# ===========================================================================

def criar_acao_planejada(
    portfolio_id: int,
    asset_ticker: str,
    tipo_acao: str,
    data_planejada: date,
    pontuacao: float = 0.0,
    preco_alvo: Optional[float] = None,
    explicacao: Optional[str] = None
) -> dict:
    """
    Cria uma nova ação planejada (sugestão do algoritmo).
    
    Conceito de Finanças:
    - tipo_acao: "compra" (o algoritmo sugere adquirir), "venda" (sugere vender),
      "manter" (não fazer nada, posição já está adequada)
    - pontuacao: confiança da IA na sugestão (0-100)
    """
    with get_session() as session:
        acao = PlannedAction(
            portfolio_id=portfolio_id,
            asset_ticker=asset_ticker.upper().strip(),
            tipo_acao=TipoAcao(tipo_acao),
            data_planejada=data_planejada,
            pontuacao=pontuacao,
            preco_alvo=preco_alvo,
            explicacao=explicacao
        )
        session.add(acao)
        session.flush()
        return {
            "id": acao.id,
            "portfolio_id": portfolio_id,
            "asset_ticker": acao.asset_ticker,
            "tipo_acao": tipo_acao,
            "data_planejada": str(data_planejada),
            "status": StatusAcao.PLANEJADO.value,
            "pontuacao": pontuacao,
            "preco_alvo": preco_alvo,
            "explicacao": explicacao
        }


def listar_acoes_portfolio(
    portfolio_id: int,
    status: Optional[str] = None
) -> list[dict]:
    """
    Lista ações planejadas de uma carteira.
    Pode filtrar por status (planejado, executado, revisao_necessaria, ignorado).
    """
    with get_session() as session:
        query = session.query(PlannedAction).filter(
            PlannedAction.portfolio_id == portfolio_id
        )
        if status:
            query = query.filter(PlannedAction.status == StatusAcao(status))
        acoes = query.order_by(PlannedAction.data_planejada.desc()).all()
        return [{
            "id": a.id,
            "portfolio_id": a.portfolio_id,
            "asset_ticker": a.asset_ticker,
            "tipo_acao": a.tipo_acao.value if a.tipo_acao else None,
            "data_planejada": str(a.data_planejada) if a.data_planejada else None,
            "data_executada": str(a.data_executada) if a.data_executada else None,
            "status": a.status.value if a.status else None,
            "pontuacao": a.pontuacao,
            "preco_alvo": a.preco_alvo,
            "preco_revisado": a.preco_revisado,
            "explicacao": a.explicacao,
            "explicacao_revisao": a.explicacao_revisao,
            "created_at": str(a.created_at) if a.created_at else None
        } for a in acoes]


def atualizar_status_acao(
    acao_id: int,
    novo_status: str,
    preco_revisado: Optional[float] = None,
    explicacao_revisao: Optional[str] = None
) -> bool:
    """
    Atualiza o status de uma ação planejada (transição de estado).
    
    Transições válidas (Máquina de Estados):
    - PLANEJADO → EXECUTADO, REVISAO_NECESSARIA, IGNORADO
    - REVISAO_NECESSARIA → EXECUTADO, IGNORADO
    """
    with get_session() as session:
        acao = session.query(PlannedAction).filter(
            PlannedAction.id == acao_id
        ).first()
        if not acao:
            return False

        acao.status = StatusAcao(novo_status)

        if novo_status == StatusAcao.EXECUTADO.value:
            acao.data_executada = date.today()

        if preco_revisado is not None:
            acao.preco_revisado = preco_revisado

        if explicacao_revisao is not None:
            acao.explicacao_revisao = explicacao_revisao

        return True


def buscar_acoes_pendentes_todas() -> list[dict]:
    """
    Busca TODAS as ações planejadas que ainda não foram executadas/ignoradas.
    Útil para a máquina de estados verificar atrasos.
    """
    with get_session() as session:
        acoes = session.query(PlannedAction).filter(
            PlannedAction.status.in_([
                StatusAcao.PLANEJADO,
                StatusAcao.REVISAO_NECESSARIA
            ])
        ).all()
        return [{
            "id": a.id,
            "portfolio_id": a.portfolio_id,
            "asset_ticker": a.asset_ticker,
            "tipo_acao": a.tipo_acao.value if a.tipo_acao else None,
            "data_planejada": str(a.data_planejada) if a.data_planejada else None,
            "status": a.status.value if a.status else None,
            "pontuacao": a.pontuacao,
            "preco_alvo": a.preco_alvo,
            "explicacao": a.explicacao
        } for a in acoes]


def deletar_acao_planejada(acao_id: int) -> bool:
    """Remove uma ação planejada do banco."""
    with get_session() as session:
        acao = session.query(PlannedAction).filter(PlannedAction.id == acao_id).first()
        if not acao:
            return False
        session.delete(acao)
        return True


# ===========================================================================
# TRANSACTIONS (MOVIMENTAÇÕES)
# ===========================================================================

def registrar_transacao(
    portfolio_id: int,
    tipo: str,
    valor: float,
    ticker: Optional[str] = None,
    quantidade: Optional[int] = None,
    preco_unitario: Optional[float] = None,
    descricao: Optional[str] = None,
    data_transacao: Optional[date] = None,
    origem: str = "manual"
) -> dict:
    """
    Registra uma transação e atualiza o montante_disponivel automaticamente.
    
    Conceito de Finanças:
    - APORTE/DIVIDENDO/VENDA: creditam o caixa ( + )
    - RETIRADA/COMPRA: debitam o caixa ( - )
    """
    with get_session() as session:
        transacao = Transaction(
            portfolio_id=portfolio_id,
            tipo=TipoTransacao(tipo),
            ticker=ticker.upper().strip() if ticker else None,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
            valor=valor,
            descricao=descricao,
            origem=OrigemTransacao(origem),
            data=data_transacao or date.today()
        )
        session.add(transacao)

        # Atualizar montante_disponivel da carteira
        portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if portfolio:
            if tipo in ("aporte", "venda", "dividendo"):
                portfolio.montante_disponivel = (portfolio.montante_disponivel or 0) + valor
            elif tipo in ("retirada", "compra"):
                portfolio.montante_disponivel = (portfolio.montante_disponivel or 0) - valor

        session.flush()
        return {
            "id": transacao.id,
            "portfolio_id": portfolio_id,
            "tipo": tipo,
            "ticker": transacao.ticker,
            "quantidade": quantidade,
            "preco_unitario": preco_unitario,
            "valor": valor,
            "descricao": descricao,
            "data": str(transacao.data),
            "origem": origem,
            "montante_atualizado": portfolio.montante_disponivel if portfolio else 0
        }


def listar_transacoes_portfolio(
    portfolio_id: int,
    tipo: Optional[str] = None,
    limit: int = 100
) -> list[dict]:
    """
    Lista transações de uma carteira com filtro opcional por tipo.
    Ordenadas da mais recente para a mais antiga.
    """
    with get_session() as session:
        query = session.query(Transaction).filter(
            Transaction.portfolio_id == portfolio_id
        )
        if tipo:
            query = query.filter(Transaction.tipo == TipoTransacao(tipo))

        transacoes = query.order_by(Transaction.data.desc(), Transaction.created_at.desc()).limit(limit).all()
        return [{
            "id": t.id,
            "portfolio_id": t.portfolio_id,
            "tipo": t.tipo.value if t.tipo else None,
            "ticker": t.ticker,
            "quantidade": t.quantidade,
            "preco_unitario": t.preco_unitario,
            "valor": t.valor,
            "descricao": t.descricao,
            "origem": t.origem.value if t.origem else "manual",
            "data": str(t.data) if t.data else None,
            "created_at": str(t.created_at) if t.created_at else None
        } for t in transacoes]


def resumo_transacoes_portfolio(portfolio_id: int) -> dict:
    """
    Calcula resumo financeiro a partir das transações.
    Retorna totais de aportes, retiradas, compras, vendas e dividendos.
    """
    transacoes = listar_transacoes_portfolio(portfolio_id, limit=10000)
    resumo = {
        "total_aportes": 0.0,
        "total_retiradas": 0.0,
        "total_compras": 0.0,
        "total_vendas": 0.0,
        "total_dividendos": 0.0,
        "num_transacoes": len(transacoes)
    }
    for t in transacoes:
        if t["tipo"] == "aporte":
            resumo["total_aportes"] += t["valor"]
        elif t["tipo"] == "retirada":
            resumo["total_retiradas"] += t["valor"]
        elif t["tipo"] == "compra":
            resumo["total_compras"] += t["valor"]
        elif t["tipo"] == "venda":
            resumo["total_vendas"] += t["valor"]
        elif t["tipo"] == "dividendo":
            resumo["total_dividendos"] += t["valor"]
    return resumo


# ===========================================================================
# WATCHLIST E AGREGADORES
# ===========================================================================

def adicionar_watchlist(portfolio_id: int, ticker: str, manual: bool = True) -> dict:
    """Adiciona um ativo à watchlist de uma carteira."""
    with get_session() as session:
        # Verifica se já existe
        existente = session.query(WatchlistItem).filter(
            WatchlistItem.portfolio_id == portfolio_id,
            WatchlistItem.ticker == ticker.upper().strip()
        ).first()
        
        if existente:
            return {
                "id": existente.id,
                "portfolio_id": portfolio_id,
                "ticker": existente.ticker,
                "adicionado_manualmente": existente.adicionado_manualmente
            }
            
        item = WatchlistItem(
            portfolio_id=portfolio_id,
            ticker=ticker.upper().strip(),
            adicionado_manualmente=manual
        )
        session.add(item)
        session.flush()
        return {
            "id": item.id,
            "portfolio_id": item.portfolio_id,
            "ticker": item.ticker,
            "adicionado_manualmente": item.adicionado_manualmente,
            "created_at": str(item.created_at)
        }


def listar_watchlist_portfolio(portfolio_id: int) -> list[dict]:
    """Lista todos os itens da watchlist de uma carteira."""
    with get_session() as session:
        itens = session.query(WatchlistItem).filter(
            WatchlistItem.portfolio_id == portfolio_id
        ).order_by(WatchlistItem.created_at.desc()).all()
        return [{
            "id": i.id,
            "portfolio_id": i.portfolio_id,
            "ticker": i.ticker,
            "adicionado_manualmente": i.adicionado_manualmente,
            "created_at": str(i.created_at) if i.created_at else None
        } for i in itens]


def remover_watchlist(item_id: int) -> bool:
    """Remove um ativo da watchlist."""
    with get_session() as session:
        item = session.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
        if not item:
            return False
        session.delete(item)
        return True


def listar_watchlist_usuario(user_id: int) -> list[dict]:
    """Lista todos os itens em watchlist de todas as carteiras do usuário."""
    with get_session() as session:
        itens = session.query(WatchlistItem).join(Portfolio).join(Persona).filter(
            Persona.user_id == user_id
        ).all()
        return [{
            "id": i.id,
            "portfolio_id": i.portfolio_id,
            "portfolio_nome": i.portfolio.nome,
            "persona_nome": i.portfolio.persona.nome,
            "ticker": i.ticker,
            "adicionado_manualmente": i.adicionado_manualmente,
            "created_at": str(i.created_at) if i.created_at else None
        } for i in itens]


def listar_todos_ativos_usuario(user_id: int) -> list[dict]:
    """Lista todos os ativos (posições) de todas as carteiras do usuário."""
    with get_session() as session:
        ativos = session.query(Asset).join(Portfolio).join(Persona).filter(
            Persona.user_id == user_id
        ).all()
        return [{
            "id": a.id,
            "portfolio_id": a.portfolio_id,
            "portfolio_nome": a.portfolio.nome,
            "persona_nome": a.portfolio.persona.nome,
            "ticker": a.ticker,
            "preco_medio": a.preco_medio,
            "quantidade": a.quantidade,
            "data_posicao": str(a.data_posicao) if a.data_posicao else None
        } for a in ativos]


# ===========================================================================
# OBSERVATIONS (OBSERVAÇÕES)
# ===========================================================================

def adicionar_observacao(entity_type: str, entity_id: int, texto: str) -> dict:
    """Adiciona uma observação a uma persona ou portfolio."""
    with get_session() as session:
        obs = Observation(
            entity_type=entity_type,
            entity_id=entity_id,
            texto=texto
        )
        session.add(obs)
        session.flush()
        return {
            "id": obs.id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "texto": texto,
            "created_at": str(obs.created_at)
        }


def listar_observacoes(entity_type: str, entity_id: int) -> list[dict]:
    """Lista observações de uma entidade (persona ou portfolio)."""
    with get_session() as session:
        obs_list = session.query(Observation).filter(
            Observation.entity_type == entity_type,
            Observation.entity_id == entity_id
        ).order_by(Observation.created_at.desc()).all()
        return [{
            "id": o.id,
            "entity_type": o.entity_type,
            "entity_id": o.entity_id,
            "texto": o.texto,
            "created_at": str(o.created_at) if o.created_at else None
        } for o in obs_list]


def deletar_observacao(obs_id: int) -> bool:
    """Remove uma observação."""
    with get_session() as session:
        obs = session.query(Observation).filter(Observation.id == obs_id).first()
        if not obs:
            return False
        session.delete(obs)
        return True


# ===========================================================================
# PENDING ORDERS (ORDENS PENDENTES)
# ===========================================================================

def criar_ordem_pendente(
    portfolio_id: int,
    ticker: str,
    tipo: str,
    quantidade: int,
    preco_alvo: float
) -> dict:
    """Cria uma ordem pendente de compra/venda condicional."""
    with get_session() as session:
        ordem = PendingOrder(
            portfolio_id=portfolio_id,
            ticker=ticker.upper().strip(),
            tipo=tipo,
            quantidade=quantidade,
            preco_alvo=preco_alvo
        )
        session.add(ordem)
        session.flush()
        return {
            "id": ordem.id,
            "portfolio_id": portfolio_id,
            "ticker": ordem.ticker,
            "tipo": tipo,
            "quantidade": quantidade,
            "preco_alvo": preco_alvo,
            "status": "pendente",
            "created_at": str(ordem.created_at)
        }


def listar_ordens_pendentes(portfolio_id: int) -> list[dict]:
    """Lista ordens pendentes de uma carteira."""
    with get_session() as session:
        ordens = session.query(PendingOrder).filter(
            PendingOrder.portfolio_id == portfolio_id,
            PendingOrder.status == "pendente"
        ).order_by(PendingOrder.created_at.desc()).all()
        return [{
            "id": o.id,
            "portfolio_id": o.portfolio_id,
            "ticker": o.ticker,
            "tipo": o.tipo,
            "quantidade": o.quantidade,
            "preco_alvo": o.preco_alvo,
            "status": o.status,
            "created_at": str(o.created_at) if o.created_at else None
        } for o in ordens]


def cancelar_ordem(ordem_id: int) -> bool:
    """Cancela uma ordem pendente."""
    with get_session() as session:
        ordem = session.query(PendingOrder).filter(PendingOrder.id == ordem_id).first()
        if not ordem:
            return False
        ordem.status = "cancelada"
        return True


def atualizar_ordem_pendente(ordem_id: int, **kwargs) -> bool:
    """Atualiza campos de uma ordem pendente (tipo, quantidade, preco_alvo)."""
    with get_session() as session:
        ordem = session.query(PendingOrder).filter(PendingOrder.id == ordem_id).first()
        if not ordem or ordem.status != "pendente":
            return False
        for key, value in kwargs.items():
            setattr(ordem, key, value)
        return True


def executar_ordem_pendente(ordem_id: int) -> Optional[dict]:
    """
    Executa uma ordem pendente: registra a transação e atualiza o ativo/caixa.
    Retorna dict com detalhes ou None se falhou.
    """
    with get_session() as session:
        ordem = session.query(PendingOrder).filter(PendingOrder.id == ordem_id).first()
        if not ordem or ordem.status != "pendente":
            return None

        portfolio = session.query(Portfolio).filter(Portfolio.id == ordem.portfolio_id).first()
        if not portfolio:
            return None

        valor_total = ordem.quantidade * ordem.preco_alvo

        if ordem.tipo == "compra":
            # Atualizar ativo (criar ou incrementar)
            ativo = session.query(Asset).filter(
                Asset.portfolio_id == ordem.portfolio_id,
                Asset.ticker == ordem.ticker
            ).first()
            if ativo:
                q_ant = ativo.quantidade
                p_ant = ativo.preco_medio
                q_nova = q_ant + ordem.quantidade
                p_novo = ((q_ant * p_ant) + valor_total) / q_nova
                ativo.quantidade = q_nova
                ativo.preco_medio = p_novo
                ativo.ultimo_update = datetime.utcnow()
            else:
                novo_ativo = Asset(
                    portfolio_id=ordem.portfolio_id,
                    ticker=ordem.ticker,
                    preco_medio=ordem.preco_alvo,
                    quantidade=ordem.quantidade,
                    data_posicao=date.today()
                )
                session.add(novo_ativo)
            # Debitar caixa (pode ficar negativo se ordem futura automática)
            portfolio.montante_disponivel = (portfolio.montante_disponivel or 0) - valor_total

        elif ordem.tipo == "venda":
            ativo = session.query(Asset).filter(
                Asset.portfolio_id == ordem.portfolio_id,
                Asset.ticker == ordem.ticker
            ).first()
            if not ativo or ativo.quantidade < ordem.quantidade:
                return None  # Não tem papéis suficientes
            nova_qtd = ativo.quantidade - ordem.quantidade
            if nova_qtd <= 0:
                session.delete(ativo)
            else:
                ativo.quantidade = nova_qtd
                ativo.ultimo_update = datetime.utcnow()
            # Creditar caixa
            portfolio.montante_disponivel = (portfolio.montante_disponivel or 0) + valor_total

        # Registrar transação
        transacao = Transaction(
            portfolio_id=ordem.portfolio_id,
            tipo=TipoTransacao(ordem.tipo),
            ticker=ordem.ticker,
            quantidade=ordem.quantidade,
            preco_unitario=ordem.preco_alvo,
            valor=valor_total,
            descricao=f"Ordem condicional executada ({ordem.tipo} a R$ {ordem.preco_alvo:.2f})",
            origem=OrigemTransacao.MANUAL,
            data=date.today()
        )
        session.add(transacao)

        # Atualizar ordem
        ordem.status = "executada"
        ordem.executed_at = datetime.utcnow()

        return {
            "id": ordem.id,
            "ticker": ordem.ticker,
            "tipo": ordem.tipo,
            "quantidade": ordem.quantidade,
            "preco_alvo": ordem.preco_alvo,
            "valor_total": valor_total
        }


def listar_ordens_pendentes_todas() -> list[dict]:
    """Lista TODAS as ordens pendentes de todos os portfolios (para verificação periódica)."""
    with get_session() as session:
        ordens = session.query(PendingOrder).filter(
            PendingOrder.status == "pendente"
        ).all()
        return [{
            "id": o.id,
            "portfolio_id": o.portfolio_id,
            "ticker": o.ticker,
            "tipo": o.tipo,
            "preco_alvo": o.preco_alvo,
            "created_at": str(o.created_at) if o.created_at else None
        } for o in ordens]


def cobrar_juros_cheque_especial():
    """
    Verifica se há carteiras com saldo negativo (montante_disponivel < 0)
    e cobra 15% a.a. proporcional ao dia (Selic) via transação.
    Executado no máximo uma vez por dia por carteira.
    """
    taxa_diaria = 0.15 / 365.0
    with get_session() as session:
        # Pega carteiras negativadas
        portfolios_negativos = session.query(Portfolio).filter(
            Portfolio.montante_disponivel < 0
        ).all()
        
        hoje = date.today()
        
        for p in portfolios_negativos:
            # Verifica se já cobrou juros hoje ("Juros Saldo Devedor")
            ja_cobrou = session.query(Transaction).filter(
                Transaction.portfolio_id == p.id,
                Transaction.data == hoje,
                Transaction.descricao.like("Juros Saldo Devedor%")
            ).first()
            
            if not ja_cobrou:
                saldo_devedor = abs(p.montante_disponivel)
                juros_hoje = saldo_devedor * taxa_diaria
                
                # Debita o valor do montante (que fica mais negativo)
                p.montante_disponivel -= juros_hoje
                
                # Registra transacao
                t_juros = Transaction(
                    portfolio_id=p.id,
                    tipo=TipoTransacao.RETIRADA,
                    valor=juros_hoje,
                    descricao="Juros Saldo Devedor (Selic Diária)",
                    origem=OrigemTransacao.SISTEMA,
                    data=hoje
                )
                session.add(t_juros)
        
        # Salva o flush
        session.commit()

