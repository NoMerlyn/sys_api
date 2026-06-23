# Deploy a Render (free tier)

## Pasos

1. **Crear cuenta en Render** (https://render.com). Free tier requiere tarjeta pero no cobra mientras uses el plan free.

2. **Crear Postgres**:
   - Dashboard → New → PostgreSQL
   - Plan: Free
   - Name: `pos-postgres`

3. **Crear Web Services** (uno por repo):
   - Dashboard → New → Web Service → "Connect a repository"
   - **sys_api**: 
     - Runtime: Docker
     - Dockerfile: `./Dockerfile`
     - Health Check: `/health/live`
     - Env vars:
       - `DATABASE_URL` (Internal Database URL del paso 2)
       - `DATABASE_URL_SYNC` (la misma pero con `postgresql+psycopg2://`)
       - `JWT_SECRET` (openssl rand -hex 32)
       - `JWT_ISSUER=sys-api`
       - `JWT_AUDIENCE=pos-front`
       - `RABBITMQ_URL=amqp://user:pass@host:5672/`
       - `CORS_ORIGINS=https://sys-front.onrender.com`
   - **sys_invoice_check**: mismo setup, mismo `JWT_SECRET`
   - **sys_front**:
     - Runtime: Static Site
     - Build Command: `npm ci && npm run build`
     - Publish Path: `./dist`
     - Env vars:
       - `VITE_API_BASE_URL=https://sys-api.onrender.com`
       - `VITE_VALIDATOR_BASE_URL=https://sys-invoice-check.onrender.com`

4. **Configurar RabbitMQ**:
   - Render no incluye RabbitMQ en free tier
   - Usar CloudAMQP free tier (https://www.cloudamqp.com/) — 1 instancia gratis permanente
   - Copiar URL AMQP y setear como `RABBITMQ_URL` en los 3 web services

5. **Migrations**: `entrypoint.sh` corre `alembic upgrade head` antes de `uvicorn` (v0.2.1)

6. **Seed inicial**: render one-off job con `python -m app.scripts.seed`

## URLs esperadas

- Front: `https://sys-front.onrender.com`
- API: `https://sys-api.onrender.com` (Swagger en `/docs`)
- Validator: `https://sys-invoice-check.onrender.com`

## Limitaciones del free tier

- **Postgres**: 90 días free, después $7/mo
- **Web services**: cold start de ~30s si idle 15 min
- **Cold start afecta UX**: el primer request del día es lento

## Alternativa: Fly.io

Si Render te complica, Fly.io tiene free tier permanente:
- `brew install flyctl`
- `fly launch --no-deploy`
- `fly postgres create` (free)
- `fly redis create` (free, para el broker)
- `fly secrets set JWT_SECRET=$(openssl rand -hex 32)`
- `fly deploy`
