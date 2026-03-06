"""
order_checker.py - Verificador de Ordens Pendentes
====================================================

Verifica se alguma ordem pendente atingiu o preço-alvo e executa automaticamente.
- Compra: executa quando preço atual <= preço alvo (ativo ficou barato o suficiente)
- Venda: executa quando preço atual >= preço alvo (ativo valorizou o suficiente)
"""

from database.crud import listar_ordens_pendentes_todas, executar_ordem_pendente
from services.market_data import buscar_preco_atual


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

            deve_executar = False
            if ordem["tipo"] == "compra" and preco_atual <= ordem["preco_alvo"]:
                deve_executar = True
            elif ordem["tipo"] == "venda" and preco_atual >= ordem["preco_alvo"]:
                deve_executar = True

            if deve_executar:
                resultado = executar_ordem_pendente(ordem["id"])
                if resultado:
                    resultado["preco_execucao"] = preco_atual
                    executadas.append(resultado)
        except Exception as e:
            print(f"[order_checker] Erro ao verificar ordem {ordem['id']}: {e}")
            continue

    return executadas
