import datetime
import streamlit as st
from database.crud import buscar_acoes_pendentes_todas, atualizar_status_acao, buscar_portfolio_por_id, buscar_persona_por_id, listar_ativos_portfolio
from services.scoring import pontuar_ativo_manutencao, pontuar_ativo_criacao
from database.models import StatusAcao

@st.cache_data(ttl=3600, show_spinner=False)
def verificar_notificacoes_background():
    """
    Roda de hora em hora (via TTL do cache do Streamlit).
    Pega todas as ações com status PLANEJADO cuja data_planejada <= hoje.
    Verifica se a ação ainda faz sentido usando os algoritmos.
    Se o algoritmo virou a mão (ex: era Compra e agora é Venda), muda o status para ABORTADO.
    """
    hoje = datetime.date.today()
    acoes = buscar_acoes_pendentes_todas()
    
    abortadas_count = 0
    
    for acao in acoes:
        if acao.get("status") == "planejado":
            try:
                data_plan_str = acao.get("data_planejada")
                if not data_plan_str:
                    continue
                # Se for datetime ou date, conveter ou pegar direto
                if isinstance(data_plan_str, str):
                    if " " in data_plan_str:
                        data_plan = datetime.datetime.strptime(data_plan_str.split(" ")[0], "%Y-%m-%d").date()
                    else:
                        data_plan = datetime.datetime.strptime(data_plan_str, "%Y-%m-%d").date()
                else:
                    data_plan = data_plan_str # assumindo que já é date ou datetime

                if isinstance(data_plan, datetime.datetime):
                    data_plan = data_plan.date()

                if data_plan <= hoje:
                    # Precisamos validar
                    portfolio_id = acao["portfolio_id"]
                    ticker = acao["asset_ticker"]
                    tipo_acao_original = acao["tipo_acao"] # 'compra', 'venda' ou 'manter'
                    
                    portfolio = buscar_portfolio_por_id(portfolio_id)
                    if not portfolio: continue
                    persona = buscar_persona_por_id(portfolio["persona_id"])
                    if not persona: continue
                    
                    ativos = listar_ativos_portfolio(portfolio_id)
                    ativo_existente = next((a for a in ativos if a["ticker"] == ticker), None)
                    
                    if ativo_existente:
                        # Avalia usando manutencao
                        pm_atual = ativo_existente["preco_medio"]
                        res = pontuar_ativo_manutencao(ticker, persona, portfolio, pm_atual)
                        nova_recomendacao = res["acao"]
                    else:
                        # Avalia usando criacao
                        res = pontuar_ativo_criacao(ticker, persona, portfolio)
                        nova_recomendacao = res["acao"]

                    deve_abortar = False
                    
                    # Regra Matemática de Aborto:
                    # Se era COMPRA e a nova recomendação é VENDA, ou IGNORAR
                    if tipo_acao_original == "compra" and nova_recomendacao in ["venda", "ignorar"]:
                        deve_abortar = True
                        
                    # Se era VENDA e a nova recomendação é COMPRA
                    if tipo_acao_original == "venda" and nova_recomendacao == "compra":
                        deve_abortar = True
                        
                    if deve_abortar:
                        atualizar_status_acao(acao["id"], "abortado", f"Abortado automaticamente pelo algoritmo. A recomendação atual do sistema virou para: {nova_recomendacao.upper()}.")
                        abortadas_count += 1
                        
            except Exception as e:
                print(f"[background_tasks] Erro ao verificar acao {acao.get('id')}: {e}")
                
    return abortadas_count
