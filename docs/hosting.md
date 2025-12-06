Here is an updated version of `docs/hosting.md` that matches the new architecture (Next.js UI + HTTP API) and keeps the `/abstract_wiki_architect` mounting on `konnaxion.com`:

````md
You can do that. Keep everything for Konnaxion on `konnaxion.com`, and mount Abstract Wiki Architect under the path `/abstract_wiki_architect` by adding one extra location in Nginx that points to a separate process/container.

### 1. Run Abstract Wiki Architect as separate services

Whether you use Docker or not, the idea is:

* Konnaxion Next.js (main site): listens on `127.0.0.1:3000`
* Abstract Wiki Architect frontend (Next.js under `architect_frontend`): listens on `127.0.0.1:4000`
* Abstract Wiki Architect HTTP API (FastAPI under `architect_http_api`): listens on `127.0.0.1:5001` (internal only)

You can run them however you want (systemd, bare `uvicorn`, `npm run start`, etc.). With Docker, a simple pattern is:

```bash
# Frontend (Next.js UI)
docker build -f docker/Dockerfile.frontend -t abstractwiki-frontend .

docker run -d --name abstractwiki-frontend \
  -p 127.0.0.1:4000:3000 \
  abstractwiki-frontend

# Backend (HTTP API, FastAPI)
docker build -f docker/Dockerfile.backend -t abstractwiki-backend .

docker run -d --name abstractwiki-backend \
  -p 127.0.0.1:5001:8000 \
  abstractwiki-backend
````

Adjust the container internal ports (`3000`, `8000`) if your Dockerfiles use different ones. The only requirements are:

* The Architect **frontend** must be reachable on `http://127.0.0.1:4000/`.
* The Architect **HTTP API** must be reachable on `http://127.0.0.1:5001/` from the frontend (same host, Docker network, or similar).

Configure the frontend so it knows:

* Its base URL is `/abstract_wiki_architect` (Next.js `basePath`).
* Its API base is `/abstract_wiki_architect/api` (or another prefix you choose consistently with Nginx).

---

### 2. Update the Nginx config for konnaxion.com

Open your Nginx server block for `konnaxion.com`:

```bash
sudo nano /etc/nginx/sites-available/konnaxion.conf
```

You probably have something like this already:

```nginx
server {
    listen 80;
    server_name konnaxion.com www.konnaxion.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Add new `location` blocks **before** the generic `/` location:

```nginx
server {
    listen 80;
    server_name konnaxion.com www.konnaxion.com;

    # Abstract Wiki Architect HTTP API (internal JSON API)
    location /abstract_wiki_architect/api/ {
        proxy_pass http://127.0.0.1:5001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Abstract Wiki Architect frontend (Next.js UI)
    location /abstract_wiki_architect/ {
        proxy_pass http://127.0.0.1:4000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Konnaxion Next.js frontend (main site)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Key points:

* The `location /abstract_wiki_architect/api/` block comes **before** `/abstract_wiki_architect/` so API calls don’t get swallowed by the UI route.
* The `location /abstract_wiki_architect/` block comes before the generic `/` so Nginx sends that path to the Architect UI, not to the main Konnaxion Next.js app.
* `proxy_pass http://127.0.0.1:4000/;` and `proxy_pass http://127.0.0.1:5001/;` both have a trailing `/`, which keeps the rest of the path after `/abstract_wiki_architect/...` when forwarding.

Then reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

If you already have HTTPS via Certbot, this change goes in the `server { listen 443 ssl; ... }` block instead (or in both 80 and 443, depending on how Certbot configured it).

---

### 3. What you get

* `https://konnaxion.com/` → Konnaxion Next.js app (main site).
* `https://konnaxion.com/abstract_wiki_architect` → Abstract Wiki Architect UI (frontend).
* `https://konnaxion.com/abstract_wiki_architect/api/...` → Abstract Wiki Architect HTTP API (FastAPI).

No extra DNS records are needed. Everything stays under the same domain and is routed by Nginx using path-based routing.
