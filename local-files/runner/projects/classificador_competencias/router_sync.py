"""
Router FastAPI para classificação síncrona de competências de UM curso novo.
Prefix: /utils

Endpoint:
  POST /utils/cursos/{course_id}/competencias/sync  — sincroniza (se preciso), classifica e persiste

Replica o processo do BATCH PADRÃO (transcrição bruta → Opus claude-opus-4-6,
biblioteca completa, passo único), porém síncrono e para 1 curso. Pensado para
cursos recém-lançados que ainda não existem no banco.

Resultado salvo em dados['competencias'] — mesmo campo do batch padrão.

Reaproveita:
  - sincronizar_curso          (alura_utils.service)     — insere o curso e popula transcrições
  - classificar_competencias   (classificador.service)   — passo único, biblioteca completa
  - update_course_competencias (alura_utils.repository)  — persiste em dados.competencias

Remoção limpa: apagar este arquivo + remover 2 linhas de app.py.
"""

from fastapi import APIRouter, HTTPException

from projects.alura_utils.queue import scraping_semaphore
from projects.alura_utils.repository import get_course_dados, update_course_competencias
from projects.alura_utils.service import sincronizar_curso
from projects.classificador_competencias.service import classificar_competencias

router = APIRouter(prefix="/utils")

_MODELO_PADRAO = "claude-opus-4-6"


@router.post("/cursos/{course_id}/competencias/sync")
async def post_classificar_competencias_sync(course_id: int, force: bool = False):
    try:
        dados = await get_course_dados(course_id)
        sincronizado = False

        # Curso novo: não existe no banco → sincroniza (scraping + API) para inserir e popular transcrições.
        if not dados:
            async with scraping_semaphore:
                await sincronizar_curso(course_id)
            dados = await get_course_dados(course_id)
            sincronizado = True
            if not dados:
                raise HTTPException(
                    status_code=502,
                    detail=f"Curso {course_id} não pôde ser sincronizado",
                )

        # Já classificado e sem force → retorna o que está salvo, sem reclassificar.
        if not force and dados.get("competencias") is not None:
            return {
                "course_id": course_id,
                "total": len(dados["competencias"]),
                "competencias": dados["competencias"],
                "from_cache": True,
                "sincronizado": sincronizado,
            }

        competencias = await classificar_competencias(
            course_id,
            provider="anthropic",
            model=_MODELO_PADRAO,
        )
        await update_course_competencias(course_id, competencias)

        return {
            "course_id": course_id,
            "total": len(competencias),
            "competencias": competencias,
            "from_cache": False,
            "sincronizado": sincronizado,
        }
    except HTTPException:
        raise
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao classificar competências (sync): {e}")
