# Deploy no Google Cloud Run

Projeto GCP: **caldas-projects-dev** | Região: **us-central1**

## Pré-requisitos (one-time)

```bash
gcloud config set project caldas-projects-dev

# Artifact Registry
gcloud artifacts repositories create passanota-images \
  --repository-format=docker \
  --location=us-central1
```

### Secret Manager

A API monta variáveis de ambiente a partir de secrets no Secret Manager. Os nomes padrão estão em `cloudbuild.yaml` (`_SECRET_*`).

| Variável na API | Secret padrão | Obrigatório |
|-----------------|---------------|-------------|
| `DATABASE_URL` | `PASSANOTA_DATABASE_URL` | Sim |
| `SUPABASE_SECRET_KEY` | `PASSANOTA_SUPABASE_SECRET_KEY` | Sim |
| `LLM_PROVIDER_API_KEY` | `PASSANOTA_OPENAI_API_KEY` | Sim (se OpenAI) |
| `RESEND_API_KEY` | `RESEND_API_KEY` | Sim |

**PowerShell — criar secrets:**

```powershell
gcloud config set project caldas-projects-dev

"postgresql+asyncpg://..." | gcloud secrets create PASSANOTA_DATABASE_URL --replication-policy=automatic --data-file=-
"sb_secret_..." | gcloud secrets create PASSANOTA_SUPABASE_SECRET_KEY --replication-policy=automatic --data-file=-
"sk-..." | gcloud secrets create PASSANOTA_OPENAI_API_KEY --replication-policy=automatic --data-file=-
```

Nova versão de secret existente:

```powershell
"valor" | gcloud secrets versions add NOME_DO_SECRET --data-file=-
```

Conceda `roles/secretmanager.secretAccessor` ao service account do Cloud Run (`{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`) e ao Cloud Build SA.

### IAM — API restrita ao frontend

A API usa `--no-allow-unauthenticated`. Apenas **passanota-web** e **Cloud Tasks** podem invocá-la.

```powershell
.\scripts\setup-api-iam.ps1
```

```bash
./scripts/setup-api-iam.sh
```

Execute **antes** do primeiro deploy com IAM, ou imediatamente antes de remover acesso público.

### Migrations (antes do primeiro deploy)

```bash
uv run alembic upgrade head
```

Use connection string **direct** (porta 5432) se o pooler falhar.

## Cloud Build via GitHub

### Conectar repositório

1. Cloud Console → Cloud Build → Repositories → Connect repository (GitHub 2nd gen)
2. Autorize e selecione `passanota-api`

### Triggers

| Trigger | Evento | Arquivo |
|---------|--------|---------|
| `passanota-api-pr` | PR → `main` | `cloudbuild.pr.yaml` |
| `passanota-api-main` | Push → `main` | `cloudbuild.yaml` |

```powershell
.\scripts\setup-cloud-build-trigger.ps1 -GitHubOwner SEU_USER -GitHubRepo passanota-api `
  -FrontendUrl "https://passanota-web-....run.app" `
  -SupabaseUrl "https://....supabase.co" `
  -TaskHandlerBaseUrl "https://passanota-api-....run.app"
```

Substitutions obrigatórias no trigger **main**:

- `_TAG=$SHORT_SHA`
- `_FRONTEND_URL`, `_SUPABASE_URL`, `_TASK_HANDLER_BASE_URL`
- `_CLOUD_TASKS_SERVICE_ACCOUNT` (ex.: `{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`)

O pipeline **main** executa: validate secrets → ruff → pytest → docker build → push → deploy (sem acesso público).

O pipeline **PR** executa: validate → ruff → pytest → docker build (sem push/deploy).

## Deploy manual (emergência)

**PowerShell:**

```powershell
cd passanota-api
$env:TAG = "hotfix-2026-06-23"
.\scripts\deploy.ps1
```

**Com substitutions completas:**

```bash
gcloud builds submit --project=caldas-projects-dev \
  --config=cloudbuild.yaml \
  --substitutions=_TAG=v1.0.0,_FRONTEND_URL=https://passanota-web-XXXX.run.app,_SUPABASE_URL=https://ref.supabase.co,_TASK_HANDLER_BASE_URL=https://passanota-api-XXXX.run.app,_CLOUD_TASKS_SERVICE_ACCOUNT=399951936554-compute@developer.gserviceaccount.com
```

## Cloud Tasks (processamento assíncrono)

```powershell
.\scripts\setup-cloud-tasks.ps1
```

Em dev local: `CLOUD_TASKS_ENABLED=false` — worker inline após commit.

### Migration 007

```bash
uv run alembic upgrade head
```

## Sequência de rollout (IAM)

1. Criar secrets no Secret Manager
2. `setup-cloud-tasks.ps1` + `setup-api-iam.ps1`
3. Deploy API (`cloudbuild.yaml` — já com `--no-allow-unauthenticated`)
4. Deploy frontend com suporte a ID token (passanota-web)
5. Validar: app funciona; `curl API/docs` → 403; Cloud Tasks processa notas

**Ordem:** API primeiro, depois Web.

## Pós-deploy — Supabase

1. **Authentication → URL Configuration** — Site URL e redirect URLs do frontend
2. Extensão `vector` e bucket `invoice-photos`
3. `_FRONTEND_URL` / `_APP_URL` apontando para URL final do web
