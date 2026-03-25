"""
Cliente HTTP para as APIs públicas da Alura.
"""

import httpx

_ALURA_API = "https://cursos.alura.com.br/api"


async def get_course_api(slug: str) -> dict:
    """Retorna metadados do curso pela API pública."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{_ALURA_API}/curso-{slug}")
        r.raise_for_status()
        return r.json()


async def get_career_api(slug: str) -> dict:
    """Retorna dados da carreira pela API pública."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{_ALURA_API}/trilha-de-carreira-{slug}")
        r.raise_for_status()
        return r.json()
