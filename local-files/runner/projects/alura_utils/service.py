"""
Orquestração do fluxo de extração de tarefas do Admin Alura.
Combina scraper (Playwright) + repository (PostgreSQL).
"""

from datetime import datetime

from projects.alura_utils.repository import get_course_dados, upsert_course
from projects.alura_utils.scraper import alura_session, get_sections, get_task_details, get_tasks


async def sincronizar_tarefas(course_id: int) -> dict:
    """
    Sincroniza todas as tarefas ativas do curso com o banco.

    - Reconstrói o documento JSON do curso a cada chamada (tarefas removidas
      do Alura desaparecem naturalmente).
    - Detalhes de cada tarefa são re-extraídos apenas quando a data da
      listagem do Admin mudou em relação ao que está cacheado no banco.
    - Retorna o documento completo salvo.
    """
    existing = await get_course_dados(course_id)

    # Monta cache de atividades já salvas: {task_id: atividade_dict}
    task_cache: dict[int, dict] = {}
    if existing:
        for aula in existing.get("aulas", []):
            for atividade in aula.get("atividades", []):
                task_cache[atividade["task_id"]] = atividade

    async with alura_session() as page:
        course_name, sections = await get_sections(page, course_id)

        aulas = []
        for position, section in enumerate(sections, start=1):
            sid = section["section_id"]
            tasks = await get_tasks(page, course_id, sid)

            atividades = []
            for task in tasks:
                task_id = task["task_id"]
                alura_updated_at: datetime = task["alura_updated_at"]

                cached = task_cache.get(task_id)
                if cached:
                    cached_dt = datetime.fromisoformat(cached["alura_updated_at"])
                    needs_update = cached_dt < alura_updated_at
                else:
                    needs_update = True

                if needs_update:
                    details = await get_task_details(page, course_id, sid, task_id)
                    atividade = {
                        "task_id": task_id,
                        "alura_updated_at": alura_updated_at.isoformat(),
                        **details,
                    }
                else:
                    atividade = cached

                atividades.append(atividade)

            aulas.append({
                "section_id": sid,
                "titulo": section["titulo"],
                "position": position,
                "atividades": atividades,
            })

    dados = {"nome": course_name, "aulas": aulas}
    await upsert_course(course_id, dados)
    return {"course_id": course_id, **dados}
