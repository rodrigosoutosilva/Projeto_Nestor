"""
excel_export.py - Serviço de Geração de Relatórios
===================================================
Gera planilhas Excel consolidadas com o histórico de movimentações.
"""
import pandas as pd
import io
from database.crud import listar_transacoes_portfolio, listar_portfolios_persona, listar_personas_usuario
from utils.helpers import nome_ativo

def gerar_relatorio_excel(user_id: int) -> bytes:
    """
    Gera um relatório unificado em Excel (XLSX) contendo todas as transações
    de todas as carteiras do usuário.
    """
    personas = listar_personas_usuario(user_id)
    todas_transacoes = []
    
    for p in personas:
        portfolios = listar_portfolios_persona(p["id"])
        for port in portfolios:
            transacoes = listar_transacoes_portfolio(port["id"], limit=10000)
            for t in transacoes:
                # Obter nome do ativo via helpers
                ativo_nome = nome_ativo(t["ticker"]) if t["ticker"] else ""
                
                # Formatar a linha
                linha = {
                    "Data": t["data"],
                    "Persona": p["nome"],
                    "Carteira": port["nome"],
                    "Tipo de Movimento": t["tipo"].upper(),
                    "Ticker": t["ticker"] or "-",
                    "Nome do Ativo": ativo_nome or "-",
                    "Valor (R$)": t["valor"],
                    "Quantidade": t["quantidade"] or "-",
                    "Preço Unitário (R$)": t["preco_unitario"] or "-",
                    "Recomendação IA?": "Sim" if t.get("origem") == "ia" or "IA " in str(t.get("descricao", "")).upper() else "Não",
                    "Observações": t["descricao"] or ""
                }
                todas_transacoes.append(linha)
                
    # Se não houver transações, criar df vazio com colunas
    if not todas_transacoes:
        df = pd.DataFrame(columns=[
            "Data", "Persona", "Carteira", "Tipo de Movimento", "Ticker", 
            "Nome do Ativo", "Valor (R$)", "Quantidade", "Preço Unitário (R$)", 
            "Recomendação IA?", "Observações"
        ])
    else:
        df = pd.DataFrame(todas_transacoes)
        # Ordenar chronologicamente
        df['Data_dt'] = pd.to_datetime(df['Data'])
        df = df.sort_values('Data_dt', ascending=False).drop('Data_dt', axis=1)

    # Escrever para bytes
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Movimentações')
        
    return output.getvalue()
