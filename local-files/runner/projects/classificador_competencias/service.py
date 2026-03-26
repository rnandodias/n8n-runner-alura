"""
Serviço de classificação de competências para cursos Alura.

Extrai transcrições de vídeo do JSON do curso e usa LLM para identificar
entre 4 e 6 competências relevantes da biblioteca de competências da plataforma.
"""

import json
import re
from pathlib import Path

from core.llm_client import criar_cliente_llm
from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

_BIBLIOTECA_PATH = Path(__file__).parent / "biblioteca_competencias.json"

with open(_BIBLIOTECA_PATH, encoding="utf-8") as _f:
    _BIBLIOTECA = json.load(_f)

_BIBLIOTECA_JSON = json.dumps(_BIBLIOTECA["competencias"], ensure_ascii=False, indent=2)
_BIBLIOTECA_IDS = {c["id_competencia"] for c in _BIBLIOTECA["competencias"]}
_HABILIDADES_IDS = {
    h["id_habilidade"]
    for c in _BIBLIOTECA["competencias"]
    for h in c["habilidades"]
}


def extrair_transcricoes(dados: dict) -> str:
    """Extrai e concatena as transcrições dos vídeos do curso."""
    partes = []
    for aula in dados.get("aulas", []):
        for atividade in aula.get("atividades", []):
            if atividade.get("kind") == "VIDEO" and atividade.get("text"):
                titulo = atividade.get("title", "")
                texto = atividade["text"]
                partes.append(f"[{titulo}]\n{texto}" if titulo else texto)
    return "\n\n---\n\n".join(partes)


def _parsear_resposta(resposta: str) -> list[dict]:
    """Extrai e valida a lista de competências da resposta do LLM."""
    resposta = resposta.strip()

    if resposta.startswith("```"):
        resposta = re.sub(r'^```\w*\s*\n?', '', resposta)
        resposta = re.sub(r'\n?```\s*$', '', resposta)
        resposta = resposta.strip()

    # Tentativa 1: parse direto
    try:
        data = json.loads(resposta)
        if isinstance(data, dict) and "competencias" in data:
            return data["competencias"]
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # Tentativa 2: extrai o objeto JSON da resposta
    match = re.search(r'\{[\s\S]*"competencias"[\s\S]*\}', resposta)
    if match:
        try:
            data = json.loads(match.group())
            if "competencias" in data:
                return data["competencias"]
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Não foi possível parsear a resposta do LLM. Preview: {resposta[:300]}")


def _validar_competencias(competencias: list[dict]) -> list[dict]:
    """
    Valida IDs de competências e habilidades contra a biblioteca.
    Remove itens com IDs inválidos em vez de lançar erro.
    """
    validas = []
    for comp in competencias:
        comp_id = comp.get("id", "")
        if comp_id not in _BIBLIOTECA_IDS:
            print(f"AVISO: competência ignorada (ID inválido): {comp_id}")
            continue

        habilidades_validas = [
            h for h in comp.get("habilidades", [])
            if h.get("id") in _HABILIDADES_IDS
        ]
        ignoradas = len(comp.get("habilidades", [])) - len(habilidades_validas)
        if ignoradas:
            print(f"AVISO: {ignoradas} habilidade(s) ignorada(s) em {comp_id} (IDs inválidos)")

        validas.append({**comp, "habilidades": habilidades_validas})

    return validas


async def classificar_competencias(
    course_id: int,
    provider: str = "anthropic",
    model: str = None,
) -> list[dict]:
    """
    Classifica as competências de um curso usando LLM.

    Args:
        course_id: ID do curso no banco.
        provider: "anthropic" ou "openai".
        model: Modelo específico. Se None, usa o padrão do provedor.

    Returns:
        Lista de competências com habilidades identificadas.

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

    print(f"Curso {course_id}: {len(transcricoes)} chars de transcrição")

    user_prompt = USER_PROMPT_TEMPLATE.format(transcricao=transcricoes)
    biblioteca_context = f"Biblioteca de Competências e Habilidades:\n\n{_BIBLIOTECA_JSON}"

    llm = criar_cliente_llm(
        provider=provider,
        model=model,
        project="CLASSIFICADOR_COMPETENCIAS",
    )
    resposta = llm.gerar_resposta(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        artigo_context=biblioteca_context,
    )

    competencias = _parsear_resposta(resposta)
    competencias = _validar_competencias(competencias)

    print(f"Curso {course_id}: {len(competencias)} competências classificadas")
    return competencias
