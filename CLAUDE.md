# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI sidecar service for n8n workflows focused on automated article review. It uses BeautifulSoup for article extraction, python-docx/OOXML for document manipulation, and Anthropic Claude / OpenAI GPT agents for review. Deployed as a Docker container alongside n8n on a VPS.

## Key Commands

### Local Development (local-tests/)

```bash
cd local-tests
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# Run full article review (all agents)
python revisar_artigo.py artigo.docx --todos

# Run specific agent
python revisar_artigo.py artigo.docx --seo --guia-seo guia.docx
python revisar_artigo.py artigo.docx --tecnico
python revisar_artigo.py artigo.docx --texto

# Generate JSON only (no document output)
python revisar_artigo.py artigo.docx --todos --json-only

# Use specific LLM provider
python revisar_artigo.py artigo.docx --todos --provider openai
```

### Docker (production runner)

```bash
cd n8n-runner

# Build and run
docker compose --env-file .env build runner
docker compose --env-file .env up -d runner
docker compose --env-file .env logs -f runner

# Debug: access container shell
docker exec -it $(docker ps --format '{{.Names}}' | grep runner | head -n1) bash

# Health check
curl http://localhost:8000/ping
```

### Test specific endpoint

```bash
# From inside n8n container
curl -X POST http://runner:8000/revisao/agente-seo-form \
  -F "file=@artigo.docx" \
  -F "palavras_chave=python, machine learning" \
  -F "provider=anthropic"
```

## Architecture

```
n8n (workflow orchestrator)
    |-- HTTP --> Runner FastAPI (:8000)
                    |-- BeautifulSoup/httpx   (article extraction for html-to-docx and image agent)
                    |-- python-docx / OOXML   (DOCX generation and Track Changes)
                    |-- LLM APIs              (Anthropic Claude / OpenAI GPT)
```

### File Layout

- **`local-files/runner/`** — Production application code (mounted into Docker at `/files/runner`)
  - `app.py` — FastAPI app with all endpoints
  - `llm_client.py` — Unified LLM client (Anthropic/OpenAI abstraction)
  - `prompts_revisao.py` — AI agent prompts (SEO, Tecnico, Texto, Imagem)
  - `track_changes.py` — Native OOXML Track Changes implementation
- **`n8n-runner/`** — Docker infrastructure
  - `docker-compose.yml` — Production compose (mounts `/local-files` volume)
  - `runner/Dockerfile` — Based on `mcr.microsoft.com/playwright/python:latest` + LibreOffice (kept as base image)
  - `runner/start.sh` — Starts uvicorn on port 8000
- **`local-tests/`** — Standalone test scripts (no Docker/FastAPI needed); mirrors the production modules for rapid iteration
- **`workflows/`** — Exported n8n workflow JSONs

### Critical Design Decisions

**Volume mount:** The Docker container mounts the host `/local-files` directory at `/files`. This means `local-files/runner/app.py` IS the production code — editing it locally changes what runs in Docker after restart (no rebuild needed for Python file changes).

**LLM abstraction:** `llm_client.py` exposes `criar_cliente_llm(provider, model)` which returns an `LLMClient` subclass (`AnthropicClient` or `OpenAIClient`). All agent calls go through this interface. Provider selection defaults to `LLM_PROVIDER` env var (default: `anthropic`).

**Prompt caching:** For Anthropic, the article content is passed as `artigo_context` which gets `cache_control: ephemeral` to reduce costs on repeated agent calls for the same article. OpenAI uses prefix caching automatically.

**Track Changes:** Implemented natively via direct `document.xml` OOXML manipulation. The `track_changes.py` module handles insertions, deletions, and comment annotations without any LibreOffice dependency.

**SVG images:** SVGs are rasterized to PNG via `cairosvg` before sending to LLM APIs (which don't support SVG natively).

**`generate_docx` is internal:** The function `generate_docx` is NOT an exposed HTTP endpoint — it's an internal async function called by `/html-to-docx`. Do not add `@app.post` decorator to it.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /ping` | Health check |
| `POST /html-to-docx` | Fetch article URL → DOCX binary (pipeline entry point) |
| `POST /revisao/extrair-texto` | Extract structured text from DOCX |
| `POST /revisao/aplicar` | Apply revisions with OOXML Track Changes |
| `POST /revisao/aplicar-json` | Apply revisions via form (URL + JSON string) |
| `POST /revisao/aplicar-form` | Apply revisions via file upload |
| `POST /revisao/aplicar-comentarios-form` | Apply revisions as Word comments (main n8n output) |
| `POST /revisao/agente-seo[-form]` | SEO review agent |
| `POST /revisao/agente-tecnico[-form]` | Technical review agent (uses web search) |
| `POST /revisao/agente-texto[-form]` | Text/didactic review agent |
| `POST /revisao/agente-imagem[-form]` | Image review agent (multimodal vision) |

## Environment Variables

Required in `n8n-runner/.env` (VPS) or `local-tests/.env` (local):

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LLM_PROVIDER=anthropic          # or openai
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
OPENAI_MODEL=gpt-4.1
```

## Review Agent Output Format

All four agents (SEO, Tecnico, Texto, Imagem) return a JSON array:

```json
[
  {
    "tipo": "SEO|TECNICO|TEXTO|IMAGEM",
    "acao": "substituir|deletar|inserir|comentario",
    "texto_original": "exact text found in document",
    "texto_novo": "replacement text",
    "justificativa": "reason for change"
  }
]
```

The `aplicar_revisoes_docx` / `aplicar_comentarios_docx` functions in `track_changes.py` consume this format and write OOXML Track Changes or Word comments into the DOCX file.

## n8n Workflow

The n8n workflow (`workflows/*.json`) runs agents in parallel:

```
Trigger -> Config -> HTML to DOCX -> [SEO | Tecnico | Texto] (parallel) -> Merge -> Apply Comments -> Output
```

Import via: n8n Settings -> Import Workflow -> paste JSON content.
