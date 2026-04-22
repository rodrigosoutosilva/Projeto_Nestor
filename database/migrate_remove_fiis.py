"""
migrate_remove_fiis.py - Migração: Remover FIIs do banco de dados
=================================================================

Remove todos os ativos do tipo FII (ticker terminando em "11" que são FIIs)
das carteiras existentes, devolvendo o valor correspondente ao caixa.
Também atualiza carteiras com tipo_ativo="fiis" ou "misto" para "acoes".
"""

from database.connection import get_session
from database.models import Portfolio, Asset, Transaction, TipoTransacao, OrigemTransacao, TipoAtivo
from services.market_data import buscar_preco_atual
from datetime import date


# Tickers conhecidos como FIIs (para identificação positiva)
FIIS_CONHECIDOS = {
    "HGLG11", "MXRF11", "XPML11", "VISC11", "KNCR11", "HGCR11",
    "KNRI11", "HGBS11", "XPLG11", "BCFF11", "VILG11", "BTLG11",
    "PVBI11", "IRDM11", "VGIP11", "CPTS11", "KNIP11",
}

# Tickers que terminam em 11 mas são AÇÕES (não FIIs)
ACOES_COM_11 = {
    "TAEE11", "KLBN11", "ENGI11", "SANB11", "ALUP11", "SAPR11", "IGTI11",
}


def _is_fii(ticker: str) -> bool:
    """Verifica se um ticker é um FII."""
    ticker = ticker.upper().strip()
    if ticker in FIIS_CONHECIDOS:
        return True
    if ticker in ACOES_COM_11:
        return False
    # Heurística: 4-6 letras + "11" e não está na lista de exceções
    if len(ticker) >= 6 and ticker.endswith("11") and ticker not in ACOES_COM_11:
        return True
    return False


def migrar_remover_fiis():
    """
    Remove FIIs existentes do banco:
    1. Para cada ativo FII, calcula o valor (quantidade * preço atual) e devolve ao caixa
    2. Registra a devolução como transação SISTEMA
    3. Remove o ativo
    4. Atualiza tipo_ativo de "fiis"/"misto" para "acoes"
    """
    print("[migrate] Iniciando migração: remoção de FIIs...")
    
    with get_session() as session:
        # 1. Buscar todos os ativos
        todos_ativos = session.query(Asset).all()
        
        removidos = 0
        for ativo in todos_ativos:
            if _is_fii(ativo.ticker):
                # Buscar preço atual para calcular valor de devolução
                preco = ativo.preco_medio  # fallback
                try:
                    dados = buscar_preco_atual(ativo.ticker)
                    if dados and isinstance(dados, dict) and dados.get("preco_atual", 0) > 0:
                        preco = dados["preco_atual"]
                except Exception:
                    pass
                
                valor_devolver = ativo.quantidade * preco
                
                # Devolver ao caixa da carteira
                portfolio = session.query(Portfolio).filter(Portfolio.id == ativo.portfolio_id).first()
                if portfolio:
                    portfolio.montante_disponivel += valor_devolver
                    
                    # Registrar transação de devolução
                    t = Transaction(
                        portfolio_id=portfolio.id,
                        tipo=TipoTransacao.APORTE,
                        valor=valor_devolver,
                        descricao=f"Devolução FII removido: {ativo.ticker} ({ativo.quantidade}x @ R$ {preco:.2f})",
                        origem=OrigemTransacao.SISTEMA,
                        data=date.today()
                    )
                    session.add(t)
                
                # Remover o ativo
                session.delete(ativo)
                removidos += 1
                print(f"  [migrate] Removido {ativo.ticker} ({ativo.quantidade}x) - devolvido R$ {valor_devolver:.2f}")
        
        # 2. Atualizar tipo_ativo de carteiras
        carteiras_atualizadas = 0
        for p in session.query(Portfolio).all():
            if p.tipo_ativo and p.tipo_ativo.value in ("fiis", "misto"):
                p.tipo_ativo = TipoAtivo.ACOES
                carteiras_atualizadas += 1
        
        session.commit()
        
    print(f"[migrate] Migração concluída: {removidos} FIIs removidos, {carteiras_atualizadas} carteiras atualizadas para 'acoes'")
