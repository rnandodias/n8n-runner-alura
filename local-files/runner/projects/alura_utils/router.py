"""
Router FastAPI para utilitários da Alura.
Prefix: /utils

Endpoints:
  POST /utils/cursos              — sincroniza curso (scraping + API pública)
  POST /utils/cursos/batch        — sincroniza vários cursos em uma única sessão Alura
  GET  /utils/cursos/{id}         — retorna curso do banco sem scraping
  GET  /utils/cursos/slug/{slug}  — retorna curso do banco buscando pelo slug
  POST /utils/carreiras/sync      — atualiza cache de todas as carreiras
  POST /utils/carreiras           — adiciona novo slug de carreira
  GET  /utils/carreiras           — lista carreiras cadastradas
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from projects.alura_utils.queue import scraping_semaphore
from projects.alura_utils.repository import (
    get_all_carreiras,
    get_course_dados,
    get_course_dados_by_slug,
    insert_carreira_slug,
)
from projects.alura_utils.service import sincronizar_carreiras, sincronizar_curso, sincronizar_cursos_batch

router = APIRouter(prefix="/utils")


class CursoPayload(BaseModel):
    course_id: int


class CursosBatchPayload(BaseModel):
    course_ids: list[int]


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


@router.post("/cursos/batch")
async def post_cursos_batch(payload: CursosBatchPayload):
    if not payload.course_ids:
        raise HTTPException(status_code=400, detail="course_ids não pode ser vazio")
    if len(payload.course_ids) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 cursos por chamada")
    async with scraping_semaphore:
        try:
            return await sincronizar_cursos_batch(payload.course_ids)
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro no batch: {e}")


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


@router.get("/cursos/slug/{slug}")
async def get_cursos_by_slug(slug: str):
    try:
        resultado = await get_course_dados_by_slug(slug)
        if not resultado:
            raise HTTPException(status_code=404, detail=f"Curso com slug '{slug}' não encontrado")
        course_id, dados = resultado
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
