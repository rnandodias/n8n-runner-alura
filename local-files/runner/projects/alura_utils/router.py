"""
Router FastAPI para utilitários da Alura.
Prefix: /utils

Funcionalidades:
  POST /utils/transcricoes          — sincroniza e retorna transcrições de um curso
  GET  /utils/transcricoes/{id}     — retorna transcrições do banco sem scraping
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from projects.alura_utils.queue import scraping_semaphore
from projects.alura_utils.repository import get_course
from projects.alura_utils.service import sincronizar_transcricoes

router = APIRouter(prefix="/utils")


class TranscricoesPayload(BaseModel):
    course_id: int


@router.post("/transcricoes")
async def post_transcricoes(payload: TranscricoesPayload):
    async with scraping_semaphore:
        try:
            return await sincronizar_transcricoes(payload.course_id)
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao sincronizar transcrições: {e}")


@router.get("/transcricoes/{course_id}")
async def get_transcricoes(course_id: int):
    try:
        result = await get_course(course_id)
        if not result["sections"]:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhuma transcrição encontrada para o curso {course_id}",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar transcrições: {e}")
