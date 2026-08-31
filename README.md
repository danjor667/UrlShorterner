# URL Shortener — Module 5

A URL shortener built as microservices, one module per branch. This branch is
the **base**: the microservice skeleton with a single service inside it.

```
   http://localhost:8000   ┌─────────────────┐
   ──────────────────────▶ │  nginx gateway  │
                           └────────┬────────┘
                                    │  everything
                                    ▼
                            ┌───────────────┐
                            │   shortener   │  :8001
                            │   (:8000)     │
                            └───────┬───────┘
                                    ▼
                            ┌───────────────┐
                            │  urlshortener │  one database,
                            └───────────────┘  shared by every service
```

One service today. The gateway is here from the start because retrofitting it
is painful: short links must resolve at the root (`/abc123`), so the shortener
has to own the `/` catch-all and every service added later gets routed by a
prefix *above* it.

Every service connects to the same database. Table names are namespaced by app
label — `shortener_url`, later `account_user` and `analytics_click` — so they
do not collide. From Module 6 each service migrates only its own app, so three
of them do not race to apply Django's built-in migrations.

## Modules

| Branch | Adds |
|---|---|
| **`master`** ← you are here | The skeleton. `URL` model, create / list / redirect, Swagger, admin, gateway, Docker. No authentication. |
| `module-6` | `auth` and `analytics` services. Custom user with tiering, tags, click tracking, custom manager and queryset. |
| `module-7` | JWT (RS256), registration and login, ownership permissions, premium tiers, the analytics endpoint. |
| `module-8` | Redis caching, Celery workers and beat, structured logging, health probes, production settings. |

Each branch builds on the one above it, so `module-8` is the complete project.

## Layout

```
libs/common/           settings shared by every service
services/shortener/
  shortener/           URL model + migrations
  shortener_service/   settings, urls, wsgi
  api/                 serializers, views, routes
  tests/
  Dockerfile, requirements.txt, manage.py
gateway/nginx.conf     routing; the shortener owns the `/` catch-all
```

`libs/common` holds one file and looks like overhead with a single service.
It earns its place in Module 6, when two more services need to agree with it.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

| URL | What |
|---|---|
| `http://localhost:8000` | Gateway — the only port a deployment exposes |
| `http://localhost:8000/{code}` | Public redirect |
| `http://localhost:8000/admin/` | Django admin (`manage.py createsuperuser`) |
| `http://localhost:8001/api/docs/` | Swagger UI |

## The API

```bash
# create
curl -X POST localhost:8000/api/v1/urls/create/ -H 'Content-Type: application/json' \
  -d '{"original_url":"https://example.com/","custom_alias":"promo"}'

# list active
curl localhost:8000/api/v1/urls/

# follow
curl -I localhost:8000/promo/
```

A URL is reachable by its generated `short_code` or its `custom_alias`, so an
alias is rejected if it collides with either column on any existing row.

## Tests

Run against a live Postgres (`docker compose up -d db`):

```bash
pip install -r requirements-dev.txt
cd services/shortener && python manage.py test    # 19
```

## Not in this module

No authentication — every endpoint is public, and `DEFAULT_PERMISSION_CLASSES`
says so explicitly rather than leaving it to a default. No caching, no
background work, no click history beyond a counter. Those arrive in 6 through 8.

Also missing on purpose, so it is not mistaken for an oversight: the list
endpoint has no pagination and returns every active URL in one response.
