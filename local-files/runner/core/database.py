"""
Conexão compartilhada com PostgreSQL via asyncpg.
Inicializa o pool e cria o schema na primeira chamada.
"""

import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None

_CAREER_SLUGS = [
    ("engenharia-de-ia", "Engenharia de IA"),
    ("especialista-em-ia", "Especialista em IA"),
    ("cloud-security", "Cloud Security"),
    ("appsec", "AppSec: Desenvolvimento Seguro de Aplicações"),
    ("platform-engineering", "Platform Engineering"),
    ("site-reliability-engineering", "Site Reliability Engineering"),
    ("desenvolvimento-backend-php", "Desenvolvimento Back-End PHP"),
    ("desenvolvimento-backend-net", "Desenvolvimento Back-End .NET"),
    ("desenvolvimento-backend-python", "Desenvolvimento Back-End Python"),
    ("desenvolvimento-backend-nodejs", "Desenvolvimento Back-End Node.js"),
    ("desenvolvimento-backend-java", "Desenvolvimento Back-End Java"),
    ("desenvolvimento-mobile-com-flutter", "Desenvolvimento Mobile com Flutter"),
    ("desenvolvimento-frontend-react", "Desenvolvimento Front-End React"),
    ("analise-de-dados", "Análise de Dados"),
    ("ciencia-de-dados", "Ciência de Dados"),
    ("governanca-de-dados", "Governança de Dados"),
    ("engenharia-de-dados", "Engenharia de Dados"),
    ("ux-design", "UX Design"),
    ("ui-design", "UI Design"),
    ("social-media-marketing", "Social Media Marketing"),
    ("growth-marketing", "Growth Marketing"),
    ("recursos-humanos", "Recursos Humanos (RH)"),
    ("lideranca", "Liderança"),
]


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

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS alura_carreiras (
                slug       TEXT PRIMARY KEY,
                titulo     TEXT NOT NULL,
                dados      JSONB,
                synced_at  TIMESTAMPTZ
            );
        """)

        for slug, titulo in _CAREER_SLUGS:
            await conn.execute(
                """
                INSERT INTO alura_carreiras (slug, titulo)
                VALUES ($1, $2)
                ON CONFLICT (slug) DO NOTHING
                """,
                slug, titulo,
            )
