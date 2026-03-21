"""
Scraper Playwright para o Admin da Alura.
Faz login e navega pelas páginas SSR para extrair dados.

Credenciais via variáveis de ambiente:
  ALURA_EMAIL    — e-mail de login
  ALURA_PASSWORD — senha

Nota: o formulário de login usa os campos 'username' e 'password'
(padrão Spring Security). Ajuste _LOGIN_USER_FIELD se necessário.
"""

import os

from bs4 import BeautifulSoup
from playwright.async_api import Page, async_playwright

_BASE_URL = "https://cursos.alura.com.br"
_LOGIN_USER_FIELD = "username"  # ajuste se o campo tiver outro name


async def _login(page: Page) -> None:
    email = os.environ.get("ALURA_EMAIL", "")
    password = os.environ.get("ALURA_PASSWORD", "")
    if not email or not password:
        raise ValueError("ALURA_EMAIL e ALURA_PASSWORD devem estar configurados no .env")

    await page.goto(f"{_BASE_URL}/loginForm")
    await page.wait_for_load_state("networkidle")
    await page.fill(f'input[name="{_LOGIN_USER_FIELD}"]', email)
    await page.fill('input[name="password"]', password)
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")

    if "loginForm" in page.url or "/login" in page.url:
        raise PermissionError("Login falhou. Verifique ALURA_EMAIL e ALURA_PASSWORD.")


async def _get_sections(page: Page, course_id: int) -> list[dict]:
    """Retorna sections ativas do curso: [{section_id, titulo}]"""
    await page.goto(f"{_BASE_URL}/admin/courses/v2/{course_id}/sections")
    await page.wait_for_load_state("networkidle")
    soup = BeautifulSoup(await page.content(), "lxml")

    sections = []
    for row in soup.select("table#sectionIds tbody tr"):
        section_id = row.get("id")
        tds = row.select("td")
        if not section_id or len(tds) < 4:
            continue
        titulo = tds[2].text.strip()
        status = tds[3].text.strip()
        if status == "Ativo":
            sections.append({"section_id": int(section_id), "titulo": titulo})
    return sections


async def _get_video_tasks(page: Page, course_id: int, section_id: int) -> list[dict]:
    """Retorna tasks de vídeo ativas de uma section: [{task_id, titulo}]"""
    await page.goto(f"{_BASE_URL}/admin/course/v2/{course_id}/section/{section_id}/tasks")
    await page.wait_for_load_state("networkidle")
    soup = BeautifulSoup(await page.content(), "lxml")

    tasks = []
    for row in soup.select("table#tasks-table tr"):
        hidden = row.select_one("input[name='sectionIds']")
        tds = row.select("td")
        if not hidden or len(tds) < 5:
            continue
        task_id = hidden.get("value")
        tipo = tds[1].text.strip()
        titulo = tds[2].text.strip()
        status = tds[4].text.strip()
        if tipo == "Vídeo" and status == "Ativo":
            tasks.append({"task_id": int(task_id), "titulo": titulo})
    return tasks


async def _get_transcricao(page: Page, course_id: int, section_id: int, task_id: int) -> str:
    """Extrai o markdown da transcrição de um vídeo."""
    await page.goto(
        f"{_BASE_URL}/admin/course/v2/{course_id}/section/{section_id}/task/edit/{task_id}"
    )
    await page.wait_for_load_state("networkidle")
    soup = BeautifulSoup(await page.content(), "lxml")
    textarea = soup.select_one("textarea[name='text']")
    return textarea.text.strip() if textarea else ""


async def extrair_transcricoes_curso(course_id: int) -> dict:
    """
    Ponto de entrada principal.
    Faz login, percorre todas as sections e vídeos do curso
    e retorna as transcrições em formato estruturado.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await _login(page)
            sections = await _get_sections(page, course_id)

            result_sections = []
            for section in sections:
                video_tasks = await _get_video_tasks(page, course_id, section["section_id"])
                if not video_tasks:
                    continue

                videos = []
                for task in video_tasks:
                    transcricao = await _get_transcricao(
                        page, course_id, section["section_id"], task["task_id"]
                    )
                    videos.append({
                        "task_id": task["task_id"],
                        "titulo": task["titulo"],
                        "transcricao": transcricao,
                    })

                result_sections.append({
                    "section_id": section["section_id"],
                    "titulo": section["titulo"],
                    "videos": videos,
                })

            return {"course_id": course_id, "sections": result_sections}
        finally:
            await browser.close()
