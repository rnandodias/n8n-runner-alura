"""
Operações de leitura e escrita no banco para o projeto alura_utils.
"""

import json

from core.database import get_pool


async def get_course_dados(course_id: int) -> dict | None:
    """Retorna o documento JSON do curso armazenado, ou None se não existe."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT dados FROM alura_cursos WHERE course_id = $1",
            course_id,
        )
        return dict(row["dados"]) if row else None


async def upsert_course(course_id: int, dados: dict) -> None:
    """Salva (ou substitui) o documento JSON do curso."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO alura_cursos (course_id, synced_at, dados)
            VALUES ($1, NOW(), $2)
            ON CONFLICT (course_id) DO UPDATE SET
                synced_at = NOW(),
                dados     = EXCLUDED.dados
            """,
            course_id, json.dumps(dados, default=str),
        )
