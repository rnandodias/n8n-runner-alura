"""
Batch Anthropic otimizado: Haiku sumariza síncronamente → Opus classifica em batch.

Estratégia de dois steps:
  Step 1 (síncrono) — Haiku lê as transcrições brutas e produz resumo denso (~2k tokens)
  Step 2 (batch)    — Opus classifica a partir do resumo + biblioteca comprimida (sem descrições)

Fluxo:
  1. submit()  — step 1 síncrono para cada curso, depois cria batch com resumos (retorna batch_id)
  2. status()  — consulta o andamento (polling manual ou via n8n Schedule)
  3. salvar()  — lê o JSONL de resultados e persiste em dados['competencias_batch_anthropic_otimizado']

Remoção: apagar este arquivo + remover import do router.py.
"""

import json
import os

import anthropic

from core.database import get_pool
from core.llm_client import criar_cliente_llm
from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.prompts_otimizado import (
    SYSTEM_PROMPT_CLASSIFICACAO,
    SYSTEM_PROMPT_SUMARIZACAO,
    USER_PROMPT_CLASSIFICACAO_TEMPLATE,
    USER_PROMPT_SUMARIZACAO_TEMPLATE,
)
from projects.classificador_competencias.service import (
    _parsear_resposta,
    _validar_competencias,
    extrair_transcricoes,
)
from projects.classificador_competencias.service_otimizado import _BIBLIOTECA_COMPRIMIDA_JSON

_DEFAULT_MODEL_SUMARIZACAO = "claude-haiku-4-5-20251001"
_DEFAULT_MODEL_CLASSIFICACAO = "claude-opus-4-6"
_DB_FIELD = "competencias_batch_anthropic_otimizado"


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("CLASSIFICADOR_COMPETENCIAS_ANTHROPIC_API_KEY") or None
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


async def submit(
    course_ids: list[int],
    modelo_sumarizacao: str = _DEFAULT_MODEL_SUMARIZACAO,
    modelo_classificacao: str = _DEFAULT_MODEL_CLASSIFICACAO,
    force: bool = False,
) -> dict:
    """
    Step 1 (síncrono): sumariza transcrições com Haiku para cada curso.
    Step 2 (batch):    envia os resumos ao Opus via Message Batches API.

    Args:
        course_ids:           Lista de IDs de cursos a classificar.
        modelo_sumarizacao:   Modelo do step 1. Default: claude-haiku-4-5-20251001.
        modelo_classificacao: Modelo do step 2. Default: claude-opus-4-6.
        force:                Se True, reclassifica mesmo que já exista resultado salvo.

    Returns:
        {"batch_id": str | None, "submitted": [ids], "skipped": [ids], "processing_status": str}
    """
    client = _get_client()
    llm_haiku = criar_cliente_llm(
        provider="anthropic",
        model=modelo_sumarizacao,
        project="CLASSIFICADOR_COMPETENCIAS",
    )
    requests = []
    skipped = []
    submitted_ids = []

    biblioteca_context = f"Biblioteca de Competências e Habilidades:\n\n{_BIBLIOTECA_COMPRIMIDA_JSON}"

    for course_id in course_ids:
        dados = await get_course_dados(course_id)
        if not dados:
            print(f"[batch/anthropic/otimizado] Curso {course_id} não encontrado, pulando")
            skipped.append(course_id)
            continue

        if not force and dados.get(_DB_FIELD) is not None:
            skipped.append(course_id)
            continue

        transcricoes = extrair_transcricoes(dados)
        if not transcricoes:
            print(f"[batch/anthropic/otimizado] Curso {course_id} sem transcrições, pulando")
            skipped.append(course_id)
            continue

        # Step 1: sumarizar com Haiku (síncrono)
        print(f"[batch/anthropic/otimizado] Curso {course_id}: sumarizando com {modelo_sumarizacao}")
        try:
            resumo = llm_haiku.gerar_resposta(
                system_prompt=SYSTEM_PROMPT_SUMARIZACAO,
                user_prompt=USER_PROMPT_SUMARIZACAO_TEMPLATE.format(transcricao=transcricoes),
            )
        except Exception as e:
            print(f"[batch/anthropic/otimizado] Curso {course_id}: erro na sumarização — {e}")
            skipped.append(course_id)
            continue

        print(f"[batch/anthropic/otimizado] Curso {course_id}: resumo gerado ({len(resumo)} chars)")

        # Step 2: montar requisição de batch com resumo
        requests.append({
            "custom_id": str(course_id),
            "params": {
                "model": modelo_classificacao,
                "max_tokens": 4096,
                "system": [
                    {
                        "type": "text",
                        "text": biblioteca_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": SYSTEM_PROMPT_CLASSIFICACAO},
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": USER_PROMPT_CLASSIFICACAO_TEMPLATE.format(resumo=resumo),
                    }
                ],
            },
        })
        submitted_ids.append(course_id)

    if not requests:
        return {"batch_id": None, "submitted": [], "skipped": skipped, "processing_status": None}

    batch = client.messages.batches.create(requests=requests)
    print(f"[batch/anthropic/otimizado] Batch criado: {batch.id} ({len(requests)} cursos)")

    return {
        "batch_id": batch.id,
        "submitted": submitted_ids,
        "skipped": skipped,
        "processing_status": batch.processing_status,
    }


def status(batch_id: str) -> dict:
    """
    Consulta o status de um batch na API Anthropic.

    Returns:
        {"batch_id": str, "processing_status": str, "request_counts": {...}, ...}
    """
    client = _get_client()
    batch = client.messages.batches.retrieve(batch_id)
    return {
        "batch_id": batch.id,
        "processing_status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "ended_at": batch.ended_at.isoformat() if batch.ended_at else None,
    }


async def salvar(batch_id: str) -> dict:
    """
    Lê os resultados do batch e persiste em dados['competencias_batch_anthropic_otimizado'].

    Só deve ser chamado quando processing_status == "ended".

    Returns:
        {"saved": [ids], "errors": [ids], "total": int}
    """
    client = _get_client()
    pool = await get_pool()
    saved = []
    errors = []

    for result in client.messages.batches.results(batch_id):
        course_id_str = result.custom_id
        try:
            course_id = int(course_id_str)
        except ValueError:
            print(f"[batch/anthropic/otimizado] custom_id inválido: {course_id_str}")
            errors.append(course_id_str)
            continue

        if result.result.type != "succeeded":
            print(f"[batch/anthropic/otimizado] Curso {course_id}: {result.result.type}")
            errors.append(course_id)
            continue

        try:
            texto = result.result.message.content[0].text
            competencias = _parsear_resposta(texto)
            competencias = _validar_competencias(competencias)
        except Exception as e:
            print(f"[batch/anthropic/otimizado] Curso {course_id}: erro ao parsear — {e}")
            errors.append(course_id)
            continue

        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE alura_cursos
                SET dados = jsonb_set(dados, '{{{_DB_FIELD}}}', $1::jsonb)
                WHERE course_id = $2
                """,
                json.dumps(competencias, ensure_ascii=False),
                course_id,
            )
        saved.append(course_id)
        print(f"[batch/anthropic/otimizado] Curso {course_id}: {len(competencias)} competências salvas")

    return {"saved": saved, "errors": errors, "total": len(saved) + len(errors)}
