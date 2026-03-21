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
        # Remove tabelas de versões anteriores, se existirem
        await conn.execute("""
            DROP TABLE IF EXISTS alura_alternativas;
            DROP TABLE IF EXISTS alura_tarefas;
            DROP TABLE IF EXISTS alura_secoes;
            DROP TABLE IF EXISTS alura_transcricoes;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alura_cursos (
                course_id  INTEGER PRIMARY KEY,
                synced_at  TIMESTAMPTZ DEFAULT NOW(),
                dados      JSONB NOT NULL
            );
        """)
