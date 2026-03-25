"""
Orquestração do fluxo de sincronização de cursos e carreiras.
Combina API pública Alura + scraper Playwright + PostgreSQL.
"""

from datetime import datetime

from projects.alura_utils.api_client import get_career_api, get_course_api
from projects.alura_utils.repository import (
    get_all_carreiras,
    get_course_dados,
    insert_carreira_slug,
    update_course_carreiras,
    upsert_carreira,
    upsert_course,
)
from projects.alura_utils.scraper import (
    alura_session,
    get_course_slug,
    get_sections,
    get_task_details,
    get_tasks,
)


def _build_task_cache(existing: dict | None) -> dict[int, dict]:
    if not existing:
        return {}
    return {
        atividade["task_id"]: atividade
        for aula in existing.get("aulas", [])
        for atividade in aula.get("atividades", [])
    }


async def _scrape_aulas(page, course_id: int, task_cache: dict) -> list[dict]:
    sections = await get_sections(page, course_id)
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
    return aulas


def _get_carreiras_para_curso(slug: str, carreiras_cache: list[dict]) -> list[dict]:
    resultado = []
    for carreira in carreiras_cache:
        dados = carreira.get("dados")
        if not dados:
            continue
        for step in dados.get("steps", []):
            for content in step.get("contents", []):
                if content.get("slug") == slug:
                    resultado.append({
                        "slug": carreira["slug"],
                        "titulo": carreira["titulo"],
                        "step_titulo": step["title"],
                        "step_position": step["position"],
                    })
    return resultado


def _build_dados(api_data: dict, aulas: list, carreiras: list) -> dict:
    slug = api_data.get("slug", "")
    return {
        "slug": slug,
        "link": f"https://cursos.alura.com.br/course/{slug}",
        "data_atualizacao": api_data.get("data_atualizacao"),
        "nome": api_data.get("nome"),
        "metadescription": api_data.get("metadescription"),
        "meta_title": api_data.get("meta_title"),
        "categoria": api_data.get("categoria"),
        "subcategoria": api_data.get("subcategoria"),
        "instrutores": api_data.get("instrutores", []),
        "ementa": api_data.get("ementa", []),
        "chamadas": api_data.get("chamadas", []),
        "publico_alvo": api_data.get("publico_alvo"),
        "carga_horaria": api_data.get("carga_horaria"),
        "nota": api_data.get("nota"),
        "quantidade_alunos": api_data.get("quantidade_alunos"),
        "quantidade_avaliacoes": api_data.get("quantidade_avaliacoes"),
        "carreiras": carreiras,
        "aulas": aulas,
    }


async def sincronizar_curso(course_id: int) -> dict:
    existing = await get_course_dados(course_id)
    slug = existing.get("slug") if existing else None
    task_cache = _build_task_cache(existing)
    carreiras_cache = await get_all_carreiras()

    if not slug:
        # Primeira vez: abre browser para obter slug + raspa tarefas na mesma sessão
        async with alura_session() as page:
            slug = await get_course_slug(page, course_id)
            api_data = await get_course_api(slug)
            aulas = await _scrape_aulas(page, course_id, task_cache)
    else:
        api_data = await get_course_api(slug)
        stored_date = existing.get("data_atualizacao") if existing else None

        if stored_date == api_data.get("data_atualizacao"):
            return {"course_id": course_id, **existing}

        async with alura_session() as page:
            aulas = await _scrape_aulas(page, course_id, task_cache)

    carreiras = _get_carreiras_para_curso(slug, carreiras_cache)
    dados = _build_dados(api_data, aulas, carreiras)
    await upsert_course(course_id, dados)
    return {"course_id": course_id, **dados}


async def sincronizar_carreiras() -> dict:
    carreiras = await get_all_carreiras()
    resultados = []

    for carreira in carreiras:
        slug = carreira["slug"]
        titulo = carreira["titulo"]
        try:
            dados = await get_career_api(slug)
            await upsert_carreira(slug, titulo, dados)
            resultados.append({"slug": slug, "ok": True})
        except Exception as e:
            resultados.append({"slug": slug, "ok": False, "erro": str(e)})

    # Atualiza o campo "carreiras" em todos os cursos afetados
    carreiras_atualizadas = await get_all_carreiras()
    affected_slugs: set[str] = set()
    for carreira in carreiras_atualizadas:
        dados = carreira.get("dados")
        if dados:
            for step in dados.get("steps", []):
                for content in step.get("contents", []):
                    cs = content.get("slug")
                    if cs:
                        affected_slugs.add(cs)

    for course_slug in affected_slugs:
        carreiras_do_curso = _get_carreiras_para_curso(course_slug, carreiras_atualizadas)
        await update_course_carreiras(course_slug, carreiras_do_curso)

    ok_count = sum(1 for r in resultados if r["ok"])
    erros = [r for r in resultados if not r["ok"]]
    return {"sincronizadas": ok_count, "erros": erros, "detalhes": resultados}
