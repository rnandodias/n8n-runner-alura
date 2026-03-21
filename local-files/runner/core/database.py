"""
Conexão compartilhada com PostgreSQL via asyncpg.
Inicializa o pool e cria o schema na primeira chamada.
"""

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
        await _init_schema(_pool)
    return _pool


async def _init_schema(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alura_transcricoes (
                task_id          INTEGER PRIMARY KEY,
                course_id        INTEGER NOT NULL,
                section_id       INTEGER NOT NULL,
                section_titulo   TEXT,
                task_titulo      TEXT,
                transcricao      TEXT,
                alura_updated_at TIMESTAMP,
                extracted_at     TIMESTAMP DEFAULT NOW()
            )
        """)
