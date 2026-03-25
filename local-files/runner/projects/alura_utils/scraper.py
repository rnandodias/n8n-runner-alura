"""
Scraper Playwright para o Admin da Alura.
Navega pelas páginas SSR para extrair dados de todos os tipos de tarefa.

Credenciais via variáveis de ambiente:
  ALURA_EMAIL    — e-mail de login
  ALURA_PASSWORD — senha
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import Page, async_playwright

_BASE_URL = "https://cursos.alura.com.br"
_LOGIN_USER_FIELD = "username"


async def _login(page: Page) -> None:
    email = os.environ.get("ALURA_EMAIL", "")
    password = os.environ.get("ALURA_PASSWORD", "")
    if not email or not password:
        raise ValueError("ALURA_EMAIL e ALURA_PASSWORD devem estar configurados no .env")

    await page.goto(f"{_BASE_URL}/loginForm", wait_until="domcontentloaded")
    await page.fill(f'input[name="{_LOGIN_USER_FIELD}"]', email)
    await page.fill('input[name="password"]', password)
    await page.press('input[name="password"]', "Enter")
    await page.wait_for_load_state("domcontentloaded")

    if "login" in page.url:
        raise PermissionError("Login falhou. Verifique ALURA_EMAIL e ALURA_PASSWORD.")


@asynccontextmanager
async def alura_session():
    """Context manager que abre browser, faz login e cede a page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await _login(page)
            yield page
        finally:
            await browser.close()


async def get_course_slug(page: Page, course_id: int) -> str:
    """Extrai o slug do curso da página admin."""
    await page.goto(f"{_BASE_URL}/admin/courses/v2/{course_id}", wait_until="domcontentloaded")
    soup = BeautifulSoup(await page.content(), "lxml")
    el = soup.select_one("input[name='code']")
    slug = el["value"] if el and el.get("value") else ""
    if not slug:
        raise ValueError(f"Não foi possível obter o slug do curso {course_id}")
    return slug


async def get_sections(page: Page, course_id: int) -> list[dict]:
    """
    Retorna sections ativas: [{section_id, titulo}] em ordem de exibição.
    """
    await page.goto(f"{_BASE_URL}/admin/courses/v2/{course_id}/sections", wait_until="domcontentloaded")
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


async def get_tasks(page: Page, course_id: int, section_id: int) -> list[dict]:
    """
    Retorna todas as tasks ativas de uma seção: [{task_id, titulo, alura_updated_at}].
    Inclui todos os tipos (VIDEO, HQ_EXPLANATION, SINGLE_CHOICE, TEXT_CONTENT, etc.).
    """
    await page.goto(f"{_BASE_URL}/admin/course/v2/{course_id}/section/{section_id}/tasks", wait_until="domcontentloaded")
    soup = BeautifulSoup(await page.content(), "lxml")

    tasks = []
    for row in soup.select("table#tasks-table tr"):
        hidden = row.select_one("input[name='sectionIds']")
        tds = row.select("td")
        if not hidden or len(tds) < 5:
            continue
        task_id = hidden.get("value")
        updated_at_str = tds[3].text.strip()
        status = tds[4].text.strip()
        if status == "Ativo":
            alura_updated_at = datetime.strptime(updated_at_str, "%d/%m/%Y %H:%M:%S")
            tasks.append({
                "task_id": int(task_id),
                "alura_updated_at": alura_updated_at,
            })
    return tasks


async def get_task_details(page: Page, course_id: int, section_id: int, task_id: int) -> dict:
    """
    Acessa a página de edição da tarefa e extrai todos os campos.
    Retorna um dict com os dados comuns e os específicos do tipo (kind).
    """
    await page.goto(
        f"{_BASE_URL}/admin/course/v2/{course_id}/section/{section_id}/task/edit/{task_id}",
        wait_until="domcontentloaded",
    )
    soup = BeautifulSoup(await page.content(), "lxml")

    def _val(selector: str) -> str:
        el = soup.select_one(selector)
        return el["value"] if el and el.get("value") else ""

    kind = _val("input[name='kind']")
    title = _val("input[name='title']")
    position = int(_val("input[name='position']") or 0)
    status_opt = soup.select_one("select[name='status'] option[selected]")
    status = status_opt["value"] if status_opt else "ACTIVE"
    author_opt = soup.select_one("select[name='authorId'] option[selected]")
    author_id = int(author_opt["value"]) if author_opt and author_opt.get("value") else None
    tag_val = _val("input[name='tagId']")
    tag_id = int(tag_val) if tag_val else None

    text_ta = soup.select_one("textarea[name='text']")
    text = text_ta.get_text(strip=True) if text_ta else ""

    result: dict = {
        "kind": kind,
        "title": title,
        "position": position,
        "status": status,
        "author_id": author_id,
        "tag_id": tag_id,
        "text": text,
        "video_uri": None,
        "video_duration": None,
        "video_size_sd": None,
        "video_size_hd": None,
        "video_size_full_hd": None,
        "opinion": None,
        "alternatives": [],
    }

    if kind == "VIDEO":
        result["video_uri"] = _val("input[name='uri']")
        dur = _val("input[name='duration']")
        result["video_duration"] = int(dur) if dur else None
        for field, name in [
            ("video_size_sd", "sizeSD"),
            ("video_size_hd", "sizeHD"),
            ("video_size_full_hd", "sizeFullHD"),
        ]:
            v = _val(f"input[name='{name}']")
            result[field] = int(v) if v else None

    elif kind == "TEXT_CONTENT":
        op_ta = soup.select_one("textarea[name='opinion']")
        result["opinion"] = op_ta.get_text(strip=True) if op_ta else None

    elif kind in ("SINGLE_CHOICE", "MULTIPLE_CHOICE"):
        alternatives = []
        for i, alt_div in enumerate(soup.select("div.fieldGroup-alternative")):
            alt_id_input = alt_div.select_one("input[name$='.id']")
            alt_id = int(alt_id_input["value"]) if alt_id_input and alt_id_input.get("value") else None
            text_ta_alt = alt_div.select_one("textarea[name$='.text']")
            alt_text = text_ta_alt.get_text(strip=True) if text_ta_alt else ""
            if not alt_id and not alt_text:
                continue
            op_ta_alt = alt_div.select_one("textarea[name$='.opinion']")
            alt_opinion = op_ta_alt.get_text(strip=True) if op_ta_alt else ""
            correct_radio = alt_div.select_one("input.fieldGroup-alternative-actions-correct")
            is_correct = correct_radio.get("checked") is not None if correct_radio else False
            alternatives.append({
                "alt_id": alt_id,
                "position": i,
                "text": alt_text,
                "opinion": alt_opinion,
                "correct": is_correct,
            })
        result["alternatives"] = alternatives

    return result
