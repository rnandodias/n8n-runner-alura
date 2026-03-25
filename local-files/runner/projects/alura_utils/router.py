"""
Router FastAPI para utilitários da Alura.
Prefix: /utils

Endpoints:
  POST /utils/cursos              — sincroniza curso (scraping + API pública)
  GET  /utils/cursos/{id}         — retorna curso do banco sem scraping
  POST /utils/carreiras/sync      — atualiza cache de todas as carreiras
  POST /utils/carreiras           — adiciona novo slug de carreira
  GET  /utils/carreiras           — lista carreiras cadastradas
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from projects.alura_utils.queue import scraping_semaphore
from projects.alura_utils.repository import get_all_carreiras, get_course_dados, insert_carreira_slug
from projects.alura_utils.service import sincronizar_carreiras, sincronizar_curso

router = APIRouter(prefix="/utils")


class CursoPayload(BaseModel):
    course_id: int


class CarreiraPayload(BaseModel):
    slug: str
    titulo: str


@router.post("/cursos")
async def post_cursos(payload: CursoPayload):
    async with scraping_semaphore:
        try:
            return await sincronizar_curso(payload.course_id)
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao sincronizar curso: {e}")


@router.get("/cursos/{course_id}")
async def get_cursos(course_id: int):
    try:
        dados = await get_course_dados(course_id)
        if not dados:
            raise HTTPException(status_code=404, detail=f"Curso {course_id} não encontrado")
        return {"course_id": course_id, **dados}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar curso: {e}")


@router.post("/carreiras/sync")
async def post_carreiras_sync():
    try:
        return await sincronizar_carreiras()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao sincronizar carreiras: {e}")


@router.post("/carreiras")
async def post_carreiras(payload: CarreiraPayload):
    try:
        await insert_carreira_slug(payload.slug, payload.titulo)
        return {"ok": True, "slug": payload.slug}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar carreira: {e}")


@router.get("/carreiras")
async def get_carreiras():
    try:
        carreiras = await get_all_carreiras()
        return {"carreiras": carreiras}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar carreiras: {e}")
