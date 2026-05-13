"""
Orquestração do fluxo de sincronização de cursos e carreiras.
Combina API pública Alura + scraper Playwright + PostgreSQL.
"""

import asyncio
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
    instrutores = [
        {k: v for k, v in instrutor.items() if k != "fotos"}
        for instrutor in api_data.get("instrutores", [])
    ]
    return {
        "slug": slug,
        "link": f"https://cursos.alura.com.br/course/{slug}",
        "data_criacao": api_data.get("data_criacao"),
        "data_atualizacao": api_data.get("data_atualizacao"),
        "nome": api_data.get("nome"),
        "metadescription": api_data.get("metadescription"),
        "meta_title": api_data.get("meta_title"),
        "categoria": api_data.get("categoria"),
        "categorias": api_data.get("categorias", []),
        "subcategoria": api_data.get("subcategoria"),
        "subcategorias": api_data.get("subcategorias", []),
        "instrutores": instrutores,
        "ementa": api_data.get("ementa", []),
        "chamadas": api_data.get("chamadas", []),
        "publico_alvo": api_data.get("publico_alvo"),
        "nota": api_data.get("nota"),
        "nota_disponivel": api_data.get("nota_disponivel"),
        "quantidade_aulas": api_data.get("quantidade_aulas"),
        "minutos_video": api_data.get("minutos_video"),
        "carga_horaria": api_data.get("carga_horaria"),
        "quantidade_atividades": api_data.get("quantidade_atividades"),
        "quantidade_alunos": api_data.get("quantidade_alunos"),
        "quantidade_avaliacoes": api_data.get("quantidade_avaliacoes"),
        "depoimentos": api_data.get("depoimentos", []),
        "formacoes": api_data.get("formacoes", []),
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


async def _sincronizar_curso_com_page(
    course_id: int,
    page,
    api_data: dict | None,
    existing: dict | None,
    carreiras_cache: list[dict],
) -> dict:
    """Sincroniza um curso usando uma page Playwright já logada. Assume que o scraping é necessário."""
    task_cache = _build_task_cache(existing)
    slug = existing.get("slug") if existing else None

    if not slug:
        slug = await get_course_slug(page, course_id)
    if api_data is None:
        api_data = await get_course_api(slug)

    aulas = await _scrape_aulas(page, course_id, task_cache)
    carreiras = _get_carreiras_para_curso(slug, carreiras_cache)
    dados = _build_dados(api_data, aulas, carreiras)
    await upsert_course(course_id, dados)
    return dados


def _resultado_pre(p: dict) -> dict:
    base = {"course_id": p["course_id"], "slug": p["slug"], "status": p["status_pre"]}
    if p["status_pre"] == "erro":
        base["erro"] = p["erro_pre"]
    return base


async def sincronizar_cursos_batch(
    course_ids: list[int],
    delay_segundos: float = 1.5,
) -> dict:
    """Sincroniza múltiplos cursos em uma única sessão Alura."""
    carreiras_cache = await get_all_carreiras()
    plano: list[dict] = []

    for course_id in course_ids:
        try:
            existing = await get_course_dados(course_id)
            slug = existing.get("slug") if existing else None
            api_data = None
            precisa_scraping = True
            status_pre = None

            if slug:
                api_data = await get_course_api(slug)
                if existing and existing.get("data_atualizacao") == api_data.get("data_atualizacao"):
                    precisa_scraping = False
                    status_pre = "unchanged"

            plano.append({
                "course_id": course_id,
                "existing": existing,
                "api_data": api_data,
                "slug": slug,
                "precisa_scraping": precisa_scraping,
                "status_pre": status_pre,
                "erro_pre": None,
            })
        except Exception as e:
            plano.append({
                "course_id": course_id,
                "existing": None,
                "api_data": None,
                "slug": None,
                "precisa_scraping": False,
                "status_pre": "erro",
                "erro_pre": str(e),
            })

    resultados: list[dict] = []
    precisam = [p for p in plano if p["precisa_scraping"]]

    if not precisam:
        for p in plano:
            resultados.append(_resultado_pre(p))
    else:
        async with alura_session() as page:
            i_scrape = 0
            for p in plano:
                if not p["precisa_scraping"]:
                    resultados.append(_resultado_pre(p))
                    continue
                try:
                    dados = await _sincronizar_curso_com_page(
                        p["course_id"], page, p["api_data"], p["existing"], carreiras_cache,
                    )
                    resultados.append({
                        "course_id": p["course_id"],
                        "slug": dados.get("slug"),
                        "status": "ok",
                    })
                except Exception as e:
                    resultados.append({
                        "course_id": p["course_id"],
                        "slug": p["slug"],
                        "status": "erro",
                        "erro": str(e),
                    })
                i_scrape += 1
                if i_scrape < len(precisam) and delay_segundos > 0:
                    await asyncio.sleep(delay_segundos)

    return {
        "total": len(course_ids),
        "ok": sum(1 for r in resultados if r["status"] == "ok"),
        "unchanged": sum(1 for r in resultados if r["status"] == "unchanged"),
        "erros": sum(1 for r in resultados if r["status"] == "erro"),
        "detalhes": resultados,
    }
