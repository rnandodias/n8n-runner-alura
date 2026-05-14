"""
Router FastAPI para diagnóstico/inspeção do banco.
Prefix: /database

Endpoints:
  GET /database/cursos/total              — total de cursos no banco
  GET /database/cursos/sem-competencias   — cursos sem o campo `competencias` preenchido
  GET /database/cursos/sem-transcricoes   — cursos sem nenhuma transcrição de vídeo
  GET /database/cursos/resumo             — os 3 números acima em uma chamada
"""

from fastapi import APIRouter, HTTPException

from projects.database.repository import (
    contar_cursos_total,
    listar_cursos_sem_competencias,
    listar_cursos_sem_transcricoes,
)

router = APIRouter(prefix="/database")


@router.get("/cursos/total")
async def get_cursos_total():
    try:
        return {"total": await contar_cursos_total()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao contar cursos: {e}")


@router.get("/cursos/sem-competencias")
async def get_cursos_sem_competencias():
    try:
        ids = await listar_cursos_sem_competencias()
        return {"total": len(ids), "course_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")


@router.get("/cursos/sem-transcricoes")
async def get_cursos_sem_transcricoes():
    try:
        ids = await listar_cursos_sem_transcricoes()
        return {"total": len(ids), "course_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")


@router.get("/cursos/resumo")
async def get_cursos_resumo():
    try:
        total = await contar_cursos_total()
        sem_comp = await listar_cursos_sem_competencias()
        sem_trans = await listar_cursos_sem_transcricoes()
        return {
            "total_cursos": total,
            "sem_competencias": len(sem_comp),
            "sem_transcricoes": len(sem_trans),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")
