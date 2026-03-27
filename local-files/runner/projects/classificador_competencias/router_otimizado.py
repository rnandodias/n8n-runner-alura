"""
Router FastAPI para classificação de competências otimizada (dois steps, custo reduzido).
Prefix: /utils

Endpoints:
  POST /utils/cursos/{course_id}/competencias/otimizado  — classifica em dois steps e persiste
  GET  /utils/cursos/{course_id}/competencias/otimizado  — retorna resultado salvo

Resultado salvo em dados['competencias_otimizado'] — separado de dados['competencias'].

Remoção limpa: apagar este arquivo + service_otimizado.py + prompts_otimizado.py
               + remover 2 linhas de app.py.
"""

from fastapi import APIRouter, HTTPException

from projects.alura_utils.repository import get_course_dados
from projects.classificador_competencias.service_otimizado import (
    _salvar_competencias_otimizado,
    classificar_competencias_otimizado,
)

router = APIRouter(prefix="/utils")


@router.post("/cursos/{course_id}/competencias/otimizado")
async def post_classificar_competencias_otimizado(
    course_id: int,
    force: bool = False,
    modelo_sumarizacao: str = "claude-haiku-4-5-20251001",
    modelo_classificacao: str = "claude-opus-4-6",
):
    try:
        dados = await get_course_dados(course_id)
        if not dados:
            raise HTTPException(status_code=404, detail=f"Curso {course_id} não encontrado")

        if not force and dados.get("competencias_otimizado") is not None:
            return {
                "course_id": course_id,
                "total": len(dados["competencias_otimizado"]),
                "competencias": dados["competencias_otimizado"],
                "resumo": dados.get("competencias_otimizado_resumo"),
                "from_cache": True,
            }

        resultado = await classificar_competencias_otimizado(
            course_id,
            modelo_sumarizacao=modelo_sumarizacao,
            modelo_classificacao=modelo_classificacao,
        )
        await _salvar_competencias_otimizado(course_id, resultado["competencias"])
        return {
            "course_id": course_id,
            "total": len(resultado["competencias"]),
            "competencias": resultado["competencias"],
            "resumo": resultado["resumo"],
            "from_cache": False,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao classificar competências (otimizado): {e}")


@router.get("/cursos/{course_id}/competencias/otimizado")
async def get_competencias_otimizado(course_id: int):
    try:
        dados = await get_course_dados(course_id)
        if not dados:
            raise HTTPException(status_code=404, detail=f"Curso {course_id} não encontrado")
        competencias = dados.get("competencias_otimizado")
        if competencias is None:
            raise HTTPException(
                status_code=404,
                detail=f"Curso {course_id} ainda não foi classificado pelo método otimizado"
            )
        return {
            "course_id": course_id,
            "total": len(competencias),
            "competencias": competencias,
            "resumo": dados.get("competencias_otimizado_resumo"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar competências (otimizado): {e}")
