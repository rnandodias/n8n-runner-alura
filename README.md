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

```bash
# Classificar e persistir
POST /utils/cursos/{course_id}/competencias?provider=anthropic&model=claude-sonnet-4-6

# Consultar resultado salvo
GET /utils/cursos/{course_id}/competencias
```

Parâmetros opcionais da classificação:
- `provider`: `"anthropic"` (padrão) ou `"openai"`
- `model`: modelo específico. Se omitido, usa o padrão do provedor.

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

| Model ID | Contexto | Tier | Recomendado para |
|---|---|---|---|
| `gpt-4.1` | 1M tokens | Balanceado (**padrão**) | Uso geral, classificação, revisão |
| `gpt-4.1-mini` | 1M tokens | Mais leve/barato | Bom custo-benefício com contexto grande |
| `gpt-5.4` | 1M tokens | Mais capaz | Tarefas muito complexas |
| `gpt-5.4-mini` | 400k tokens | Balanceado | Bom, mas janela menor |
| `gpt-5.4-nano` | — | Mais barato | Tarefas simples e alto volume |
| `o3` | 200k tokens | Reasoning | Problemas complexos de raciocínio |
| `o4-mini` | 200k tokens | Reasoning leve | Ciência, matemática, código |

> **Nota:** `gpt-4.1` e `gpt-4.1-mini` foram removidos da interface ChatGPT mas continuam **totalmente ativos na API**. Para tarefas com transcrições longas, prefira modelos com janela de 1M tokens.

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
│           │   ├── service.py            # Extrai transcricoes + chama LLM + valida resposta
│           │   ├── prompts.py            # System e user prompts do classificador
│           │   └── biblioteca_competencias.json  # 112 competencias, ~669 habilidades
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
