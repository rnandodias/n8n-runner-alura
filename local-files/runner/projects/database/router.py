"""
Router FastAPI para diagnóstico/inspeção do banco.
Prefix: /database

Endpoints:
  GET /database/cursos/total                       — total de cursos no banco
  GET /database/cursos/sem-competencias            — cursos sem o campo `competencias` preenchido
  GET /database/cursos/sem-transcricoes            — cursos sem nenhuma transcrição de vídeo
  GET /database/cursos/resumo                      — os 3 números acima em uma chamada
  GET /database/cursos/exportar-xlsx-comercial     — planilha XLSX comercial (6 tipos de aba)
"""

import io
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from projects.database.comercial import build_workbook
from projects.database.repository import (
    contar_cursos_total,
    listar_cursos_sem_competencias,
    listar_cursos_sem_transcricoes,
    listar_todos_cursos_com_dados,
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


@router.get("/cursos/exportar-xlsx-comercial")
async def get_exportar_xlsx_comercial():
    """
    Gera planilha XLSX rica com todos os cursos para uso do time comercial B2B.
    Múltiplas abas: Capa+Índice, Catálogo Geral, por Categoria, por Carreira, por Competência.
    """
    try:
        print("[exportar-xlsx-comercial] carregando cursos do banco…", flush=True)
        cursos = await listar_todos_cursos_com_dados()
        print(
            f"[exportar-xlsx-comercial] {len(cursos)} cursos carregados, montando workbook…",
            flush=True,
        )

        xlsx_bytes = build_workbook(cursos)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"catalogo_alura_comercial_{timestamp}.xlsx"
        size_mb = len(xlsx_bytes) / 1024 / 1024
        print(
            f"[exportar-xlsx-comercial] workbook pronto — {size_mb:.1f} MB → {filename}",
            flush=True,
        )

        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar planilha: {e}")
