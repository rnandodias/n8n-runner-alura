"""
Serviço de classificação de competências otimizado para redução de custos.

Estratégia de dois steps:
  Step 1 — Haiku lê as transcrições brutas e produz um resumo denso (1.5–2.5k palavras)
  Step 2 — Opus classifica a partir do resumo + biblioteca comprimida (sem descrições)

Resultado salvo em dados['competencias_otimizado'] — campo separado de dados['competencias']
para permitir comparação direta entre as abordagens.

Remoção: apagar este arquivo + prompts_otimizado.py + router_otimizado.py + 1 linha em app.py.
"""

import json
import re
from pathlib import Path

from core.llm_client import criar_cliente_llm
from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.prompts_otimizado import (
    SYSTEM_PROMPT_CLASSIFICACAO,
    SYSTEM_PROMPT_SUMARIZACAO,
    USER_PROMPT_CLASSIFICACAO_TEMPLATE,
    USER_PROMPT_SUMARIZACAO_TEMPLATE,
)
from projects.classificador_competencias.service import (
    _validar_competencias,
    extrair_transcricoes,
)

_BIBLIOTECA_PATH = Path(__file__).parent / "biblioteca_competencias.json"

with open(_BIBLIOTECA_PATH, encoding="utf-8") as _f:
    _BIBLIOTECA_COMPLETA = json.load(_f)

# Biblioteca comprimida: remove descricao_competencia para reduzir tokens (~50% menor)
_BIBLIOTECA_COMPRIMIDA = [
    {
        "id_competencia": c["id_competencia"],
        "nome_competencia": c["nome_competencia"],
        "habilidades": c["habilidades"],
    }
    for c in _BIBLIOTECA_COMPLETA["competencias"]
]
_BIBLIOTECA_COMPRIMIDA_JSON = json.dumps(_BIBLIOTECA_COMPRIMIDA, ensure_ascii=False, indent=2)


def _parsear_resposta(resposta: str) -> list[dict]:
    """Extrai e valida a lista de competências da resposta do LLM."""
    resposta = resposta.strip()

    if resposta.startswith("```"):
        resposta = re.sub(r'^```\w*\s*\n?', '', resposta)
        resposta = re.sub(r'\n?```\s*$', '', resposta)
        resposta = resposta.strip()

    try:
        data = json.loads(resposta)
        if isinstance(data, dict) and "competencias" in data:
            return data["competencias"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[\s\S]*"competencias"[\s\S]*\}', resposta)
    if match:
        try:
            data = json.loads(match.group())
            if "competencias" in data:
                return data["competencias"]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível parsear a resposta do LLM. Preview: {resposta[:300]}")


async def _salvar_competencias_otimizado(course_id: int, competencias: list[dict]) -> None:
    """Salva resultado em dados['competencias_otimizado'] — campo separado do fluxo original."""
    from core.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE alura_cursos
            SET dados = jsonb_set(dados, '{competencias_otimizado}', $1::jsonb)
            WHERE course_id = $2
            """,
            json.dumps(competencias, ensure_ascii=False), course_id,
        )


async def classificar_competencias_otimizado(
    course_id: int,
    modelo_sumarizacao: str = "claude-haiku-4-5-20251001",
    modelo_classificacao: str = "claude-opus-4-6",
) -> dict:
    """
    Classifica competências em dois steps para reduzir custo.

    Step 1: Haiku sumariza as transcrições (~80k tokens → ~2k tokens)
    Step 2: Opus classifica usando resumo + biblioteca comprimida

    Args:
        course_id: ID do curso no banco.
        modelo_sumarizacao: Modelo do Step 1. Default: Haiku (barato e rápido).
        modelo_classificacao: Modelo do Step 2. Default: Opus (melhor qualidade).

    Returns:
        Dict com competencias, resumo gerado e tokens de cada step.

    Raises:
        ValueError: Se curso não encontrado ou sem transcrições de vídeo.
    """
    dados = await get_course_dados(course_id)
    if not dados:
        raise ValueError(f"Curso {course_id} não encontrado no banco")

    transcricoes = extrair_transcricoes(dados)
    if not transcricoes:
        raise ValueError(
            f"Curso {course_id} não possui transcrições de vídeo "
            "(atividades com kind=VIDEO e campo text preenchido)"
        )

    print(f"[otimizado] Curso {course_id}: {len(transcricoes)} chars de transcrição")

    # ── Step 1: sumarizar transcrições com Haiku ──────────────────────────────
    print(f"[otimizado] Step 1 — sumarizando com {modelo_sumarizacao}")
    llm_haiku = criar_cliente_llm(
        provider="anthropic",
        model=modelo_sumarizacao,
        project="CLASSIFICADOR_COMPETENCIAS",
    )
    resumo = llm_haiku.gerar_resposta(
        system_prompt=SYSTEM_PROMPT_SUMARIZACAO,
        user_prompt=USER_PROMPT_SUMARIZACAO_TEMPLATE.format(transcricao=transcricoes),
    )
    print(f"[otimizado] Resumo gerado: {len(resumo)} chars")

    # ── Step 2: classificar com Opus usando resumo + biblioteca comprimida ────
    print(f"[otimizado] Step 2 — classificando com {modelo_classificacao}")
    biblioteca_context = f"Biblioteca de Competências e Habilidades:\n\n{_BIBLIOTECA_COMPRIMIDA_JSON}"
    llm_opus = criar_cliente_llm(
        provider="anthropic",
        model=modelo_classificacao,
        project="CLASSIFICADOR_COMPETENCIAS",
    )
    resposta = llm_opus.gerar_resposta(
        system_prompt=SYSTEM_PROMPT_CLASSIFICACAO,
        user_prompt=USER_PROMPT_CLASSIFICACAO_TEMPLATE.format(resumo=resumo),
        artigo_context=biblioteca_context,
    )

    competencias = _parsear_resposta(resposta)
    competencias = _validar_competencias(competencias)

    print(f"[otimizado] Curso {course_id}: {len(competencias)} competências classificadas")
    return {"competencias": competencias, "resumo": resumo}
