"""
Operações de leitura e escrita no banco para o projeto alura_utils.
"""

from datetime import datetime

from core.database import get_pool


async def get_alura_updated_at(task_id: int) -> datetime | None:
    """Retorna a data de atualização registrada no banco para uma task, ou None se não existe."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT alura_updated_at FROM alura_transcricoes WHERE task_id = $1",
            task_id,
        )
        return row["alura_updated_at"] if row else None


async def upsert_transcricao(
    task_id: int,
    course_id: int,
    section_id: int,
    section_titulo: str,
    task_titulo: str,
    transcricao: str,
    alura_updated_at: datetime,
) -> None:
    """Insere ou atualiza a transcrição de um vídeo no banco."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO alura_transcricoes
                (task_id, course_id, section_id, section_titulo, task_titulo,
                 transcricao, alura_updated_at, extracted_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            ON CONFLICT (task_id) DO UPDATE SET
                transcricao      = EXCLUDED.transcricao,
                alura_updated_at = EXCLUDED.alura_updated_at,
                extracted_at     = NOW()
            """,
            task_id, course_id, section_id, section_titulo, task_titulo,
            transcricao, alura_updated_at,
        )


async def get_course(course_id: int) -> dict:
    """Retorna todas as transcrições de um curso agrupadas por section."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT section_id, section_titulo, task_id, task_titulo, transcricao
            FROM alura_transcricoes
            WHERE course_id = $1
            ORDER BY section_id, task_id
            """,
            course_id,
        )

    sections: dict[int, dict] = {}
    for row in rows:
        sid = row["section_id"]
        if sid not in sections:
            sections[sid] = {
                "section_id": sid,
                "titulo": row["section_titulo"],
                "videos": [],
            }
        sections[sid]["videos"].append({
            "task_id": row["task_id"],
            "titulo": row["task_titulo"],
            "transcricao": row["transcricao"],
        })

    return {"course_id": course_id, "sections": list(sections.values())}
