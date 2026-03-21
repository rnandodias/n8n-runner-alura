"""
Router FastAPI para utilitários da Alura.
Prefix: /utils

Funcionalidades:
  POST /utils/transcricoes  — extrai transcrições de vídeos de um curso
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from projects.alura_utils.scraper import extrair_transcricoes_curso

router = APIRouter(prefix="/utils")


class TranscricoesPayload(BaseModel):
    course_id: int


@router.post("/transcricoes")
async def obter_transcricoes(payload: TranscricoesPayload):
    try:
        return await extrair_transcricoes_curso(payload.course_id)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao extrair transcrições: {e}")
