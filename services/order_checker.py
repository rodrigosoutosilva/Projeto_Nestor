"""
order_checker.py - Verificador de Ordens Pendentes
====================================================

Verifica se alguma ordem pendente atingiu o preço-alvo e executa automaticamente.
- Compra: executa quando preço atual <= preço alvo + R$0.01 (ativo está no preço ou abaixo)
- Venda: executa quando preço atual >= preço alvo - R$0.01 (ativo está no preço ou acima)

Tolerância de R$ 0.01 (1 centavo) em ambas as direções.
"""

from database.crud import listar_ordens_pendentes_todas, executar_ordem_pendente
from services.market_data import buscar_preco_atual

# Tolerância de 1 centavo
TOLERANCIA = 0.01


def deve_executar_ordem(tipo: str, preco_alvo: float, preco_atual: float) -> bool:
    """
    Determina se uma ordem deve ser executada com base no preço atual.
    
    - Compra: o usuário quer comprar a esse preço ou menos. Se o mercado está
      no preço alvo ou abaixo, executa. (preco_atual <= preco_alvo + tolerância)
    - Venda: o usuário quer vender a esse preço ou mais. Se o mercado está
      no preço alvo ou acima, executa. (preco_atual >= preco_alvo - tolerância)
    """
    if tipo == "compra":
        return preco_atual <= preco_alvo + TOLERANCIA
    elif tipo == "venda":
        return preco_atual >= preco_alvo - TOLERANCIA
    return False


def verificar_e_executar_ordens() -> list[dict]:
    """
    Verifica todas as ordens pendentes e executa as que atingiram o preço-alvo.
    Retorna lista de ordens executadas nesta verificação.
    """
    ordens = listar_ordens_pendentes_todas()
    executadas = []

    for ordem in ordens:
        try:
            preco_info = buscar_preco_atual(ordem["ticker"])
            if not isinstance(preco_info, dict) or preco_info.get("preco_atual", 0) <= 0:
                continue

            preco_atual = preco_info["preco_atual"]

            if deve_executar_ordem(ordem["tipo"], ordem["preco_alvo"], preco_atual):
                resultado = executar_ordem_pendente(ordem["id"])
                if resultado:
                    resultado["preco_execucao"] = preco_atual
                    executadas.append(resultado)
        except Exception as e:
            print(f"[order_checker] Erro ao verificar ordem {ordem['id']}: {e}")
            continue

    return executadas
