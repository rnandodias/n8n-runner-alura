"""
Router FastAPI para utilitários da Alura.
Prefix: /utils

Funcionalidades:
  POST /utils/tarefas          — sincroniza e retorna todas as tarefas de um curso
  GET  /utils/tarefas/{id}     — retorna tarefas do banco sem scraping
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from projects.alura_utils.queue import scraping_semaphore
from projects.alura_utils.repository import get_course_dados
from projects.alura_utils.service import sincronizar_tarefas

router = APIRouter(prefix="/utils")


class TarefasPayload(BaseModel):
    course_id: int


@router.post("/tarefas")
async def post_tarefas(payload: TarefasPayload):
    async with scraping_semaphore:
        try:
            return await sincronizar_tarefas(payload.course_id)
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao sincronizar tarefas: {e}")


@router.get("/tarefas/{course_id}")
async def get_tarefas(course_id: int):
    try:
        dados = await get_course_dados(course_id)
        if not dados:
            raise HTTPException(
                status_code=404,
                detail=f"Nenhuma tarefa encontrada para o curso {course_id}",
            )
        return {"course_id": course_id, **dados}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar tarefas: {e}")
