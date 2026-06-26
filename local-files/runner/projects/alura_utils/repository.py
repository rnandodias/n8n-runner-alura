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
        return json.loads(row["dados"]) if row else None


async def get_course_dados_by_slug(slug: str) -> tuple[int, dict] | None:
    """Retorna (course_id, dados) do curso buscando pelo slug, ou None se não existe."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT course_id, dados FROM alura_cursos WHERE dados->>'slug' = $1",
            slug,
        )
        if not row:
            return None
        return row["course_id"], json.loads(row["dados"])


async def delete_course(course_id: int) -> bool:
    """Remove o curso do banco. Retorna True se algo foi deletado, False se não existia."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval(
            "DELETE FROM alura_cursos WHERE course_id = $1 RETURNING course_id",
            course_id,
        )
        return deleted is not None


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


async def get_all_carreiras() -> list[dict]:
    """Retorna todas as carreiras cadastradas com seus dados em cache."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT slug, titulo, dados, synced_at FROM alura_carreiras ORDER BY slug"
        )
        return [
            {
                "slug": r["slug"],
                "titulo": r["titulo"],
                "dados": json.loads(r["dados"]) if r["dados"] else None,
                "synced_at": r["synced_at"].isoformat() if r["synced_at"] else None,
            }
            for r in rows
        ]


async def upsert_carreira(slug: str, titulo: str, dados: dict) -> None:
    """Salva (ou atualiza) os dados de uma carreira."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO alura_carreiras (slug, titulo, dados, synced_at)
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                titulo    = EXCLUDED.titulo,
                dados     = EXCLUDED.dados,
                synced_at = NOW()
            """,
            slug, titulo, json.dumps(dados, default=str),
        )


async def insert_carreira_slug(slug: str, titulo: str) -> None:
    """Adiciona novo slug de carreira para rastreamento."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO alura_carreiras (slug, titulo)
            VALUES ($1, $2)
            ON CONFLICT (slug) DO UPDATE SET titulo = EXCLUDED.titulo
            """,
            slug, titulo,
        )


async def update_course_competencias(course_id: int, competencias: list[dict]) -> None:
    """Salva (ou substitui) a lista de competências no JSON do curso."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE alura_cursos
            SET dados = jsonb_set(dados, '{competencias}', $1::jsonb)
            WHERE course_id = $2
            """,
            json.dumps(competencias, ensure_ascii=False), course_id,
        )


async def update_course_carreiras(course_slug: str, carreiras: list[dict]) -> None:
    """Atualiza o campo carreiras no JSON do curso identificado pelo slug."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE alura_cursos
            SET dados = jsonb_set(dados, '{carreiras}', $1::jsonb)
            WHERE dados->>'slug' = $2
            """,
            json.dumps(carreiras, default=str), course_slug,
        )
