"""
Batch Anthropic padrão: envia transcrições brutas → Opus via Message Batches API.

Fluxo:
  1. submit()  — prepara as mensagens e cria o batch (retorna batch_id)
  2. status()  — consulta o andamento (polling manual ou via n8n Schedule)
  3. salvar()  — lê o JSONL de resultados e persiste em dados['competencias_batch_anthropic_padrao']

Remoção: apagar este arquivo + remover import do router.py.
"""

import json
import os

import anthropic

from core.database import get_pool
from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from projects.classificador_competencias.service import (
    _BIBLIOTECA_JSON,
    _parsear_resposta,
    _validar_competencias,
    extrair_transcricoes,
)

_DEFAULT_MODEL = "claude-opus-4-6"
_DB_FIELD = "competencias_batch_anthropic_padrao"


def _get_client() -> anthropic.Anthropic:
    api_key = os.getenv("CLASSIFICADOR_COMPETENCIAS_ANTHROPIC_API_KEY") or None
    return anthropic.Anthropic(api_key=api_key, max_retries=3)


async def submit(
    course_ids: list[int],
    model: str = _DEFAULT_MODEL,
    force: bool = False,
) -> dict:
    """
    Prepara as mensagens e cria o batch na API Anthropic.

    Args:
        course_ids: Lista de IDs de cursos a classificar.
        model:      Modelo a usar. Default: claude-opus-4-6.
        force:      Se True, reclassifica mesmo que já exista resultado salvo.

    Returns:
        {"batch_id": str | None, "submitted": [ids], "skipped": [ids], "processing_status": str}
    """
    client = _get_client()
    requests = []
    skipped = []
    submitted_ids = []

    biblioteca_context = f"Biblioteca de Competências e Habilidades:\n\n{_BIBLIOTECA_JSON}"

    for course_id in course_ids:
        dados = await get_course_dados(course_id)
        if not dados:
            print(f"[batch/anthropic/padrao] Curso {course_id} não encontrado, pulando")
            skipped.append(course_id)
            continue

        if not force and dados.get(_DB_FIELD) is not None:
            skipped.append(course_id)
            continue

        transcricoes = extrair_transcricoes(dados)
        if not transcricoes:
            print(f"[batch/anthropic/padrao] Curso {course_id} sem transcrições, pulando")
            skipped.append(course_id)
            continue

        requests.append({
            "custom_id": str(course_id),
            "params": {
                "model": model,
                "max_tokens": 4096,
                "system": [
                    {
                        "type": "text",
                        "text": biblioteca_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": SYSTEM_PROMPT},
                ],
                "messages": [
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(transcricao=transcricoes),
                    }
                ],
            },
        })
        submitted_ids.append(course_id)

    if not requests:
        return {"batch_id": None, "submitted": [], "skipped": skipped, "processing_status": None}

    batch = client.messages.batches.create(requests=requests)
    print(f"[batch/anthropic/padrao] Batch criado: {batch.id} ({len(requests)} cursos)")

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
    Lê os resultados do batch e persiste em dados['competencias_batch_anthropic_padrao'].

    Só deve ser chamado quando processing_status == "ended".

    Returns:
        {"saved": [ids], "errors": [ids], "total": int}
    """
    client = _get_client()
    pool = await get_pool()
    saved = []
    errors = []

    # results() retorna BinaryAPIResponse com o JSONL bruto — parseia linha a linha
    resposta = client.messages.batches.results(batch_id)
    linhas = resposta.text.strip().splitlines()
    print(f"[batch/anthropic/padrao] {len(linhas)} resultado(s) recebido(s) do batch {batch_id}")

    for linha in linhas:
        if not linha.strip():
            continue

        try:
            data = json.loads(linha)
        except json.JSONDecodeError as e:
            print(f"[batch/anthropic/padrao] Linha inválida no JSONL: {e}")
            continue

        course_id_str = data.get("custom_id", "")
        try:
            course_id = int(course_id_str)
        except ValueError:
            print(f"[batch/anthropic/padrao] custom_id inválido: {course_id_str}")
            errors.append(course_id_str)
            continue

        result = data.get("result", {})
        if result.get("type") != "succeeded":
            print(f"[batch/anthropic/padrao] Curso {course_id}: {result.get('type')}")
            errors.append(course_id)
            continue

        try:
            content = result["message"]["content"]
            texto = next(b["text"] for b in content if b["type"] == "text")
            competencias = _parsear_resposta(texto)
            competencias = _validar_competencias(competencias)
        except Exception as e:
            print(f"[batch/anthropic/padrao] Curso {course_id}: erro ao parsear — {e}")
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
        print(f"[batch/anthropic/padrao] Curso {course_id}: {len(competencias)} competências salvas")

    return {"saved": saved, "errors": errors, "total": len(saved) + len(errors)}
