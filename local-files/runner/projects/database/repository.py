"""Operações de leitura no banco para diagnóstico do projeto database."""

import json

from core.database import get_pool


async def contar_cursos_total() -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM alura_cursos")


async def listar_cursos_sem_competencias() -> list[int]:
    """
    Retorna course_ids onde o campo `dados.competencias` está ausente, NULL ou array vazio.
    Os outros campos (competencias_otimizado, competencias_batch_*) são resultados
    de testes e NÃO entram no critério.
    """
    sql = """
        SELECT course_id FROM alura_cursos
        WHERE COALESCE(jsonb_array_length(dados->'competencias'), 0) = 0
        ORDER BY course_id
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [r["course_id"] for r in rows]


async def listar_cursos_sem_transcricoes() -> list[int]:
    """
    Retorna course_ids onde NENHUMA atividade kind=VIDEO em nenhuma aula
    tem campo `text` não-vazio.
    """
    sql = """
        SELECT course_id FROM alura_cursos
        WHERE NOT EXISTS (
            SELECT 1
            FROM jsonb_array_elements(COALESCE(dados->'aulas', '[]'::jsonb)) AS aula,
                 jsonb_array_elements(COALESCE(aula->'atividades', '[]'::jsonb)) AS ativ
            WHERE ativ->>'kind' = 'VIDEO'
              AND COALESCE(ativ->>'text', '') <> ''
        )
        ORDER BY course_id
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [r["course_id"] for r in rows]


async def listar_todos_cursos_com_dados() -> list[dict]:
    """
    Retorna todos os cursos do banco com o `dados` JSONB completo, mesclado com `course_id`.
    Usado pela exportação comercial XLSX. Pode pesar ~50-100MB em memória para 2000+ cursos.
    """
    sql = "SELECT course_id, dados FROM alura_cursos ORDER BY course_id"
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
        return [
            {"course_id": r["course_id"], **json.loads(r["dados"])}
            for r in rows
        ]
