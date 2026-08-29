# Passanota API

API de controle de custos via leitura de notas fiscais com IA, PostgreSQL (Supabase) e pgvector.

## Requisitos

- Python 3.13+
- Projeto [Supabase](https://supabase.com) com PostgreSQL
- Provedor de IA com visão (OpenAI, Gemini ou Anthropic)

## Variáveis de ambiente

| Variável | Uso |
|----------|-----|
| `LLM_PROVIDER` | Provedor de visão: `openai`, `gemini` ou `anthropic` |
| `LLM_PROVIDER_API_KEY` | Chave do provedor de IA (OpenAI, Google, Anthropic) |
| `EMBEDDING_MODEL` | Embeddings OpenAI (`text-embedding-3-small`) |
| `DATABASE_URL` | Connection string do Supabase Postgres |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | Storage e validação de tokens |

Aliases legados ainda aceitos: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `SUPABASE_SERVICE_ROLE_KEY`.

## Setup com Supabase

### 1. Scripts SQL no Supabase (uma vez)

No **SQL Editor** do painel Supabase, execute nesta ordem:

1. `supabase/enable_pgvector.sql` — habilita extensão `vector`
2. `supabase/storage_invoice_photos.sql` — cria bucket de fotos

### 2. Configurar `.env`

```bash
cp .env.example .env
```

Preencha `DATABASE_URL` com a connection string do Supabase (Settings → Database → URI). Pode colar `postgresql://...` — o driver `+asyncpg` é aplicado automaticamente.

**Dica:** use o **Session pooler** (porta 6543) para a API; **Direct** (5432) para migrations se o pooler falhar.

### 3. Aplicar schema com Alembic

O Alembic aplica as migrations no Postgres do Supabase — é assim que a estrutura vai para o banco remoto:

```bash
uv sync --extra dev --extra cv

# Ver estado atual
uv run alembic current

# Aplicar todas as migrations pendentes
uv run alembic upgrade head
```

Isso executa, em ordem:

| Revision | Conteúdo |
|----------|----------|
| `001` | Tabelas base, pgvector, categorias |
| `002` | Remove api_keys legado |
| `003` | Empresas, funcionários, multi-tenancy |
| `004` | Campos foto/IA, keywords, funções SQL |
| `011` | Embeddings OpenAI `vector(512)` |

Depois do `upgrade head` em produção, rode `uv run python scripts/reembed.py` para preencher categorias e itens sem vetor. Notas presas em `pending`: `uv run python scripts/requeue_pending.py` (ou `--inline` em local).

**Banco novo no Supabase:** rode `upgrade head` uma vez após os scripts SQL de extensão.

**Verificar:**

```bash
uv run alembic current   # deve mostrar 011 (head)
```

### 4. Subir a API

```bash
uv run uvicorn app.main:app --reload
```

## Fluxo de captura

```
Foto → OpenCV → LLM (1x) → SQL (normalização + categoria) → banco
```

## Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/v1/invoices/capture` | Captura foto + extração IA |
| GET | `/v1/invoices` | Lista paginada |
| GET | `/v1/invoices/{id}` | Detalhe |
| GET | `/v1/dashboard/*` | Análises |
| POST | `/v1/search/semantic` | Busca semântica |

Rotas `/v1/*` exigem autenticação Supabase (`Authorization: Bearer`) ou token de dispositivo (`X-Device-Token`).

## Deploy (Cloud Run)

Ver [docs/DEPLOY-GCP.md](docs/DEPLOY-GCP.md).

## Testes

```bash
uv run python -m pytest
```
