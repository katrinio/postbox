# Postbox Production Deployment

This guide covers deploying Postbox to a VPS using Docker Compose and nginx reverse proxy.

## Architecture

```
                          ┌─ postbox.finpipe.net (HTTPS)
                          │  nginx reverse proxy
                          │
                ┌─────────┴──────────┬──────────┐
                │                    │          │
            /api/*                 /             (static)
                │                  │
        ┌───────┴──────┐     ┌─────┴──────┐
        │ FastAPI      │     │ Next.js    │
        │ 127.0.0.1:8000      │ 127.0.0.1:3000
        │              │     │            │
        └──────────────┴─────┴────────────┘
        
        Docker container (postbox)
        - Mounts ./data:/data for SQLite persistence
        - Logs rotated via docker json-file driver
        - Health check via /api/ready endpoint
```

## Prerequisites

- Ubuntu/Debian server with Docker and Docker Compose
- nginx reverse proxy (configured outside this repository)
- curl or equivalent for health checks
- Telegram BotFather app to register your domain

## Initial Setup

### 1. Create Application Directory

```bash
sudo mkdir -p ~/projects/postbox
sudo chown $USER:$USER ~/projects/postbox
cd ~/projects/postbox
```

### 2. Clone Repository

```bash
git clone https://github.com/katrinio/postbox.git .
```

### 3. Configure Environment

Create `.env` file with production values:

```bash
cat > .env << 'EOF'
# Security (REQUIRED)
POSTBOX_JWT_SECRET_KEY=replace-with-output-of-openssl-rand-hex-32
POSTBOX_PUBLIC_URL=https://postbox.finpipe.net

# Configuration
POSTBOX_REGISTRATION_LIMIT=5
POSTBOX_LOG_LEVEL=INFO

# Frontend: leave empty to use relative /api paths (recommended)
NEXT_PUBLIC_POSTBOX_API_URL=

# Uvicorn
POSTBOX_API_HOST=127.0.0.1
POSTBOX_API_PORT=8000
POSTBOX_API_RELOAD=false
EOF

chmod 600 .env
```

Generate a strong JWT secret:

```bash
openssl rand -hex 32
```

### 4. Create Data Directories

```bash
mkdir -p data backups
```

The `data/` directory will be mounted inside the container as `/data` and persist across restarts.

### 5. Build Docker Image

```bash
docker compose build
```

Or pull pre-built image:

```bash
docker compose pull
```

### 6. Start Application

```bash
docker compose up -d
```

Verify containers are running:

```bash
docker compose ps
```

Check health:

```bash
curl -s http://127.0.0.1:8000/api/health | jq .
```

## nginx Configuration

Configure nginx to reverse proxy to the Docker containers.

Example `/etc/nginx/sites-available/postbox.finpipe.net`:

```nginx
upstream postbox_api {
    server 127.0.0.1:8000;
}

upstream postbox_web {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    listen [::]:80;
    server_name postbox.finpipe.net;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name postbox.finpipe.net;

    # SSL configuration
    ssl_certificate     /etc/letsencrypt/live/postbox.finpipe.net/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/postbox.finpipe.net/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API paths
    location /api/ {
        proxy_pass http://postbox_api;

        # Proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Connection settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Frontend paths
    location / {
        proxy_pass http://postbox_web;

        # Proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Connection settings
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (not proxied, kept internal)
    location = /_nginx_health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
```

### Enable and Test

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/postbox.finpipe.net \
  /etc/nginx/sites-enabled/postbox.finpipe.net

# Test nginx configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Verify proxy is working
curl -s https://postbox.finpipe.net/api/health | jq .
```

### SSL Certificate

Use Certbot for Let's Encrypt:

```bash
sudo certbot certonly --webroot -w /var/www/html \
  -d postbox.finpipe.net
```

Or use your existing certificate management.

## Database Management

### Backup

Manually create a backup:

```bash
./scripts/backup_sqlite.sh
```

This creates timestamped backups in `./backups/` using SQLite's atomic `VACUUM INTO` command.

For automated backups, add a cron job:

```bash
# Run backup daily at 05:30 UTC
30 5 * * * cd ~/projects/postbox && \
  SOURCE_DB=data/postbox.db BACKUP_DIR=backups ./scripts/backup_sqlite.sh

# Cleanup old backups (older than 30 days) every week
0 2 * * 0 cd ~/projects/postbox && \
  BACKUP_DIR=backups RETENTION_DAYS=30 find backups -name "postbox-*.db" \
  -mtime +30 -delete
```

### Restore from Backup

To restore from a backup:

1. Stop the application:

   ```bash
   docker compose stop
   ```

2. Restore the database:

   ```bash
   cp data/postbox.db data/postbox.db.broken
   cp backups/postbox-TIMESTAMP.db data/postbox.db
   ```

3. Verify integrity:

   ```bash
   ./scripts/verify_backup.sh backups/postbox-TIMESTAMP.db
   ```

4. Restart:

   ```bash
   docker compose up -d
   ```

5. Confirm health:

   ```bash
   curl -s https://postbox.finpipe.net/api/ready | jq .
   ```

## Monitoring

### Uptime Kuma

Configure Uptime Kuma to monitor health:

- **Type**: HTTP(s)
- **URL**: `https://postbox.finpipe.net/api/health`
- **Method**: GET
- **Accepted Status Code**: 200
- **Interval**: 60 seconds
- **Retries**: 2
- **Timeout**: 10 seconds

Expected response:

```json
{
  "status": "ok"
}
```

### Container Logs

View recent logs:

```bash
docker compose logs --tail=100 postbox
```

Follow logs in real-time:

```bash
docker compose logs -f postbox
```

Filter by service:

```bash
docker compose logs postbox | grep ERROR
```

### Service Status

```bash
docker compose ps
docker stats
```

## Deployment

### Automatic Deployment (GitHub Actions)

After setting up GitHub secrets (`POSTBOX_HOST`, `POSTBOX_USER`, `POSTBOX_SSH_KEY`), deployment runs automatically on push to `main`.

The workflow:
1. Builds Docker image
2. Pushes to GitHub Container Registry
3. SSH into VPS and runs deployment script

### Manual Deployment

Deploy the latest code manually:

```bash
cd ~/projects/postbox
./scripts/deploy.sh
```

This script:
1. Fetches latest code
2. Creates database backup
3. Rebuilds Docker image
4. Restarts containers (gracefully, no data loss)
5. Waits for health check
6. Shows status

### Rollback

If deployment fails or issues are found, rollback to previous commit:

```bash
git log --oneline | head -5
git reset --hard <commit-hash>
docker compose up -d
```

## Telegram Web App Configuration

Register your domain with Telegram BotFather:

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/setdomain`
3. Select your bot
4. Enter: `postbox.finpipe.net`

Your bot's Telegram Web App will now open at:
```
https://t.me/[YOUR_BOT]/app?startapp=...
```

And authenticate users via:
```
POST https://postbox.finpipe.net/api/auth/telegram
```

## Troubleshooting

### Containers won't start

```bash
docker compose logs postbox
```

Check:
- Is `.env` file present and readable?
- Is `POSTBOX_JWT_SECRET_KEY` set?
- Is port 8000 and 3000 available?

### Health check failing

```bash
docker compose exec postbox curl http://127.0.0.1:8000/api/ready
```

Check:
- Is database file writable?
- Is `/data` directory mounted?
- Are database migrations applied?

### nginx 502 Bad Gateway

```bash
sudo tail -f /var/log/nginx/error.log
curl -v http://127.0.0.1:8000/api/health
```

Check:
- Are containers running? `docker compose ps`
- Is port 8000 listening? `netstat -an | grep 8000`
- Check docker logs: `docker compose logs postbox`

### Database locked

SQLite can lock if two processes access it simultaneously. If you see `database is locked`:

1. Stop the application: `docker compose stop`
2. Verify integrity: `sqlite3 data/postbox.db "PRAGMA integrity_check;"`
3. Restart: `docker compose up -d`

## Maintenance

### Update Application Code

```bash
cd ~/projects/postbox
git fetch origin main
git reset --hard origin/main
docker compose build
docker compose up -d
```

Or use the deployment script:

```bash
./scripts/deploy.sh
```

### Update Docker Image

```bash
docker compose pull
docker compose up -d
```

### View Statistics

```bash
docker stats
docker system df
```

### Clean Up

Remove unused images and volumes:

```bash
docker image prune -f
docker system prune
```

**Warning**: Do not use `docker volume prune`; it may delete persistent data.

## File Permissions

The application runs as user `postbox` (UID 10001) inside the container.

The host directories must be readable/writable:

```bash
ls -la ~/projects/postbox/
drwxr-xr-x  data
drwxr-xr-x  backups
-rw-------  .env
```

If permission issues occur:

```bash
sudo chown -R $USER:$USER ~/projects/postbox/data
sudo chown -R $USER:$USER ~/projects/postbox/backups
```

---

**Questions?** Check the main [README.md](../README.md) or open an issue.
