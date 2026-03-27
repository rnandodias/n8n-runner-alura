"""
Router FastAPI para classificação de competências em batch.
Prefix: /utils

Endpoints (13 total):

  Anthropic — padrão (transcrições brutas → Opus):
    POST /utils/competencias/batch/anthropic/padrao/submit
    GET  /utils/competencias/batch/anthropic/padrao/status/{batch_id}
    POST /utils/competencias/batch/anthropic/padrao/salvar/{batch_id}

  Anthropic — otimizado (Haiku sumariza → Opus classifica em batch):
    POST /utils/competencias/batch/anthropic/otimizado/submit
    GET  /utils/competencias/batch/anthropic/otimizado/status/{batch_id}
    POST /utils/competencias/batch/anthropic/otimizado/salvar/{batch_id}

  OpenAI — padrão (transcrições brutas → gpt-4.1):
    POST /utils/competencias/batch/openai/padrao/submit
    GET  /utils/competencias/batch/openai/padrao/status/{batch_id}
    POST /utils/competencias/batch/openai/padrao/salvar/{batch_id}

  OpenAI — otimizado (gpt-4.1-mini sumariza → gpt-4.1 classifica em batch):
    POST /utils/competencias/batch/openai/otimizado/submit
    GET  /utils/competencias/batch/openai/otimizado/status/{batch_id}
    POST /utils/competencias/batch/openai/otimizado/salvar/{batch_id}

  OpenAI — webhook (recebe notificação de batch concluído):
    POST /utils/competencias/batch/openai/webhook

Remoção limpa: apagar a pasta batch/ inteira + remover 2 linhas de app.py.
"""

import hashlib
import hmac
import os
import time

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from projects.classificador_competencias.batch.anthropic import (
    service_otimizado as anthropic_otimizado,
)
from projects.classificador_competencias.batch.anthropic import (
    service_padrao as anthropic_padrao,
)
from projects.classificador_competencias.batch.openai import (
    service_otimizado as openai_otimizado,
)
from projects.classificador_competencias.batch.openai import service_padrao as openai_padrao

router = APIRouter(prefix="/utils")


# ─── Modelos de request ───────────────────────────────────────────────────────


class BatchSubmitPadraoRequest(BaseModel):
    course_ids: list[int]
    force: bool = False
    model: str | None = None


class BatchSubmitOtimizadoRequest(BaseModel):
    course_ids: list[int]
    force: bool = False
    modelo_sumarizacao: str | None = None
    modelo_classificacao: str | None = None


# ─── Anthropic — padrão ───────────────────────────────────────────────────────


@router.post("/competencias/batch/anthropic/padrao/submit")
async def post_anthropic_padrao_submit(body: BatchSubmitPadraoRequest):
    """
    Submete um batch Anthropic padrão.

    Envia as transcrições brutas de cada curso para o Opus via Message Batches API.
    Retorna o batch_id para monitoramento.
    """
    try:
        kwargs = {"course_ids": body.course_ids, "force": body.force}
        if body.model:
            kwargs["model"] = body.model
        return await anthropic_padrao.submit(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao submeter batch Anthropic padrão: {e}")


@router.get("/competencias/batch/anthropic/padrao/status/{batch_id}")
def get_anthropic_padrao_status(batch_id: str):
    """Consulta o status de um batch Anthropic padrão."""
    try:
        return anthropic_padrao.status(batch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar status: {e}")


@router.post("/competencias/batch/anthropic/padrao/salvar/{batch_id}")
async def post_anthropic_padrao_salvar(batch_id: str):
    """
    Lê os resultados de um batch Anthropic padrão concluído e persiste no banco.

    Chame este endpoint somente quando processing_status == "ended".
    Salva em dados['competencias_batch_anthropic_padrao'].
    """
    try:
        return await anthropic_padrao.salvar(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar resultados: {e}")


# ─── Anthropic — otimizado ────────────────────────────────────────────────────


@router.post("/competencias/batch/anthropic/otimizado/submit")
async def post_anthropic_otimizado_submit(body: BatchSubmitOtimizadoRequest):
    """
    Submete um batch Anthropic otimizado.

    Step 1 (síncrono): Haiku sumariza cada curso.
    Step 2 (batch):    Opus classifica a partir dos resumos.
    Retorna o batch_id para monitoramento.
    """
    try:
        kwargs = {"course_ids": body.course_ids, "force": body.force}
        if body.modelo_sumarizacao:
            kwargs["modelo_sumarizacao"] = body.modelo_sumarizacao
        if body.modelo_classificacao:
            kwargs["modelo_classificacao"] = body.modelo_classificacao
        return await anthropic_otimizado.submit(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao submeter batch Anthropic otimizado: {e}")


@router.get("/competencias/batch/anthropic/otimizado/status/{batch_id}")
def get_anthropic_otimizado_status(batch_id: str):
    """Consulta o status de um batch Anthropic otimizado."""
    try:
        return anthropic_otimizado.status(batch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar status: {e}")


@router.post("/competencias/batch/anthropic/otimizado/salvar/{batch_id}")
async def post_anthropic_otimizado_salvar(batch_id: str):
    """
    Lê os resultados de um batch Anthropic otimizado concluído e persiste no banco.

    Chame este endpoint somente quando processing_status == "ended".
    Salva em dados['competencias_batch_anthropic_otimizado'].
    """
    try:
        return await anthropic_otimizado.salvar(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar resultados: {e}")


# ─── OpenAI — padrão ──────────────────────────────────────────────────────────


@router.post("/competencias/batch/openai/padrao/submit")
async def post_openai_padrao_submit(body: BatchSubmitPadraoRequest):
    """
    Submete um batch OpenAI padrão.

    Faz upload do JSONL com transcrições brutas e cria o batch para gpt-4.1.
    Retorna o batch_id para monitoramento.
    """
    try:
        kwargs = {"course_ids": body.course_ids, "force": body.force}
        if body.model:
            kwargs["model"] = body.model
        return await openai_padrao.submit(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao submeter batch OpenAI padrão: {e}")


@router.get("/competencias/batch/openai/padrao/status/{batch_id}")
def get_openai_padrao_status(batch_id: str):
    """Consulta o status de um batch OpenAI padrão."""
    try:
        return openai_padrao.status(batch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar status: {e}")


@router.post("/competencias/batch/openai/padrao/salvar/{batch_id}")
async def post_openai_padrao_salvar(batch_id: str):
    """
    Lê os resultados de um batch OpenAI padrão concluído e persiste no banco.

    Chame este endpoint somente quando status == "completed".
    Salva em dados['competencias_batch_openai_padrao'].
    """
    try:
        return await openai_padrao.salvar(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar resultados: {e}")


# ─── OpenAI — otimizado ───────────────────────────────────────────────────────


@router.post("/competencias/batch/openai/otimizado/submit")
async def post_openai_otimizado_submit(body: BatchSubmitOtimizadoRequest):
    """
    Submete um batch OpenAI otimizado.

    Step 1 (síncrono): gpt-4.1-mini sumariza cada curso.
    Step 2 (batch):    gpt-4.1 classifica a partir dos resumos.
    Retorna o batch_id para monitoramento.
    """
    try:
        kwargs = {"course_ids": body.course_ids, "force": body.force}
        if body.modelo_sumarizacao:
            kwargs["modelo_sumarizacao"] = body.modelo_sumarizacao
        if body.modelo_classificacao:
            kwargs["modelo_classificacao"] = body.modelo_classificacao
        return await openai_otimizado.submit(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao submeter batch OpenAI otimizado: {e}")


@router.get("/competencias/batch/openai/otimizado/status/{batch_id}")
def get_openai_otimizado_status(batch_id: str):
    """Consulta o status de um batch OpenAI otimizado."""
    try:
        return openai_otimizado.status(batch_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar status: {e}")


@router.post("/competencias/batch/openai/otimizado/salvar/{batch_id}")
async def post_openai_otimizado_salvar(batch_id: str):
    """
    Lê os resultados de um batch OpenAI otimizado concluído e persiste no banco.

    Chame este endpoint somente quando status == "completed".
    Salva em dados['competencias_batch_openai_otimizado'].
    """
    try:
        return await openai_otimizado.salvar(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar resultados: {e}")


# ─── OpenAI — webhook ─────────────────────────────────────────────────────────


def _verify_openai_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """
    Verifica a assinatura do webhook OpenAI.

    Formato do header OpenAI-Signature: t=TIMESTAMP,v1=HEX_SIGNATURE
    Signed payload: f"{timestamp}.{raw_body}"
    """
    try:
        parts = dict(item.split("=", 1) for item in signature_header.split(","))
        timestamp = parts.get("t")
        v1_sig = parts.get("v1")
        if not timestamp or not v1_sig:
            return False
        # Rejeita payloads com mais de 5 minutos de atraso
        if abs(time.time() - int(timestamp)) > 300:
            return False
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, v1_sig)
    except Exception:
        return False


@router.post("/competencias/batch/openai/webhook")
async def post_openai_webhook(
    request: Request,
    openai_signature: str = Header(None, alias="OpenAI-Signature"),
):
    """
    Recebe notificação da OpenAI quando um batch é concluído.

    Usa o campo metadata.variant para rotear ao salvar correto:
      - "padrao"    → salva em competencias_batch_openai_padrao
      - "otimizado" → salva em competencias_batch_openai_otimizado

    Verificação de assinatura: configure OPENAI_WEBHOOK_SECRET no .env.
    Se a variável não estiver configurada, a verificação é ignorada (não recomendado em produção).
    """
    payload = await request.body()
    secret = os.getenv("OPENAI_WEBHOOK_SECRET")

    if secret:
        if not openai_signature:
            raise HTTPException(status_code=401, detail="Header OpenAI-Signature ausente")
        if not _verify_openai_signature(payload, openai_signature, secret):
            raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event_type = event.get("type", "")
    if event_type != "batch.completed":
        # Outros eventos (batch.failed, etc.) são ignorados silenciosamente
        return {"ok": True, "ignored": True, "type": event_type}

    data = event.get("data", {})
    batch_id = data.get("id")
    variant = (data.get("metadata") or {}).get("variant")

    if not batch_id:
        raise HTTPException(status_code=400, detail="batch_id ausente no payload")

    if variant == "padrao":
        resultado = await openai_padrao.salvar(batch_id)
    elif variant == "otimizado":
        resultado = await openai_otimizado.salvar(batch_id)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"metadata.variant inválido ou ausente: '{variant}'. Use 'padrao' ou 'otimizado'.",
        )

    return {"ok": True, "batch_id": batch_id, "variant": variant, **resultado}
