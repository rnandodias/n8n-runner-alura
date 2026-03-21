"""
Controle de concorrência para o scraper da Alura.
A Alura permite apenas uma sessão ativa por usuário,
portanto limitamos a 1 scraping simultâneo globalmente.
"""

import asyncio

scraping_semaphore = asyncio.Semaphore(1)
