"""
Batch OpenAI padrão: envia transcrições brutas → gpt-4.1 via Batch API.

Fluxo:
  1. submit()  — monta JSONL, faz upload e cria o batch (retorna batch_id)
  2. status()  — consulta o andamento (polling manual ou via n8n Schedule)
  3. salvar()  — lê o arquivo de saída e persiste em dados['competencias_batch_openai_padrao']

A variante é identificada pelo metadata {"variant": "padrao"} salvo no batch.
O endpoint de webhook usa esse metadata para rotear o salvar correto.

Remoção: apagar este arquivo + remover import do router.py.
"""

import io
import json
import os

from openai import OpenAI

from core.database import get_pool
from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from projects.classificador_competencias.service import (
    _BIBLIOTECA_JSON,
    _parsear_resposta,
    _validar_competencias,
    extrair_transcricoes,
)

_DEFAULT_MODEL = "gpt-4.1"
_DB_FIELD = "competencias_batch_openai_padrao"
_VARIANT = "padrao"


def _get_client() -> OpenAI:
    api_key = os.getenv("CLASSIFICADOR_COMPETENCIAS_OPENAI_API_KEY") or None
    return OpenAI(api_key=api_key)


async def submit(
    course_ids: list[int],
    model: str = _DEFAULT_MODEL,
    force: bool = False,
) -> dict:
    """
    Monta o JSONL, faz upload para a Files API e cria o batch.

    Args:
        course_ids: Lista de IDs de cursos a classificar.
        model:      Modelo a usar. Default: gpt-4.1.
        force:      Se True, reclassifica mesmo que já exista resultado salvo.

    Returns:
        {"batch_id": str | None, "submitted": [ids], "skipped": [ids], "status": str}
    """
    client = _get_client()
    biblioteca_context = f"Biblioteca de Competências e Habilidades:\n\n{_BIBLIOTECA_JSON}"
    system_content = f"{biblioteca_context}\n\n---\n\n{SYSTEM_PROMPT}"

    lines = []
    skipped = []
    submitted_ids = []

    for course_id in course_ids:
        dados = await get_course_dados(course_id)
        if not dados:
            print(f"[batch/openai/padrao] Curso {course_id} não encontrado, pulando")
            skipped.append(course_id)
            continue

        if not force and dados.get(_DB_FIELD) is not None:
            skipped.append(course_id)
            continue

        transcricoes = extrair_transcricoes(dados)
        if not transcricoes:
            print(f"[batch/openai/padrao] Curso {course_id} sem transcrições, pulando")
            skipped.append(course_id)
            continue

        lines.append(json.dumps({
            "custom_id": str(course_id),
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "max_completion_tokens": 4096,
                "messages": [
                    {"role": "system", "content": system_content},
                    {
                        "role": "user",
                        "content": USER_PROMPT_TEMPLATE.format(transcricao=transcricoes),
                    },
                ],
            },
        }, ensure_ascii=False))
        submitted_ids.append(course_id)

    if not lines:
        return {"batch_id": None, "submitted": [], "skipped": skipped, "status": None}

    jsonl_bytes = "\n".join(lines).encode("utf-8")
    uploaded = client.files.create(
        file=("batch_padrao.jsonl", io.BytesIO(jsonl_bytes), "application/jsonl"),
        purpose="batch",
    )
    batch = client.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"variant": _VARIANT},
    )
    print(f"[batch/openai/padrao] Batch criado: {batch.id} ({len(lines)} cursos)")

    return {
        "batch_id": batch.id,
        "submitted": submitted_ids,
        "skipped": skipped,
        "status": batch.status,
    }


def status(batch_id: str) -> dict:
    """
    Consulta o status de um batch na API OpenAI.

    Returns:
        {"batch_id": str, "status": str, "request_counts": {...}, "output_file_id": str | None, ...}
    """
    client = _get_client()
    batch = client.batches.retrieve(batch_id)
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "request_counts": {
            "total": batch.request_counts.total,
            "completed": batch.request_counts.completed,
            "failed": batch.request_counts.failed,
        },
        "output_file_id": batch.output_file_id,
        "error_file_id": batch.error_file_id,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "metadata": batch.metadata,
    }


async def salvar(batch_id: str) -> dict:
    """
    Lê o arquivo de saída do batch e persiste em dados['competencias_batch_openai_padrao'].

    Só deve ser chamado quando status == "completed".

    Returns:
        {"saved": [ids], "errors": [ids], "total": int}
    """
    client = _get_client()

    batch = client.batches.retrieve(batch_id)
    if not batch.output_file_id:
        raise ValueError(f"Batch {batch_id} ainda não tem output_file_id (status: {batch.status})")

    content = client.files.content(batch.output_file_id).content.decode("utf-8")
    pool = await get_pool()
    saved = []
    errors = []

    for line in content.strip().splitlines():
        if not line.strip():
            continue
        try:
            result = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[batch/openai/padrao] Linha inválida no JSONL: {e}")
            continue

        course_id_str = result.get("custom_id", "")
        try:
            course_id = int(course_id_str)
        except ValueError:
            print(f"[batch/openai/padrao] custom_id inválido: {course_id_str}")
            errors.append(course_id_str)
            continue

        response = result.get("response", {})
        if response.get("status_code") != 200:
            print(f"[batch/openai/padrao] Curso {course_id}: status_code={response.get('status_code')}")
            errors.append(course_id)
            continue

        try:
            texto = response["body"]["choices"][0]["message"]["content"]
            competencias = _parsear_resposta(texto)
            competencias = _validar_competencias(competencias)
        except Exception as e:
            print(f"[batch/openai/padrao] Curso {course_id}: erro ao parsear — {e}")
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
        print(f"[batch/openai/padrao] Curso {course_id}: {len(competencias)} competências salvas")

    return {"saved": saved, "errors": errors, "total": len(saved) + len(errors)}
