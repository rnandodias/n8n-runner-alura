"""
Router FastAPI para classificação de competências de cursos.
Prefix: /utils (compartilhado com alura_utils)

Endpoints:
  POST /utils/cursos/{course_id}/competencias  — classifica e persiste competências no banco
  GET  /utils/cursos/{course_id}/competencias  — retorna competências já classificadas
"""

from fastapi import APIRouter, HTTPException

from projects.alura_utils.repository import get_course_dados, update_course_competencias
from projects.classificador_competencias.service import classificar_competencias

router = APIRouter(prefix="/utils")


@router.post("/cursos/{course_id}/competencias")
async def post_classificar_competencias(
    course_id: int,
    provider: str = "anthropic",
    model: str = None,
):
    try:
        competencias = await classificar_competencias(course_id, provider=provider, model=model)
        await update_course_competencias(course_id, competencias)
        return {
            "course_id": course_id,
            "total": len(competencias),
            "competencias": competencias,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao classificar competências: {e}")


@router.get("/cursos/{course_id}/competencias")
async def get_competencias(course_id: int):
    try:
        dados = await get_course_dados(course_id)
        if not dados:
            raise HTTPException(status_code=404, detail=f"Curso {course_id} não encontrado")
        competencias = dados.get("competencias")
        if competencias is None:
            raise HTTPException(
                status_code=404,
                detail=f"Curso {course_id} ainda não foi classificado"
            )
        return {
            "course_id": course_id,
            "total": len(competencias),
            "competencias": competencias,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar competências: {e}")
