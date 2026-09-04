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
| **`module-6`**  | `auth` and `analytics` services. Custom user with tiering, tags, click tracking, custom manager and queryset. |
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

Served through the gateway at `http://localhost:8000`. **No authentication** —
`DEFAULT_PERMISSION_CLASSES` is `AllowAny` on every service in this module, and
there is no pagination or rate limiting yet either.

| Method | Path | What |
|---|---|---|
| `POST` | `/api/v1/urls/create/` | Create a short URL |
| `GET`  | `/api/v1/urls/` | List active short URLs |
| `GET`  | `/{code}/` | Public redirect |
| `POST` | `/internal/clicks/` | Record a click — service-to-service only |

### POST /api/v1/urls/create/

| Field | Required | Notes |
|---|---|---|
| `original_url` | yes | Max 2048 chars, must be a valid URL |
| `custom_alias` | no | Max 10 chars, unique across aliases *and* generated codes |
| `expires_at` | no | ISO-8601; the redirect returns 410 once it passes |
| `tags` | no | List of names. Unknown names are created, not rejected |

```bash
curl -X POST localhost:8000/api/v1/urls/create/ \
  -H 'Content-Type: application/json' \
  -d '{"original_url":"https://example.com/","custom_alias":"promo","tags":["docs","launch"]}'
```

`201` answers with the full representation, not the fields you sent:

```json
{
  "id": 1,
  "original_url": "https://example.com/",
  "short_code": "aB3xY9",
  "custom_alias": "promo",
  "short_url": "http://localhost:8000/promo/",
  "owner_id": null,
  "tags": [{"id": 1, "name": "docs"}, {"id": 2, "name": "launch"}],
  "title": "", "description": "", "favicon": "",
  "is_active": true,
  "expires_at": null,
  "click_count": 0,
  "created_at": "2026-09-04T09:12:33.481Z"
}
```

A `short_code` is always generated, even alongside an alias, and the generator
retries until it dodges every existing code *and* alias. Both resolve;
`short_url` shows the alias, since that is what `active_code` prefers. A taken
alias or an invalid URL is a `400`.

### GET /api/v1/urls/

```bash
curl localhost:8000/api/v1/urls/
```

A bare JSON array of the object above, newest first. Active means `is_active`
and not past `expires_at`, so a deactivated or expired URL leaves the list
without being deleted. No pagination — this returns every active row.

### GET /{code}/

```bash
curl -i localhost:8000/promo/
```

The one public endpoint. Takes the generated code or the custom alias.

| Status | When |
|---|---|
| `302` | `Location` holds `original_url`; `click_count` is incremented |
| `404` | Unknown code, or `is_active=false` |
| `410` | Past `expires_at` |
| `502` | Analytics could not record the click |

That last row is this module's trade, described above: the redirect blocks on
the click being recorded rather than quietly losing it.

### POST /internal/clicks/

On the analytics service, called by the shortener's `record_click()` on every
redirect with a 3s timeout (`ANALYTICS_TIMEOUT`). The gateway returns 404 for
`/internal/`, so it is reachable inside the compose network and nowhere else.

```json
{
  "url_id": 1,
  "ip_address": "203.0.113.7",
  "user_agent": "Mozilla/5.0 ...",
  "referrer": "https://news.example.com/"
}
```

`url_id` is a plain integer — the click table is in another database and cannot
hold a foreign key to `URL`. `city` and `country` are accepted but never sent:
geo-IP is not in this module, and the fields exist so the schema does not change
when it arrives. `201` on success; any non-2xx, timeout or connection error
becomes the `502` above.

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

