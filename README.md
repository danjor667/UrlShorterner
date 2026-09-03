# URL Shortener — Module 6

A URL shortener built as microservices, one module per branch. This branch adds
the two services that make the split real: **auth** and **analytics**.

```
   http://localhost:8000   ┌─────────────────┐
   ──────────────────────▶ │  nginx gateway  │
                           └────────┬────────┘
         /api/v1/auth/  ┌───────────┼───────────┐  /api/v1/analytics/
         /admin/auth/   │           │           │  /admin/analytics/
                        ▼           ▼           ▼
                  ┌──────────┐ ┌──────────┐ ┌───────────┐
                  │   auth   │ │shortener │ │ analytics │
                  └────┬─────┘ └────┬─────┘ └─────┬─────┘
                       │            │  records    │
                       │            └── click ───▶│
                       ▼            ▼             ▼
                  ┌──────────┐ ┌──────────┐ ┌───────────┐
                  │ db-auth  │ │db-short..│ │db-analyt..│
                  └──────────┘ └──────────┘ └───────────┘
```

Three services, three Postgres containers, three databases. A service owns its
data outright — nothing else holds a connection to it.

## What database-per-service costs

Two relations that were foreign keys in the monolith cannot be, because they
cross a database boundary:

| Was | Is now |
|---|---|
| `URL.owner` → `User` | `URL.owner_id`, a plain integer into the auth service |
| `Click.url` → `URL` | `Click.url_id`, a plain integer into the shortener |

Nothing at the database level enforces either. Deleting a user no longer
cascades to their URLs, and `URL.objects.popular()` ranks by the denormalized
`click_count` rather than `Count('clicks')` — the click table is not in this
database and the app is not installed here.

Recording a click is therefore an HTTP call. The redirect **blocks** on it: if
analytics cannot record the click, the redirect returns `502` instead of
serving a link whose click nobody counted. That puts analytics on the critical
path of every short link, which is the trade this module makes deliberately —
Module 8's Celery hand-off is what removes it.

## Modules

| Branch | Adds |
|---|---|
| `master` | The skeleton. `URL` model, create / list / redirect, Swagger, admin, gateway, Docker. One service, its own database. |
| **`module-6`** ← you are here | `auth` and `analytics` services. Custom user with tiering, tags, click tracking, custom manager and queryset. |
| `module-7` | JWT (RS256), registration and login, ownership permissions, premium tiers, the analytics endpoint. |
| `module-8` | Redis caching, Celery workers and beat, structured logging, health probes, production settings. |

The pre-microservice history of this branch is kept at the tag
`module-6-monolith`.

## Layout

```
libs/common/            base_settings.py — shared settings + service_database()
services/auth/
  account/              custom User with tiering; AUTH_USER_MODEL
  auth_service/         settings, urls (admin at /admin/auth/), wsgi
services/shortener/
  shortener/            URL, Tag, URLQuerySet/URLManager, analytics_client.py
  shortener_service/    settings, root urls, wsgi
services/analytics/
  analytics/            Click event log + the internal write API
  analytics_service/    settings, urls (admin at /admin/analytics/), wsgi
gateway/nginx.conf      routing; the shortener owns the `/` catch-all
docker-compose.yml      3 services + 3 databases + gateway; only the gateway is published
```

Each service has its own `Dockerfile`, `entrypoint.sh` and `requirements.txt`.
The build context is the repo root so `libs/` can be copied in; `.dockerignore`
keeps that context to a couple of kilobytes.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

Exactly one port is published — the gateway's. The services and all three
databases are reachable only from inside the compose network.

| URL | What |
|---|---|
| `http://localhost:8000/{code}` | Public redirect |
| `http://localhost:8000/api/v1/urls/` | The shortener API |
| `http://localhost:8000/api/docs/` | Swagger UI (the shortener's) |
| `http://localhost:8000/admin/` | Shortener admin — URLs and tags |
| `http://localhost:8000/admin/auth/` | Auth admin — users and tiers |
| `http://localhost:8000/admin/analytics/` | Analytics admin — click log |

Three services each have an admin and only one can own a path, so the two new
ones are mounted under a suffix. `/api/v1/auth/` and `/api/v1/analytics/` are
routed but have no views behind them yet — Module 7 fills them in without
touching the gateway.

`POST /internal/clicks/` on the analytics service is service-to-service only.
The gateway returns 404 for `/internal/` so it cannot be reached from outside.

## The API

```bash
# create, with tags
curl -X POST localhost:8000/api/v1/urls/create/ -H 'Content-Type: application/json' \
  -d '{"original_url":"https://example.com/","custom_alias":"promo","tags":["docs","launch"]}'

# list active
curl localhost:8000/api/v1/urls/

# follow — writes a Click row in the analytics database
curl -I localhost:8000/promo/
```

## Tests

Each service has its own suite and its own test database:

```bash
docker compose exec shortener python manage.py test    # 41
docker compose exec auth      python manage.py test    # 7
docker compose exec analytics python manage.py test    # 8
```

The shortener's redirect tests patch `record_click`: a unit test of one service
should not need a second one running. The real cross-service call is covered by
running the stack.

## Not in this module

No authentication — every endpoint is public, and `DEFAULT_PERMISSION_CLASSES`
says so explicitly. No registration or login, and no public analytics endpoint;
those are Module 7. No caching or background work; that is Module 8.

Also missing on purpose: the list endpoint has no pagination, `Click.city` and
`Click.country` are never populated (no geo-IP lookup yet), and the analytics
service cannot show you a URL's `short_code` — it stores only `url_id`, and the
read model that fixes that arrives with the Module 7 reporting endpoint.
