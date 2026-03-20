# Runner Alura - Agente de Revisao Automatica de Artigos

Servico FastAPI para revisao automatizada de artigos, integrado ao n8n via containers Docker.

## Visao Geral

Este projeto fornece um runner FastAPI que combina:
- **BeautifulSoup/httpx** para extração de conteúdo de artigos e conversão para DOCX
- **Agentes de IA** (Anthropic Claude e OpenAI GPT) para revisao automatizada de artigos
- **python-docx / OOXML** para manipulacao de documentos e aplicacao de comentarios

Usado como sidecar do n8n para automacoes envolvendo revisao de artigos com IA.

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
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  BeautifulSoup   │  │   Agentes de IA  │  │ python-docx  │  │
│  │  (extracao HTML) │  │  Claude / GPT    │  │  (OOXML)     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Endpoints

### Utilitarios

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/ping` | GET | Health check do servico |

### Conversao de Artigos

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/html-to-docx` | POST | Converte URL de artigo para DOCX binario |

### Revisao com Agentes de IA

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/revisao/extrair-texto` | POST | Extrai texto de DOCX para revisao |
| `/revisao/aplicar` | POST | Aplica revisoes com Track Changes (OOXML) |
| `/revisao/aplicar-json` | POST | Aplica revisoes JSON via form |
| `/revisao/aplicar-form` | POST | Aplica revisoes via multipart form |
| `/revisao/aplicar-comentarios-form` | POST | Aplica revisoes como comentarios DOCX |
| `/revisao/agente-seo` | POST | Agente de revisao SEO/GEO |
| `/revisao/agente-tecnico` | POST | Agente de revisao tecnica |
| `/revisao/agente-texto` | POST | Agente de revisao textual/didatica |
| `/revisao/agente-seo-form` | POST | Agente SEO via multipart form |
| `/revisao/agente-tecnico-form` | POST | Agente tecnico via multipart form |
| `/revisao/agente-texto-form` | POST | Agente texto via multipart form |
| `/revisao/agente-imagem` | POST | Agente de revisao de imagens (visao multimodal) |
| `/revisao/agente-imagem-form` | POST | Agente imagem via multipart form |

---

## Agentes de Revisao de Artigos

O sistema inclui quatro agentes especializados de IA para revisao de artigos:

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

**Nota:** O agente de imagem requer `url_artigo` para extrair as imagens via scraping.
Com Anthropic, usa visao + busca web. Com OpenAI, usa apenas visao.

### Formato de Saida

Todos os agentes retornam JSON estruturado:

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
├── local-files/
│   └── runner/
│       ├── app.py                 # Aplicacao FastAPI principal
│       ├── llm_client.py          # Cliente unificado LLM (Anthropic/OpenAI)
│       ├── prompts_revisao.py     # Prompts dos agentes de revisao
│       └── track_changes.py       # Implementacao OOXML Track Changes
├── n8n-runner/
│   ├── docker-compose.yml         # Compose do runner
│   └── runner/
│       ├── Dockerfile             # Imagem Docker
│       ├── requirements.txt       # Dependencias Python
│       └── start.sh               # Script de inicializacao
├── workflows/
│   └── *.json                     # Workflows n8n exportados
└── README.md
```

---

## Configuracao

### Variaveis de Ambiente

Criar `/opt/n8n-runner/.env` na VPS:

```env
# APIs de LLM
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Provider padrao (anthropic ou openai)
LLM_PROVIDER=anthropic

# Modelo padrao (opcional)
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
2. Criar diretorios:
   ```bash
   sudo mkdir -p /opt/n8n-runner/runner
   sudo mkdir -p /local-files/runner
   ```

### Deploy Manual

```bash
cd /opt/n8n-runner
docker compose --env-file .env build runner
docker compose --env-file .env up -d runner
docker compose --env-file .env logs -f runner
```

### Debug

```bash
# Logs do container
docker compose --env-file .env logs -f runner

# Acesso ao container
docker exec -it $(docker ps --format '{{.Names}}' | grep runner | head -n1) bash

# Testar conectividade (de dentro do n8n)
docker exec -it $(docker ps --format '{{.Names}}' | grep n8n | head -n1) \
  sh -lc "curl -i http://runner:8000/ping"
```

---

## Workflow n8n - Revisao de Artigos

O projeto inclui workflow n8n para revisao automatizada:

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

### Interno (de dentro do container n8n)

```bash
# Converter artigo para DOCX
curl -X POST http://runner:8000/html-to-docx \
  -H "Content-Type: application/json" \
  -d '{"url": "https://exemplo.com/artigo"}'

# Revisao SEO
curl -X POST http://runner:8000/revisao/agente-seo-form \
  -F "file=@artigo.docx" \
  -F "palavras_chave=python, machine learning, ia" \
  -F "provider=anthropic"

# Aplicar comentarios
curl -X POST http://runner:8000/revisao/aplicar-comentarios-form \
  -F "file=@artigo.docx" \
  -F 'revisoes=[{"tipo":"SEO","acao":"substituir","texto_original":"texto antigo","texto_novo":"texto novo","justificativa":"melhora SEO"}]'
```

---

## Dependencias Principais

- **FastAPI** - Framework web
- **python-docx** - Geracao e manipulacao de DOCX
- **anthropic** - SDK Anthropic Claude
- **openai** - SDK OpenAI
- **BeautifulSoup4** - Parsing HTML para extracao de artigos
- **Pillow / cairosvg** - Processamento de imagens

---

## Notas Tecnicas

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

---

## Guia Completo de Deploy

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

# Apaga historico Git antigo (se existir)
rm -rf .git

# Inicia repositorio novo e limpo
git init
git branch -M main

# Conecta ao GitHub (substitua pela URL do seu repo)
git remote add origin https://github.com/rnandodias/n8n-runner-alura.git
```

---

### Passo 3 — Primeiro commit e push

Adicione apenas os arquivos do projeto — **nunca o .env**.

```bash
git add .gitignore
git add ENV.EXAMPLE.txt
git add README.md
git add CLAUDE.md
git add .github/workflows/deploy-runner.yml
git add n8n-runner/docker-compose.yml
git add n8n-runner/runner/Dockerfile
git add n8n-runner/runner/requirements.txt
git add n8n-runner/runner/start.sh
git add local-files/runner/app.py
git add local-files/runner/llm_client.py
git add local-files/runner/prompts_revisao.py
git add local-files/runner/track_changes.py

git commit -m "Inicial: Agente de Revisao Automatica de Artigos"
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
# Conecte na VPS
ssh SEU_USUARIO@IP_DA_VPS

# Instale o Docker (se ainda nao tiver)
curl -fsSL https://get.docker.com | sh

# Crie as redes Docker que o projeto usa
docker network create root_default 2>/dev/null || true
docker network create svc_net 2>/dev/null || true

# Crie os diretorios necessarios
mkdir -p /opt/n8n-runner /local-files/runner
```

---

### Passo 8 — Disparar o deploy

A partir de agora qualquer push para `main` que altere arquivos em `n8n-runner/` ou `local-files/` dispara o deploy automaticamente.

Para verificar: acesse **github.com/SEU_USER/NOME_DO_REPO → Actions** e acompanhe o workflow em tempo real.

Para forcar um deploy sem alterar codigo:

```bash
git commit --allow-empty -m "chore: trigger deploy"
git push origin main
```

---

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
