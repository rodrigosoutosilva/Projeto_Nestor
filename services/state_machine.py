"""
state_machine.py - Máquina de Estados das Ações Planejadas
============================================================

Conceito de Eng. Software: State Machine (Máquina de Estados Finitos)
Uma Máquina de Estados define:
1. Os possíveis ESTADOS de um objeto
2. As TRANSIÇÕES válidas entre estados
3. As CONDIÇÕES para cada transição

Diagrama de Estados para PlannedAction:

    ┌──────────────┐
    │   PLANEJADO  │ (Estado inicial: IA sugeriu uma ação)
    └──────┬───────┘
           │
    ┌──────┴───────────────────┐
    │  Data X chegou?          │
    ├──────────────────────────┤
    │ SIM + Usuário executou   │──────► EXECUTADO ✅
    │ SIM + Usuário ignorou    │──────► IGNORADO ❌
    │ SIM + Não fez nada       │──────► REVISÃO NECESSÁRIA ⚠️
    └──────────────────────────┘
                                         │
    ┌────────────────────────────────────┘
    │ IA recalcula com preço atual
    │
    ├── Usuário executa nova sugestão ──► EXECUTADO ✅
    └── Usuário ignora                ──► IGNORADO ❌

Conceito de Finanças:
O mercado é dinâmico. Uma sugestão de compra a R$30 pode não
fazer sentido se o preço já subiu para R$35. Por isso, ações
atrasadas DEVEM ser recalculadas.
"""

from datetime import date
from database.crud import (
    buscar_acoes_pendentes_todas,
    atualizar_status_acao,
    buscar_persona_por_id,
    buscar_portfolio_por_id
)
from services.market_data import buscar_preco_atual
from services.ai_brain import analisar_revisao_atraso


def verificar_acoes_atrasadas() -> list[dict]:
    """
    Verifica todas as ações planejadas e identifica as que estão atrasadas.
    
    Uma ação está atrasada quando:
    - Status = PLANEJADO
    - data_planejada < data de hoje (a data já passou)
    
    Retorna lista de ações atrasadas com informações para recálculo.
    """
    acoes_pendentes = buscar_acoes_pendentes_todas()
    hoje = date.today()
    atrasadas = []

    for acao in acoes_pendentes:
        if acao["status"] == "planejado":
            data_plan = acao.get("data_planejada", "")
            try:
                data = date.fromisoformat(data_plan) if isinstance(data_plan, str) else data_plan
                if data < hoje:
                    dias_atraso = (hoje - data).days
                    atrasadas.append({
                        **acao,
                        "dias_atraso": dias_atraso
                    })
            except (ValueError, TypeError):
                continue

    return atrasadas


def processar_atrasos() -> list[dict]:
    """
    Processa TODAS as ações atrasadas:
    1. Busca preço atual do ativo
    2. Compara com preço original da sugestão
    3. Usa IA para gerar nova recomendação
    4. Atualiza o status para REVISÃO NECESSÁRIA
    
    Conceito de Eng. Software: Batch Processing
    Roda de uma vez para todas as ações atrasadas, evitando
    múltiplas verificações pontuais.
    
    Retorna lista de ações revisadas com novas recomendações.
    """
    atrasadas = verificar_acoes_atrasadas()
    resultados = []

    for acao in atrasadas:
        ticker = acao["asset_ticker"]
        preco_original = acao.get("preco_alvo", 0)

        # Buscar preço atual
        dados_atuais = buscar_preco_atual(ticker)
        if not dados_atuais:
            continue

        preco_atual = dados_atuais["preco_atual"]

        # Buscar persona para saber tolerância a risco
        portfolio = buscar_portfolio_por_id(acao["portfolio_id"])
        persona = None
        if portfolio:
            persona = buscar_persona_por_id(portfolio.get("persona_id"))

        tolerancia = persona.get("tolerancia_risco", 5) if persona else 5

        # IA recalcula a recomendação
        revisao = analisar_revisao_atraso(
            ticker=ticker,
            acao_original=acao.get("tipo_acao", "manter"),
            preco_original=preco_original or preco_atual,
            preco_atual=preco_atual,
            dias_atraso=acao["dias_atraso"],
            tolerancia_risco=tolerancia
        )

        # Atualizar status no banco para REVISÃO NECESSÁRIA
        atualizar_status_acao(
            acao_id=acao["id"],
            novo_status="revisao_necessaria",
            preco_revisado=preco_atual,
            explicacao_revisao=revisao["explicacao"]
        )

        resultados.append({
            "acao_id": acao["id"],
            "ticker": ticker,
            "tipo_original": acao.get("tipo_acao"),
            "preco_original": preco_original,
            "preco_atual": preco_atual,
            "variacao": revisao["variacao_percent"],
            "dias_atraso": acao["dias_atraso"],
            "nova_recomendacao": revisao["nova_acao"],
            "urgencia": revisao["urgencia"],
            "explicacao": revisao["explicacao"]
        })

    return resultados


def executar_acao(acao_id: int) -> bool:
    """
    Marca uma ação como EXECUTADA pelo usuário.
    
    Transição: PLANEJADO/REVISÃO → EXECUTADO
    """
    return atualizar_status_acao(acao_id, "executado")


def ignorar_acao(acao_id: int) -> bool:
    """
    Marca uma ação como IGNORADA (usuário decidiu não executar).
    
    Transição: PLANEJADO/REVISÃO → IGNORADO
    """
    return atualizar_status_acao(acao_id, "ignorado")


def obter_resumo_estados(portfolio_id: int = None) -> dict:
    """
    Retorna contagem de ações por estado.
    Útil para dashboards e alertas visuais.
    """
    from database.crud import listar_acoes_portfolio
    
    if portfolio_id:
        acoes = listar_acoes_portfolio(portfolio_id)
    else:
        acoes = buscar_acoes_pendentes_todas()

    contagem = {
        "planejado": 0,
        "executado": 0,
        "revisao_necessaria": 0,
        "ignorado": 0,
        "total": len(acoes)
    }

    for acao in acoes:
        status = acao.get("status", "")
        if status in contagem:
            contagem[status] += 1

    return contagem
