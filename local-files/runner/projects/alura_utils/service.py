"""
Orquestração do fluxo de extração de transcrições.
Combina scraper (Playwright) + repository (PostgreSQL).
"""

from projects.alura_utils.repository import get_alura_updated_at, get_course, upsert_transcricao
from projects.alura_utils.scraper import alura_session, get_sections, get_transcricao, get_video_tasks


async def sincronizar_transcricoes(course_id: int) -> dict:
    """
    Abre sessão no Admin Alura e sincroniza as transcrições do curso com o banco.
    - Sections e tasks são listadas com suas datas de atualização (scraping leve).
    - Transcrições são re-extraídas apenas quando a data mudou ou o registro não existe.
    - Retorna os dados completos do curso a partir do banco.
    """
    async with alura_session() as page:
        sections = await get_sections(page, course_id)

        for section in sections:
            video_tasks = await get_video_tasks(page, course_id, section["section_id"])

            for task in video_tasks:
                db_updated_at = await get_alura_updated_at(task["task_id"])
                needs_update = (
                    db_updated_at is None
                    or db_updated_at.replace(tzinfo=None) < task["updated_at"]
                )

                if needs_update:
                    transcricao = await get_transcricao(
                        page, course_id, section["section_id"], task["task_id"]
                    )
                    await upsert_transcricao(
                        task_id=task["task_id"],
                        course_id=course_id,
                        section_id=section["section_id"],
                        section_titulo=section["titulo"],
                        task_titulo=task["titulo"],
                        transcricao=transcricao,
                        alura_updated_at=task["updated_at"],
                    )

    return await get_course(course_id)
