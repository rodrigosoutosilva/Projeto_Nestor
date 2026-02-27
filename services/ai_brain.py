"""
ai_brain.py - O "Cérebro" do Sistema (Integração com Google Gemini)
====================================================================

Conceito de Eng. Software:
- Este módulo é o coração da IA do sistema
- Usa a API do Google Gemini para análise de sentimento e geração de texto
- Padrão Strategy: a lógica de IA é isolada, pode trocar por outro LLM no futuro
- Retry com backoff exponencial para lidar com limites de taxa (429)

Conceito de Finanças:
- Análise de Sentimento: usar IA para determinar se notícias são positivas
  ou negativas para um ativo — complementa a análise técnica
- A IA NÃO substitui a decisão humana, apenas sugere com base em dados
"""

import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional

# Carrega variáveis de ambiente (.env)
load_dotenv()

# ---------------------------------------------------------------------------
# Configuração da API Gemini
# Tenta 3 fontes em ordem: variável de ambiente, .env, Streamlit secrets
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Fallback: Streamlit Cloud secrets (para deploy)
if not GEMINI_API_KEY:
    try:
        import streamlit as st
        GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        pass

# Flag global para saber se a API está disponível
_api_configurada = False

# Constantes de retry
MAX_RETRIES = 4
RETRY_BASE_DELAY = 20  # segundos (Gemini sugere ~20s de espera)

# Modelos em ordem de prioridade
MODELOS_GEMINI = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash"]
_modelo_atual_idx = 0



def configurar_gemini() -> bool:
    """
    Configura a API do Gemini com a chave do .env.
    Retorna True se configurado com sucesso.
    """
    global _api_configurada

    if not GEMINI_API_KEY:
        print("[ai_brain] AVISO: GEMINI_API_KEY não encontrada no .env")
        _api_configurada = False
        return False

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        _api_configurada = True
        return True
    except Exception as e:
        print(f"[ai_brain] Erro ao configurar Gemini: {e}")
        _api_configurada = False
        return False


def _get_model():
    """
    Retorna instância do modelo Gemini.
    Tenta o modelo primário, e se falhar por quota, tenta o fallback.
    """
    global _modelo_atual_idx
    if not _api_configurada:
        configurar_gemini()

    modelo = MODELOS_GEMINI[min(_modelo_atual_idx, len(MODELOS_GEMINI) - 1)]
    return genai.GenerativeModel(modelo)



def _chamar_gemini_com_retry(prompt: str, contexto: str = "") -> str:
    """
    Chama a API Gemini com retry automático para erros 429 (rate limit).
    
    Conceito de Eng. Software: Retry Pattern com Exponential Backoff
    Quando a API retorna 429 (too many requests), esperamos um tempo
    crescente antes de tentar novamente (2s, 4s, 8s...).
    
    Args:
        prompt: O prompt a enviar para o Gemini
        contexto: Nome da operação para logging
        
    Returns:
        Texto da resposta do Gemini
        
    Raises:
        Exception se todas as tentativas falharem
    """
    model = _get_model()
    last_error = None
    global _modelo_atual_idx
    
    for tentativa in range(MAX_RETRIES):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Verificar se e erro 429 (rate limit)
            if "429" in str(e) or "resource_exhausted" in error_str or "quota" in error_str:
                # Tentar trocar para modelo fallback
                if _modelo_atual_idx < len(MODELOS_GEMINI) - 1:
                    _modelo_atual_idx += 1
                    modelo_nome = MODELOS_GEMINI[_modelo_atual_idx]
                    try:
                        print(f"[ai_brain] Tentando modelo alternativo: {modelo_nome}")
                    except UnicodeEncodeError:
                        pass
                    model = genai.GenerativeModel(modelo_nome)
                    continue
                
                wait_time = RETRY_BASE_DELAY * (tentativa + 1)  # 20, 40, 60, 80 segundos
                try:
                    print(
                        f"[ai_brain] Rate limit ({contexto}). "
                        f"Tentativa {tentativa + 1}/{MAX_RETRIES}. "
                        f"Aguardando {wait_time}s..."
                    )
                except UnicodeEncodeError:
                    pass  # Ignora erro de encoding no console Windows
                time.sleep(wait_time)
            else:
                # Outros erros: nao faz retry
                raise e
    
    # Se esgotou todas as tentativas
    raise Exception(
        f"Limite de requisicoes atingido apos {MAX_RETRIES} tentativas. "
        f"A API Gemini esta temporariamente indisponivel. "
        f"Aguarde alguns minutos e tente novamente."
    )


def analisar_sentimento(noticias_texto: str, ticker: str) -> dict:
    """
    Usa o Gemini para analisar o sentimento das notícias sobre um ativo.
    Retorna:
    - score: -1.0 (muito negativo) a 1.0 (muito positivo)
    - resumo: explicação em português do sentimento
    """
    if not noticias_texto or noticias_texto.startswith("Nenhuma notícia"):
        return {
            "score": 0.0,
            "resumo": "Sem notícias disponíveis para análise de sentimento."
        }

    prompt = f"""Você é um analista financeiro especializado no mercado brasileiro (B3).

Analise as seguintes notícias sobre o ativo {ticker} e determine o SENTIMENTO do mercado.

{noticias_texto}

Responda EXATAMENTE no formato abaixo (sem markdown, sem formatação extra):
SCORE: [um número entre -1.0 e 1.0, onde -1 é muito negativo, 0 é neutro, 1 é muito positivo]
RESUMO: [Explicação em 2-3 frases do por que você deu esse score, citando as notícias mais relevantes]
"""

    try:
        texto = _chamar_gemini_com_retry(prompt, f"sentimento_{ticker}")

        # Parsear resposta
        score = 0.0
        resumo = texto

        for linha in texto.split("\n"):
            linha = linha.strip()
            if linha.upper().startswith("SCORE:"):
                try:
                    score_str = linha.split(":", 1)[1].strip()
                    score = float(score_str)
                    score = max(-1.0, min(1.0, score))
                except (ValueError, IndexError):
                    score = 0.0
            elif linha.upper().startswith("RESUMO:"):
                resumo = linha.split(":", 1)[1].strip()

        return {"score": score, "resumo": resumo}

    except Exception as e:
        print(f"[ai_brain] Erro na análise de sentimento: {e}")
        return {
            "score": 0.0,
            "resumo": f"⚠️ {str(e)}"
        }


def gerar_recomendacao_ia(
    ticker: str,
    indicadores: dict,
    sentimento: dict,
    persona_info: dict,
    portfolio_info: dict
) -> dict:
    """
    Gera uma recomendação completa usando o Gemini.
    Inclui montante disponível e setores preferidos no prompt.
    """
    montante = portfolio_info.get('montante_disponivel', 0)
    setores = portfolio_info.get('setores_preferidos', '')
    
    prompt = f"""Você é um consultor de investimentos especializado no mercado brasileiro (B3).

ATIVO: {ticker}

INDICADORES TÉCNICOS:
- Preço Atual: R$ {indicadores.get('preco_atual', 'N/A')}
- RSI (14): {indicadores.get('rsi', 'N/A')} (>70 = sobrecomprado, <30 = sobrevendido)
- SMA 20: R$ {indicadores.get('sma_20', 'N/A')}
- SMA 50: R$ {indicadores.get('sma_50', 'N/A')}
- MACD: {indicadores.get('macd', 'N/A')}
- Signal: {indicadores.get('macd_signal', 'N/A')}
- Tendência Geral: {indicadores.get('tendencia', 'N/A')}

SENTIMENTO DAS NOTÍCIAS:
- Score: {sentimento.get('score', 0)} (-1 a 1)
- Resumo: {sentimento.get('resumo', 'Sem dados')}

PERFIL DO INVESTIDOR:
- Estilo: {persona_info.get('estilo', 'dividendos')}
- Tolerância a Risco: {persona_info.get('tolerancia_risco', 5)}/10
- Frequência de Revisão: {persona_info.get('frequencia_acao', 'semanal')}
- Objetivo de Prazo: {portfolio_info.get('objetivo_prazo', 'longo')}
- Meta de Dividendos: {portfolio_info.get('meta_dividendos', 6.0)}% ao ano
- Tipo de Ativo: {portfolio_info.get('tipo_ativo', 'misto')}
- Montante Disponível: R$ {montante:,.2f}
- Setores Preferidos: {setores if setores else 'Sem preferência específica'}

IMPORTANTE: O investidor tem R$ {montante:,.2f} disponíveis. NÃO sugira compras de valores acima deste montante. Se o preço atual do ativo multiplicado por uma quantidade razoável ultrapassar o montante, ajuste a recomendação.

Com base em TODOS esses dados, responda EXATAMENTE no formato:
ACAO: [COMPRA ou VENDA ou MANTER]
CONFIANCA: [número de 0 a 100 indicando sua confiança na recomendação]
EXPLICACAO: [Explicação detalhada em 3-5 frases justificando a decisão, citando indicadores específicos e como se alinham ao perfil do investidor. Use linguagem acessível.]
"""

    try:
        texto = _chamar_gemini_com_retry(prompt, f"recomendacao_{ticker}")

        # Parsear resposta
        acao = "manter"
        confianca = 50.0
        explicacao = texto

        for linha in texto.split("\n"):
            linha_strip = linha.strip()
            if linha_strip.upper().startswith("ACAO:") or linha_strip.upper().startswith("AÇÃO:"):
                valor = linha_strip.split(":", 1)[1].strip().upper()
                if "COMPRA" in valor:
                    acao = "compra"
                elif "VENDA" in valor:
                    acao = "venda"
                else:
                    acao = "manter"
            elif linha_strip.upper().startswith("CONFIANCA:") or linha_strip.upper().startswith("CONFIANÇA:"):
                try:
                    confianca = float(linha_strip.split(":", 1)[1].strip())
                    confianca = max(0, min(100, confianca))
                except (ValueError, IndexError):
                    confianca = 50.0
            elif linha_strip.upper().startswith("EXPLICACAO:") or linha_strip.upper().startswith("EXPLICAÇÃO:"):
                explicacao = linha_strip.split(":", 1)[1].strip()

        return {
            "acao": acao,
            "confianca": confianca,
            "explicacao": explicacao
        }

    except Exception as e:
        print(f"[ai_brain] Erro ao gerar recomendação: {e}")
        return {
            "acao": "manter",
            "confianca": 0.0,
            "explicacao": f"⚠️ {str(e)}"
        }


def gerar_sugestoes_compra(
    ativos_atuais: list[dict],
    persona_info: dict,
    portfolio_info: dict
) -> dict:
    """
    Sugere novos ativos para comprar OU reforço de posição em ativos existentes,
    baseado no montante disponível, perfil e setores preferidos.
    """
    montante = portfolio_info.get('montante_disponivel', 0)
    setores = portfolio_info.get('setores_preferidos', '')
    
    ativos_str = ", ".join([
        f"{a['ticker']} ({a['quantidade']}x @ R$ {a['preco_medio']:.2f})"
        for a in ativos_atuais
    ]) if ativos_atuais else "Nenhum ativo na carteira"

    prompt = f"""Você é um consultor de investimentos especializado no mercado brasileiro (B3).

CARTEIRA ATUAL DO INVESTIDOR:
{ativos_str}

PERFIL DO INVESTIDOR:
- Estilo: {persona_info.get('estilo', 'dividendos')}
- Tolerância a Risco: {persona_info.get('tolerancia_risco', 5)}/10
- Objetivo de Prazo: {portfolio_info.get('objetivo_prazo', 'longo')}
- Tipo de Ativo: {portfolio_info.get('tipo_ativo', 'misto')}
- Setores Preferidos: {setores if setores else 'Sem preferência específica'}

MONTANTE DISPONÍVEL PARA COMPRAS: R$ {montante:,.2f}

Com base no perfil, na carteira atual e no montante disponível, sugira:
1. Novos ativos que complementariam a carteira (diversificação)
2. Ativos existentes que valem reforçar (comprar mais)

O valor TOTAL das sugestões NÃO deve ultrapassar R$ {montante:,.2f}.
Sugira de 2 a 5 operações.

Responda EXATAMENTE no formato (uma sugestão por linha):
TICKER: [código] | TIPO: [Novo/Reforço] | QTD: [quantidade sugerida] | PRECO_ESTIMADO: [preço estimado por unidade] | MOTIVO: [explicação curta de 1 frase]

No final, adicione:
RESUMO: [Explicação geral de 2-3 frases sobre as sugestões]
"""

    try:
        texto = _chamar_gemini_com_retry(prompt, "sugestoes_compra")

        sugestoes = []
        resumo = ""

        for linha in texto.split("\n"):
            linha = linha.strip()
            if linha.upper().startswith("TICKER:"):
                partes = linha.split("|")
                sugestao = {}
                for parte in partes:
                    parte = parte.strip()
                    if ":" in parte:
                        chave, valor = parte.split(":", 1)
                        chave = chave.strip().upper()
                        valor = valor.strip()
                        if chave == "TICKER":
                            sugestao["ticker"] = valor.upper().replace(".SA", "")
                        elif chave == "TIPO":
                            sugestao["tipo"] = valor
                        elif chave == "QTD":
                            try:
                                sugestao["quantidade"] = int(valor)
                            except ValueError:
                                sugestao["quantidade"] = 1
                        elif chave == "PRECO_ESTIMADO":
                            try:
                                sugestao["preco_estimado"] = float(valor.replace("R$", "").replace(",", ".").strip())
                            except ValueError:
                                sugestao["preco_estimado"] = 0
                        elif chave == "MOTIVO":
                            sugestao["motivo"] = valor
                if sugestao.get("ticker"):
                    sugestao["valor_total"] = sugestao.get("quantidade", 1) * sugestao.get("preco_estimado", 0)
                    sugestoes.append(sugestao)
            elif linha.upper().startswith("RESUMO:"):
                resumo = linha.split(":", 1)[1].strip()

        return {
            "sugestoes": sugestoes,
            "resumo": resumo or "Sugestões baseadas no seu perfil e montante disponível.",
            "sucesso": len(sugestoes) > 0
        }

    except Exception as e:
        print(f"[ai_brain] Erro nas sugestões de compra: {e}")
        return {
            "sugestoes": [],
            "resumo": f"⚠️ {str(e)}",
            "sucesso": False
        }


def gerar_sugestao_onboarding(respostas: dict) -> dict:
    """
    Gera sugestões de ativos iniciais para o onboarding.
    Baseado nas respostas do questionário do usuário.
    """
    prompt = f"""Você é um consultor de investimentos especializado no mercado brasileiro.

Um novo investidor respondeu um questionário com as seguintes respostas:
- Tolerância a Risco: {respostas.get('tolerancia_risco', 5)}/10
- Estilo preferido: {respostas.get('estilo', 'dividendos')}
- Objetivo de Prazo: {respostas.get('objetivo_prazo', 'longo')}
- Valor disponível: R$ {respostas.get('valor_disponivel', 1000)}
- Tipo de ativo preferido: {respostas.get('tipo_ativo', 'misto')}
- Meta de dividendos: {respostas.get('meta_dividendos', 6.0)}% ao ano

Sugira de 3 a 6 ativos (ações ou FIIs da B3) para uma carteira inicial diversificada.
O valor total das sugestões NÃO deve ultrapassar R$ {respostas.get('valor_disponivel', 1000)}.

Responda EXATAMENTE no formato (um ativo por linha, sem extras):
TICKER: [código] | TIPO: [Ação/FII] | ALOCACAO: [percentual do total] | MOTIVO: [Explicação curta de 1 frase]

No final, adicione:
RESUMO: [Explicação geral de 2-3 frases sobre a carteira sugerida]
"""

    try:
        texto = _chamar_gemini_com_retry(prompt, "onboarding")

        ativos_sugeridos = []
        resumo = ""

        for linha in texto.split("\n"):
            linha = linha.strip()
            if linha.upper().startswith("TICKER:"):
                partes = linha.split("|")
                ativo = {}
                for parte in partes:
                    parte = parte.strip()
                    if ":" in parte:
                        chave, valor = parte.split(":", 1)
                        chave = chave.strip().upper()
                        valor = valor.strip()
                        if chave == "TICKER":
                            ativo["ticker"] = valor.upper().replace(".SA", "")
                        elif chave == "TIPO":
                            ativo["tipo"] = valor
                        elif chave in ("ALOCACAO", "ALOCAÇÃO"):
                            try:
                                ativo["alocacao"] = float(valor.replace("%", ""))
                            except ValueError:
                                ativo["alocacao"] = 0
                        elif chave == "MOTIVO":
                            ativo["motivo"] = valor
                if ativo.get("ticker"):
                    ativos_sugeridos.append(ativo)
            elif linha.upper().startswith("RESUMO:"):
                resumo = linha.split(":", 1)[1].strip()

        return {
            "ativos": ativos_sugeridos,
            "resumo": resumo or "Carteira diversificada para o seu perfil.",
            "sucesso": len(ativos_sugeridos) > 0
        }

    except Exception as e:
        print(f"[ai_brain] Erro no onboarding: {e}")
        # Fallback: sugestão padrão se a IA falhar
        return {
            "ativos": [
                {"ticker": "PETR4", "tipo": "Ação", "alocacao": 20, "motivo": "Blue chip, dividendos consistentes"},
                {"ticker": "VALE3", "tipo": "Ação", "alocacao": 20, "motivo": "Mineração, exposição global"},
                {"ticker": "ITUB4", "tipo": "Ação", "alocacao": 20, "motivo": "Banco sólido, dividendos regulares"},
                {"ticker": "HGLG11", "tipo": "FII", "alocacao": 20, "motivo": "FII logístico, renda mensal"},
                {"ticker": "MXRF11", "tipo": "FII", "alocacao": 20, "motivo": "FII de papel, yield atrativo"},
            ],
            "resumo": "⚠️ Carteira padrão diversificada (IA temporariamente indisponível).",
            "sucesso": True
        }


def analisar_revisao_atraso(
    ticker: str,
    acao_original: str,
    preco_original: float,
    preco_atual: float,
    dias_atraso: int,
    tolerancia_risco: int
) -> dict:
    """
    Recalcula a recomendação quando o usuário atrasou a execução.
    """
    variacao = ((preco_atual - preco_original) / preco_original) * 100

    prompt = f"""Você é um consultor de investimentos analisando uma ação atrasada.

CONTEXTO:
- Ativo: {ticker}
- Ação original sugerida: {acao_original.upper()}
- Preço quando foi sugerido: R$ {preco_original:.2f}
- Preço ATUAL: R$ {preco_atual:.2f}
- Variação: {variacao:+.2f}%
- Dias de atraso: {dias_atraso}
- Tolerância a risco do investidor: {tolerancia_risco}/10

O investidor NÃO executou a ação na data planejada. Agora o cenário mudou.

Responda EXATAMENTE no formato:
NOVA_ACAO: [COMPRA ou VENDA ou MANTER]
URGENCIA: [ALTA, MEDIA ou BAIXA]
EXPLICACAO: [Explicação de 2-3 frases no formato: "O plano original era X, mas como o preço [subiu/caiu] Y% e sua tolerância a risco é Z, agora a recomendação é W porque..."]
"""

    try:
        texto = _chamar_gemini_com_retry(prompt, f"revisao_{ticker}")

        nova_acao = acao_original
        urgencia = "media"
        explicacao = texto

        for linha in texto.split("\n"):
            linha = linha.strip()
            if linha.upper().startswith("NOVA_ACAO:") or linha.upper().startswith("NOVA_AÇÃO:"):
                valor = linha.split(":", 1)[1].strip().upper()
                if "COMPRA" in valor:
                    nova_acao = "compra"
                elif "VENDA" in valor:
                    nova_acao = "venda"
                else:
                    nova_acao = "manter"
            elif linha.upper().startswith("URGENCIA:") or linha.upper().startswith("URGÊNCIA:"):
                valor = linha.split(":", 1)[1].strip().upper()
                if "ALTA" in valor:
                    urgencia = "alta"
                elif "BAIXA" in valor:
                    urgencia = "baixa"
                else:
                    urgencia = "media"
            elif linha.upper().startswith("EXPLICACAO:") or linha.upper().startswith("EXPLICAÇÃO:"):
                explicacao = linha.split(":", 1)[1].strip()

        return {
            "nova_acao": nova_acao,
            "urgencia": urgencia,
            "explicacao": explicacao,
            "variacao_percent": round(variacao, 2),
            "preco_atual": preco_atual
        }

    except Exception as e:
        print(f"[ai_brain] Erro na revisão: {e}")
        return {
            "nova_acao": "manter",
            "urgencia": "media",
            "explicacao": f"⚠️ {str(e)}. Recomendação padrão: manter posição.",
            "variacao_percent": round(variacao, 2),
            "preco_atual": preco_atual
        }
