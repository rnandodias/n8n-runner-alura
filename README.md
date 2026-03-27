# Runner Alura - Sidecar FastAPI para n8n

Serviço FastAPI usado como sidecar do n8n para automações envolvendo cursos e artigos da Alura.

## Visao Geral

Este projeto fornece um runner FastAPI que combina:
- **Scraping com Playwright** para sincronizar dados de cursos do Admin Alura
- **API pública da Alura** para metadados de cursos e carreiras
- **PostgreSQL** para persistência dos dados de cursos em JSONB
- **Agentes de IA** (Anthropic Claude e OpenAI GPT) para classificação de competências e revisão de artigos
- **BeautifulSoup/httpx** para extração de conteúdo de artigos e conversão para DOCX
- **python-docx / OOXML** para manipulação de documentos e aplicação de comentários

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                           n8n                                   │
│                    (orquestrador de workflows)                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP (runner:8000)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Runner FastAPI                             │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  Playwright  │  │   Agentes de IA  │  │  BeautifulSoup   │  │
│  │  (scraping)  │  │  Claude / GPT    │  │  python-docx     │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
│                           │                                     │
│                    ┌──────▼──────┐                              │
│                    │ PostgreSQL  │                              │
│                    │  (JSONB)    │                              │
│                    └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Endpoints

### Utilitários

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `GET /ping` | GET | Health check do serviço |

### Alura Utils — Cursos e Carreiras

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/cursos` | POST | Sincroniza curso (scraping Admin + API pública) |
| `GET /utils/cursos/{course_id}` | GET | Retorna dados do curso do banco sem scraping |
| `POST /utils/carreiras/sync` | POST | Atualiza cache de todas as carreiras |
| `POST /utils/carreiras` | POST | Adiciona novo slug de carreira |
| `GET /utils/carreiras` | GET | Lista carreiras cadastradas |

### Classificador de Competências

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/cursos/{course_id}/competencias` | POST | Classifica competências do curso via LLM e persiste no banco |
| `GET /utils/cursos/{course_id}/competencias` | GET | Retorna competências já classificadas |
| `POST /utils/cursos/{course_id}/competencias/otimizado` | POST | Classifica com Haiku→Opus (dois steps, custo reduzido) |
| `GET /utils/cursos/{course_id}/competencias/otimizado` | GET | Retorna competências classificadas pelo método otimizado |

### Batch — Anthropic (padrão)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/competencias/batch/anthropic/padrao/submit` | POST | Submete batch: transcrições brutas → Opus |
| `GET /utils/competencias/batch/anthropic/padrao/status/{batch_id}` | GET | Consulta status do batch |
| `POST /utils/competencias/batch/anthropic/padrao/salvar/{batch_id}` | POST | Lê resultados e persiste no banco |

### Batch — Anthropic (otimizado)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/competencias/batch/anthropic/otimizado/submit` | POST | Submete batch: Haiku sumariza → Opus classifica em batch |
| `GET /utils/competencias/batch/anthropic/otimizado/status/{batch_id}` | GET | Consulta status do batch |
| `POST /utils/competencias/batch/anthropic/otimizado/salvar/{batch_id}` | POST | Lê resultados e persiste no banco |

### Batch — OpenAI (padrão)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/competencias/batch/openai/padrao/submit` | POST | Submete batch: transcrições brutas → gpt-4.1 |
| `GET /utils/competencias/batch/openai/padrao/status/{batch_id}` | GET | Consulta status do batch |
| `POST /utils/competencias/batch/openai/padrao/salvar/{batch_id}` | POST | Lê resultados e persiste no banco |
| `POST /utils/competencias/batch/openai/webhook` | POST | Recebe notificação de batch concluído (ambas variantes OpenAI) |

### Batch — OpenAI (otimizado)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /utils/competencias/batch/openai/otimizado/submit` | POST | Submete batch: gpt-4.1-mini sumariza → gpt-4.1 classifica em batch |
| `GET /utils/competencias/batch/openai/otimizado/status/{batch_id}` | GET | Consulta status do batch |
| `POST /utils/competencias/batch/openai/otimizado/salvar/{batch_id}` | POST | Lê resultados e persiste no banco |

### Conversao de Artigos

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /revisao/artigos/html-to-docx` | POST | Converte URL de artigo para DOCX binario |

### Revisao com Agentes de IA

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `POST /revisao/artigos/extrair-texto` | POST | Extrai texto de DOCX para revisao |
| `POST /revisao/artigos/aplicar` | POST | Aplica revisoes com Track Changes (OOXML) |
| `POST /revisao/artigos/aplicar-json` | POST | Aplica revisoes JSON via form |
| `POST /revisao/artigos/aplicar-form` | POST | Aplica revisoes via multipart form |
| `POST /revisao/artigos/aplicar-comentarios-form` | POST | Aplica revisoes como comentarios DOCX |
| `POST /revisao/artigos/agente-seo` | POST | Agente de revisao SEO/GEO |
| `POST /revisao/artigos/agente-tecnico` | POST | Agente de revisao tecnica |
| `POST /revisao/artigos/agente-texto` | POST | Agente de revisao textual/didatica |
| `POST /revisao/artigos/agente-seo-form` | POST | Agente SEO via multipart form |
| `POST /revisao/artigos/agente-tecnico-form` | POST | Agente tecnico via multipart form |
| `POST /revisao/artigos/agente-texto-form` | POST | Agente texto via multipart form |
| `POST /revisao/artigos/agente-imagem` | POST | Agente de revisao de imagens (visao multimodal) |
| `POST /revisao/artigos/agente-imagem-form` | POST | Agente imagem via multipart form |

---

## Classificador de Competências

Endpoint que analisa as transcrições dos vídeos de um curso e identifica entre 4 e 6 competências
da biblioteca de competências da plataforma.

### Entrada

Todos os parâmetros são passados como **query string**:

```bash
# Classificar com defaults (anthropic + claude-sonnet-4-5-20250929)
POST /utils/cursos/{course_id}/competencias

# Forçar reclassificação (ignora cache)
POST /utils/cursos/{course_id}/competencias?force=true

# Escolher provider e modelo
POST /utils/cursos/{course_id}/competencias?provider=anthropic&model=claude-opus-4-6
POST /utils/cursos/{course_id}/competencias?provider=openai&model=gpt-4.1

# Forçar reclassificação com modelo específico
POST /utils/cursos/{course_id}/competencias?force=true&provider=anthropic&model=claude-opus-4-6

# Consultar resultado salvo (sem chamar LLM)
GET /utils/cursos/{course_id}/competencias
```

Parâmetros opcionais:

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `provider` | string | `"anthropic"` | Provider do LLM: `"anthropic"` ou `"openai"` |
| `model` | string | padrão do provider | ID do modelo. Ver tabela [Provedores e Modelos](#provedores-e-modelos) |
| `force` | bool | `false` | Se `true`, reclassifica mesmo que já exista resultado salvo |

### Saída

```json
{
  "course_id": 12345,
  "total": 5,
  "competencias": [
    {
      "id": "CP0042",
      "nome": "Nome da competência",
      "descricao": "Descrição da competência",
      "habilidades": [
        { "id": "HB00201", "nome": "nome da habilidade" },
        { "id": "HB00202", "nome": "nome da habilidade" }
      ]
    }
  ]
}
```

As competências são persistidas dentro do JSONB do curso (`dados.competencias`).
Cursos não classificados não possuem a chave — o GET retorna 404 nesses casos.

### Chave de API por projeto

Para controle de custos, o classificador suporta chave de API dedicada:

```env
CLASSIFICADOR_COMPETENCIAS_ANTHROPIC_API_KEY=sk-ant-...   # opcional
CLASSIFICADOR_COMPETENCIAS_OPENAI_API_KEY=sk-...          # opcional
```

Se não configuradas, usa as chaves globais (`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`).
O mesmo padrão `{PROJETO}_ANTHROPIC_API_KEY` funciona para qualquer projeto.

### Biblioteca de Competências

Localizada em `local-files/runner/projects/classificador_competencias/biblioteca_competencias.json`.
Contém 112 competências (~669 habilidades), carregada em memória na inicialização do serviço.

---

## Classificação em Batch

Para classificar muitos cursos de uma vez, o runner suporta as **Batch APIs** da Anthropic e da OpenAI, que oferecem **50% de desconto** em troca de latência de até 24 h.

### Variantes disponíveis

| Variante | Provider | Step 1 | Step 2 (batch) | Campo no banco |
| --- | --- | --- | --- | --- |
| `anthropic/padrao` | Anthropic | — | Opus (transcrições brutas) | `competencias_batch_anthropic_padrao` |
| `anthropic/otimizado` | Anthropic | Haiku sumariza (síncrono) | Opus classifica resumos | `competencias_batch_anthropic_otimizado` |
| `openai/padrao` | OpenAI | — | gpt-4.1 (transcrições brutas) | `competencias_batch_openai_padrao` |
| `openai/otimizado` | OpenAI | gpt-4.1-mini sumariza (síncrono) | gpt-4.1 classifica resumos | `competencias_batch_openai_otimizado` |

> Todas as variantes são **independentes** — os resultados ficam em campos separados, permitindo comparação direta. Para remover uma variante, apague o arquivo de service correspondente e remova o import do `router.py`.

### Parâmetros do submit

Corpo JSON para todos os endpoints `submit`:

```json
{
  "course_ids": [123, 456, 789],
  "force": false
}
```

Variantes padrão aceitam também `"model"`. Variantes otimizado aceitam `"modelo_sumarizacao"` e `"modelo_classificacao"`.

| Campo | Tipo | Padrão | Descrição |
|---|---|---|---|
| `course_ids` | `list[int]` | — | IDs dos cursos a processar |
| `force` | `bool` | `false` | Se `true`, reclassifica mesmo que já exista resultado salvo |
| `model` | `string` | modelo padrão da variante | (só variantes padrão) Modelo para classificação |
| `modelo_sumarizacao` | `string` | Haiku / gpt-4.1-mini | (só variantes otimizado) Modelo do step 1 |
| `modelo_classificacao` | `string` | Opus / gpt-4.1 | (só variantes otimizado) Modelo do step 2 (batch) |

Cursos sem transcrições ou não encontrados no banco são automaticamente ignorados (`skipped`).

### Saída do submit

```json
{
  "batch_id": "msgbatch_abc123",
  "submitted": [123, 456],
  "skipped": [789],
  "processing_status": "in_progress"
}
```

---

## Como usar — Anthropic Batch

A Anthropic Batch API **não tem webhook**. O fluxo é sempre: **submit → polling de status → salvar**. Escolha a variante que faz mais sentido para o seu caso.

### Variante padrão (`anthropic/padrao`)

Envia as transcrições brutas direto para o Opus. Mais simples, maior custo por token.

```bash
# 1. Submeter o batch
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/padrao/submit \
  -H "Content-Type: application/json" \
  -d '{"course_ids": [123, 456, 789]}'

# Resposta:
# {"batch_id": "msgbatch_abc123", "submitted": [123, 456, 789], "skipped": [], "processing_status": "in_progress"}

# 2. Verificar status (repita até processing_status == "ended")
curl http://runner:8000/utils/competencias/batch/anthropic/padrao/status/msgbatch_abc123

# 3. Salvar resultados no banco
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/padrao/salvar/msgbatch_abc123

# Resposta:
# {"saved": [123, 456, 789], "errors": [], "total": 3}
```

### Variante otimizada (`anthropic/otimizado`)

Haiku sumariza cada curso síncronamente no submit, depois Opus classifica os resumos em batch. Custo ~52% menor.

```bash
# 1. Submeter o batch (Haiku sumariza cada curso durante o submit — pode demorar alguns minutos)
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/otimizado/submit \
  -H "Content-Type: application/json" \
  -d '{"course_ids": [123, 456, 789]}'

# 2. Verificar status
curl http://runner:8000/utils/competencias/batch/anthropic/otimizado/status/msgbatch_abc123

# 3. Salvar resultados no banco
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/otimizado/salvar/msgbatch_abc123
```

**Forçar reclassificação** de cursos já processados:

```bash
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/padrao/submit \
  -H "Content-Type: application/json" \
  -d '{"course_ids": [123, 456], "force": true}'
```

**Usar modelo diferente:**

```bash
curl -X POST http://runner:8000/utils/competencias/batch/anthropic/padrao/submit \
  -H "Content-Type: application/json" \
  -d '{"course_ids": [123, 456], "model": "claude-sonnet-4-6"}'
```

---

### Automatizando com n8n — Anthropic (dois workflows)

Como a Anthropic não tem webhook, use **dois workflows separados**: um para submeter e outro para fazer polling.

#### Workflow 1 — Submit (disparo manual ou agendado)

```
[Manual Trigger]
      │
      ▼
[HTTP Request — POST /submit]
  Method: POST
  URL: http://runner:8000/utils/competencias/batch/anthropic/otimizado/submit
  Body (JSON):
    {"course_ids": [123, 456, 789]}
      │
      ▼
[Set — salva batch_id como variável]
  Variável: batch_id
  Valor: {{ $json.batch_id }}
      │
      ▼
[Ativar Workflow 2 — Polling]
  (via n8n API ou Execute Workflow)
```

**Passo a passo:**

1. Crie um workflow **"Batch Submit"**
2. Adicione **Manual Trigger** (ou Schedule se quiser rodar periodicamente)
3. Adicione **HTTP Request**:
   - Method: `POST`
   - URL: `http://runner:8000/utils/competencias/batch/anthropic/otimizado/submit`
   - Body Content Type: `JSON`
   - Body: `{"course_ids": [123, 456, 789]}`
4. Adicione **Set** para capturar o `batch_id`:
   - Name: `batch_id` / Value: `{{ $json.batch_id }}`
5. Adicione **Execute Workflow** apontando para o Workflow 2 (polling), passando o `batch_id`

---

#### Workflow 2 — Polling (verifica e salva quando pronto)

```
[Schedule Trigger — a cada 5 min]
        │
        ▼
[HTTP Request — GET /status/{batch_id}]
        │
        ▼
[IF — processing_status == "ended"?]
   │                        │
  Sim                      Não
   │                        │
   ▼                        ▼
[HTTP Request —         [Stop and Error
 POST /salvar/{batch_id}]   ou NoOp]
   │
   ▼
[Desativar este workflow]
```

**Passo a passo:**

1. Crie um workflow **"Batch Polling"** com um parâmetro de entrada para o `batch_id`
2. Adicione **Schedule Trigger** com intervalo de 5 minutos
3. Adicione **HTTP Request** para status:
   - Method: `GET`
   - URL: `http://runner:8000/utils/competencias/batch/anthropic/otimizado/status/{{ $('Schedule Trigger').params.batch_id }}`
4. Adicione nó **IF**:
   - Condição: `{{ $json.processing_status }}` **equals** `ended`
5. Ramo **true** — adicione **HTTP Request** para salvar:
   - Method: `POST`
   - URL: `http://runner:8000/utils/competencias/batch/anthropic/otimizado/salvar/{{ $('Schedule Trigger').params.batch_id }}`
6. Após o salvar, adicione **n8n** node para desativar o próprio workflow (evita polling infinito):
   - Resource: `Workflow` / Operation: `Deactivate`
   - Workflow ID: `{{ $workflow.id }}`

> **Dica:** O `processing_status` pode ser `"in_progress"` ou `"ended"`. Só chame o `/salvar` quando for `"ended"` — antes disso o endpoint retornará erro.

---

### Automatizando com n8n — OpenAI (webhook)

A API OpenAI Batches **tem suporte a webhook**. O runner expõe um endpoint único em:

```
POST /utils/competencias/batch/openai/webhook
```

O endpoint roteia automaticamente para `padrao` ou `otimizado` com base no `metadata.variant` salvo no batch durante o submit.

**Configuração:**

1. Configure a URL do webhook no painel da OpenAI apontando para:

   ```text
   https://seu-runner.dominio.com.br/utils/competencias/batch/openai/webhook
   ```

2. Adicione a variável de ambiente `OPENAI_WEBHOOK_SECRET` no `.env` com o segredo gerado pela OpenAI
3. O runner verificará a assinatura `OpenAI-Signature` automaticamente

**Passo a passo no n8n (submit + aguardar webhook):**

```
[Manual Trigger ou Schedule]
        │
        ▼
[HTTP Request — POST submit]
  body: {"course_ids": [...], "force": false}
        │
        ▼
[Set — salva batch_id como variável]
        │
        ▼
[Webhook n8n — aguarda evento do runner]
        │
        ▼
[Notificação ou próximo passo do pipeline]
```

> **Nota:** O runner chama `salvar()` automaticamente ao receber o webhook da OpenAI. Não é necessário chamar o endpoint `/salvar` manualmente.

---

## Provedores e Modelos

Todos os endpoints que aceitam `provider` e `model` suportam as opções abaixo.

### Anthropic

| Model ID | Contexto | Tier | Recomendado para |
|---|---|---|---|
| `claude-sonnet-4-6` | 1M tokens | Balanceado (**padrão**) | Uso geral, classificação, revisão |
| `claude-opus-4-6` | 1M tokens | Mais capaz | Tarefas muito complexas |
| `claude-haiku-4-5-20251001` | 200k tokens | Mais rápido/barato | Alto volume — risco de estouro em cursos longos |
| `claude-sonnet-4-5-20250929` | 200k tokens | Legacy | Ainda disponível |

### OpenAI

| Model ID | Contexto | Input/MTok | Recomendado para |
|---|---|---|---|
| `gpt-4.1` | **1M tokens** | $2.00 | Classificação, revisão — **melhor contexto pelo preço** (**padrão**) |
| `gpt-4.1-mini` | **1M tokens** | — | Contexto grande com custo reduzido |
| `gpt-5.4` | **1M tokens** | $2.50 | Tarefas muito complexas com contexto grande |
| `gpt-5` | 400k tokens | $1.25 | Input mais barato, mas janela menor |
| `gpt-5.1` | 400k tokens | — | Reasoning configurável, janela menor |
| `gpt-5.2` | 400k tokens | $1.75 | Reasoning e código, janela menor |
| `gpt-5-mini` | — | $0.25 | Alto volume, tarefas simples |
| `gpt-4.1-nano` | — | $0.10 | Muito barato, tarefas simples |
| `gpt-5-nano` | — | $0.05 | Opção mais barata disponível |
| `o3` | 200k tokens | — | Raciocínio complexo |
| `o4-mini` | 200k tokens | — | Raciocínio leve, ciência e código |

> **Nota:** `gpt-4.1` e `gpt-4.1-mini` foram removidos da interface ChatGPT mas continuam **totalmente ativos na API**. Para tarefas com transcrições longas de cursos, prefira modelos com janela de 1M tokens. Fonte: `platform.openai.com/docs/models` e `openai.com/api/pricing`.

---

## Agentes de Revisao de Artigos

O sistema inclui quatro agentes especializados de IA para revisão de artigos:

### Agente SEO
- Analisa intencao de busca e resposta do conteudo
- Avalia distribuicao de palavras-chave (densidade 5-8%)
- Verifica estrutura de titulos e escaneabilidade
- Sugere links internos/externos
- Recomenda CTAs estrategicos

### Agente Tecnico
- Valida correcao e atualizacao de informacoes
- Verifica versoes de bibliotecas/frameworks (com busca web)
- Avalia exemplos de codigo e boas praticas
- Identifica recursos deprecados ou problemas de seguranca
- Sugere referencias e evidencias

### Agente Texto
- Melhora clareza, didatica e fluidez
- Corrige gramatica e ortografia (PT-BR)
- Avalia progressao logica e transicoes
- Sugere ajustes de tom e nivel do publico
- Recomenda listas, tabelas e elementos visuais

### Agente Imagem
- Analisa relevancia e contexto das imagens
- Verifica qualidade e legibilidade de screenshots
- Detecta interfaces desatualizadas (com busca web)
- Avalia alt text para acessibilidade
- Identifica textos presos em imagens que deveriam estar no artigo
- Sugere onde adicionar imagens faltantes
- Usa visao multimodal (Claude Vision ou GPT-4 Vision)
- Suporta rasterizacao de SVG via cairosvg

**Nota:** O agente de imagem requer `url_artigo` para extrair as imagens via scraping.
Com Anthropic, usa visao + busca web. Com OpenAI, usa apenas visao.

### Formato de Saida dos Agentes

```json
[
  {
    "tipo": "SEO|TECNICO|TEXTO|IMAGEM",
    "acao": "substituir|deletar|inserir|comentario",
    "texto_original": "texto exato encontrado no documento",
    "texto_novo": "texto substituto",
    "justificativa": "explicacao clara da mudanca"
  }
]
```

---

## Estrutura do Projeto

```
n8n-runner-alura/
├── .github/
│   └── workflows/
│       └── deploy-runner.yml             # CI/CD para VPS
├── local-files/
│   └── runner/
│       ├── app.py                        # Aplicação FastAPI principal (thin app)
│       ├── core/
│       │   ├── database.py               # Pool PostgreSQL + inicializacao de schema
│       │   ├── llm_client.py             # Cliente unificado LLM (Anthropic/OpenAI)
│       │   └── track_changes.py          # Implementacao OOXML Track Changes
│       └── projects/
│           ├── alura_utils/
│           │   ├── router.py             # Endpoints /utils/cursos e /utils/carreiras
│           │   ├── service.py            # Orquestracao de sync (scraping + API)
│           │   ├── repository.py         # Operacoes no banco (alura_cursos, alura_carreiras)
│           │   ├── scraper.py            # Playwright: login + scraping do Admin Alura
│           │   ├── api_client.py         # Cliente HTTP para API publica da Alura
│           │   └── queue.py              # Semaphore para controle de concorrencia do scraping
│           ├── classificador_competencias/
│           │   ├── router.py             # Endpoints /utils/cursos/{id}/competencias
│           │   ├── router_otimizado.py   # Endpoints /utils/cursos/{id}/competencias/otimizado
│           │   ├── service.py            # Extrai transcricoes + chama LLM + valida resposta
│           │   ├── service_otimizado.py  # Dois steps: Haiku sumariza → Opus classifica
│           │   ├── prompts.py            # Prompts do classificador padrão
│           │   ├── prompts_otimizado.py  # Prompts do classificador otimizado
│           │   ├── biblioteca_competencias.json  # 112 competencias, ~669 habilidades
│           │   └── batch/
│           │       ├── router.py         # 13 endpoints batch (todos os providers/variantes)
│           │       ├── anthropic/
│           │       │   ├── service_padrao.py     # Batch Anthropic: transcrições → Opus
│           │       │   └── service_otimizado.py  # Batch Anthropic: Haiku→Opus
│           │       └── openai/
│           │           ├── service_padrao.py     # Batch OpenAI: transcrições → gpt-4.1
│           │           └── service_otimizado.py  # Batch OpenAI: mini→gpt-4.1
│           └── revisao_artigos/
│               ├── router.py             # Endpoints /revisao/artigos/*
│               ├── prompts.py            # Prompts dos agentes de revisao
│               ├── scraping.py           # Extracao de conteudo HTML (BeautifulSoup)
│               └── docx_builder.py       # Geracao de DOCX a partir de artigos
├── manuais/
│   └── biblioteca_competencias_prompt_ready.json  # Fonte original da biblioteca
├── n8n-runner/
│   ├── docker-compose.yml                # Compose do runner
│   └── runner/
│       ├── Dockerfile                    # Imagem Docker (Playwright + LibreOffice)
│       ├── requirements.txt              # Dependencias Python
│       └── start.sh                      # Script de inicializacao (uvicorn)
├── local-tests/                          # Scripts de teste local (sem Docker)
├── workflows/                            # JSONs de workflows n8n exportados
├── ENV.EXAMPLE.txt                       # Template de variaveis de ambiente
└── README.md
```

---

## Configuracao

### Variaveis de Ambiente

Criar `/opt/n8n-runner/.env` na VPS:

```env
# Banco de dados
DATABASE_URL=postgresql://user:pass@host/db

# Credenciais do Admin Alura (para scraping)
ALURA_EMAIL=admin@alura.com
ALURA_PASSWORD=sua-senha

# APIs de LLM (chaves globais — fallback para todos os projetos)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Chaves por projeto (opcional — para controle de custos separado)
CLASSIFICADOR_COMPETENCIAS_ANTHROPIC_API_KEY=sk-ant-...
CLASSIFICADOR_COMPETENCIAS_OPENAI_API_KEY=sk-...
REVISAO_ARTIGOS_ANTHROPIC_API_KEY=sk-ant-...
REVISAO_ARTIGOS_OPENAI_API_KEY=sk-...

# Modelos padrao (opcional — se nao definido, usa o hardcoded no cliente)
ANTHROPIC_MODEL=claude-sonnet-4-5-20250929
OPENAI_MODEL=gpt-4.1

# Segredo para verificação de assinaturas do webhook OpenAI Batch
OPENAI_WEBHOOK_SECRET=whsec_...

# HTTPS via Traefik (opcional)
RUNNER_SUBDOMAIN=runner
DOMAIN_NAME=seu-dominio.com.br
TRAEFIK_NETWORK=root_default
```

---

## Deploy

### Pre-requisitos na VPS

1. Docker + Docker Compose instalados
2. Criar redes Docker:
   ```bash
   docker network create root_default 2>/dev/null || true
   docker network create svc_net 2>/dev/null || true
   ```

### Passo 1 — Criar o repositório no GitHub

1. Acesse **github.com/new**
2. Escolha um nome (ex: `n8n-runner-alura`)
3. Marque como **Private**
4. **Nao** inicialize com README, .gitignore ou licença
5. Clique em **Create repository**

---

### Passo 2 — Inicializar o Git local e conectar ao GitHub

```bash
cd /caminho/do/projeto

git init
git branch -M main

# Conecta ao GitHub (substitua pela URL do seu repo)
git remote add origin https://github.com/SEU_USUARIO/n8n-runner-alura.git
```

---

### Passo 3 — Primeiro commit e push

```bash
git add -A
git commit -m "Inicial: Runner Alura"
git push -u origin main
```

---

### Passo 4 — Gerar chave SSH para o GitHub Actions

Execute no **PowerShell** (nao na VPS):

```powershell
ssh-keygen -t ed25519 -C "gh-actions" -f "$env:USERPROFILE\.ssh\id_ed25519_gh_actions"
# Deixe a senha em branco (pressione Enter duas vezes)
```

Isso gera dois arquivos em `C:\Users\SEU_USUARIO\.ssh\`:
- `id_ed25519_gh_actions` — **chave privada** (vai para o GitHub Secrets)
- `id_ed25519_gh_actions.pub` — **chave publica** (vai para a VPS)

---

### Passo 5 — Autorizar a chave na VPS

Execute no **PowerShell**:

```powershell
# Copie a chave publica para a VPS
$pubKey = Get-Content "$env:USERPROFILE\.ssh\id_ed25519_gh_actions.pub"
ssh SEU_USUARIO@IP_DA_VPS "mkdir -p ~/.ssh && echo '$pubKey' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"

# Teste a conexao
ssh -i "$env:USERPROFILE\.ssh\id_ed25519_gh_actions" SEU_USUARIO@IP_DA_VPS "echo ok"
```

---

### Passo 6 — Configurar Secrets no GitHub

Acesse: `github.com/SEU_USER/NOME_DO_REPO` → **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|---|---|
| `SSH_PRIVATE_KEY` | Conteudo de `id_ed25519_gh_actions` (chave **privada**, incluindo as linhas `-----BEGIN...` e `-----END...`) |
| `VPS_HOST` | IP ou hostname da VPS |
| `VPS_PORT` | Porta SSH (normalmente `22`) |
| `VPS_USER` | Usuario SSH (ex: `root`) |
| `ANTHROPIC_API_KEY` | Sua chave da Anthropic |
| `OPENAI_API_KEY` | Sua chave da OpenAI |

Para ler e copiar a chave privada no PowerShell:

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519_gh_actions" | Set-Clipboard
# A chave ja esta na area de transferencia, cole direto no GitHub
```

---

### Passo 7 — Preparar a VPS (apenas na primeira vez)

```bash
ssh SEU_USUARIO@IP_DA_VPS

# Crie as redes Docker que o projeto usa (seguro rodar mesmo se ja existirem)
docker network create root_default 2>/dev/null || true
docker network create svc_net 2>/dev/null || true
```

---

### Passo 8 — Disparar o deploy

A partir de agora qualquer push para `main` que altere arquivos em `n8n-runner/` ou `local-files/` dispara o deploy automaticamente.

Para verificar: acesse **github.com/SEU_USER/NOME_DO_REPO → Actions** e acompanhe o workflow em tempo real.

Para forcar um deploy sem alterar codigo:

```bash
git commit --allow-empty -m "chore: trigger deploy" && git push origin main
```

---

## Workflow n8n - Revisao de Artigos

O projeto inclui workflow n8n para revisão automatizada:

```
[Trigger] → [Config] → [HTML to DOCX] → [Agentes IA em paralelo] → [Merge] → [Aplicar Comentarios] → [Output]
                                                ↓
                                    ┌───────────┼───────────┐
                                    ↓           ↓           ↓
                                 [SEO]     [Tecnico]    [Texto]
```

### Fluxo:
1. **Input**: URL do artigo + palavras-chave (opcional)
2. **Conversao**: HTML do artigo vira DOCX
3. **Revisao**: Tres agentes rodam em paralelo
4. **Merge**: Combina todas as sugestoes
5. **Output**: DOCX com comentarios aplicados

### Importar Workflow

1. Acesse n8n → Settings → Import Workflow
2. Cole o JSON de `workflows/`
3. Configure credenciais (Google Drive, se usado)

---

## Uso

### Sincronizar e classificar um curso

```bash
# 1. Sincronizar dados do curso (scraping)
curl -X POST http://runner:8000/utils/cursos \
  -H "Content-Type: application/json" \
  -d '{"course_id": 12345}'

# 2. Classificar competências
curl -X POST "http://runner:8000/utils/cursos/12345/competencias?provider=anthropic"

# 3. Consultar resultado
curl http://runner:8000/utils/cursos/12345/competencias
```

### Revisao de artigos

```bash
# Converter artigo para DOCX
curl -X POST http://runner:8000/revisao/artigos/html-to-docx \
  -H "Content-Type: application/json" \
  -d '{"url": "https://exemplo.com/artigo"}'

# Revisao SEO
curl -X POST http://runner:8000/revisao/artigos/agente-seo-form \
  -F "file=@artigo.docx" \
  -F "palavras_chave=python, machine learning, ia" \
  -F "provider=anthropic"

# Aplicar comentarios
curl -X POST http://runner:8000/revisao/artigos/aplicar-comentarios-form \
  -F "file=@artigo.docx" \
  -F 'revisoes=[{"tipo":"SEO","acao":"substituir","texto_original":"texto antigo","texto_novo":"texto novo","justificativa":"melhora SEO"}]'
```

---

## Debug

```bash
# Logs do container
docker compose --env-file .env logs -f runner

# Acesso ao container
docker exec -it $(docker ps --format '{{.Names}}' | grep runner | head -n1) bash

# Testar conectividade (de dentro do runner)
docker exec -it $(docker ps --format '{{.Names}}' | grep runner | head -n1) \
  python3 -c "import httpx; r = httpx.get('http://localhost:8000/ping'); print(r.status_code, r.text)"
```

---

## Dependencias Principais

- **FastAPI** - Framework web
- **asyncpg** - Cliente PostgreSQL assíncrono
- **anthropic** - SDK Anthropic Claude
- **openai** - SDK OpenAI
- **playwright** - Scraping do Admin Alura
- **python-docx** - Geracao e manipulacao de DOCX
- **BeautifulSoup4** - Parsing HTML para extracao de artigos
- **Pillow / cairosvg** - Processamento de imagens (rasterizacao de SVG)

---

## Notas Tecnicas

### Sincronizacao de Cursos

O sync é incremental por `data_atualizacao`:
- Se a data do curso na API não mudou → retorna cache direto (sem scraping)
- Se mudou → re-faz scraping das tarefas do curso
- Dentro do scraping, tarefas individuais são comparadas por `alura_updated_at`

### Classificador de Competências

- Input: campo `text` de atividades com `kind == "VIDEO"` (transcrições dos vídeos)
- A biblioteca é carregada em memória na inicialização (zero I/O por request)
- Para Anthropic, a biblioteca é enviada com `cache_control: ephemeral` — tokens cacheados entre chamadas
- Resposta validada: IDs inválidos são descartados em vez de lançar erro

### Track Changes OOXML

O sistema implementa Track Changes nativo OOXML (sem depender de LibreOffice):
- Manipulacao direta de `document.xml`
- Suporte a insercoes, delecoes e modificacoes
- Preservacao de formatacao original

### Comentarios DOCX

Comentarios sao inseridos com:
- Ranges sobrepostos para multiplos comentarios no mesmo trecho
- Formatacao visual com emojis por tipo (SEO, TECNICO, TEXTO)
- Estrutura multi-paragrafo para corpo do comentario

### Busca Web (Agente Tecnico)

O agente tecnico usa `web_search` da Anthropic para verificar:
- Versoes atuais de bibliotecas/frameworks
- Documentacao oficial atualizada
- Validade de informacoes tecnicas

### Rodar localmente (desenvolvimento)

```bash
cd n8n-runner

# Sobe o container mapeando a porta 8000 localmente
docker compose -f docker-compose.local.yml --env-file .env up --build

# Testar
curl http://localhost:8000/ping
```

O arquivo `local-files/runner/app.py` e montado como volume — editar o arquivo localmente
reflete imediatamente no container sem precisar rebuild.
