# Background Removal Microservice — Complete Operations Guide

## Project Structure

```
bgremove/
├── main.py                  # FastAPI application entry point
├── app/
│   ├── __init__.py
│   ├── config.py            # Pydantic settings (env-driven)
│   ├── logger.py            # Structured JSON logging (structlog)
│   ├── model.py             # rembg singleton + warm-up
│   ├── security.py          # Magic-byte, MIME, decompression-bomb guards
│   └── processing.py        # In-memory inference pipeline
├── requirements.txt
├── gunicorn.conf.py         # Production Gunicorn tuning
├── bgremove.service         # systemd unit file
├── nginx.conf               # Nginx reverse proxy + TLS
└── .env.example             # Environment variable template
```

---

## 1. VPS Deployment (Hetzner CX21 / DigitalOcean Basic — 2 vCPU, 4 GB RAM)

### 1.1 Server bootstrap

```bash
# As root on a fresh Ubuntu 22.04 LTS
apt update && apt upgrade -y
apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx \
               build-essential libssl-dev git

# Create a dedicated, unprivileged user
useradd -m -s /bin/bash -d /opt/bgremove bgremove
```

### 1.2 Application setup

```bash
su - bgremove         # switch to service user

# Clone / upload your code
git clone https://github.com/yourorg/bgremove /opt/bgremove
cd /opt/bgremove

# Create virtualenv and install deps
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt

# Pre-download model weights (avoids first-request cold start)
python3 -c "import rembg; rembg.new_session('u2net')"
```

### 1.3 Environment file

```bash
# As root
cp /opt/bgremove/.env.example /etc/bgremove.env
chmod 600 /etc/bgremove.env
chown bgremove:bgremove /etc/bgremove.env

# Edit and set API_KEY, WEB_CONCURRENCY, etc.
nano /etc/bgremove.env
```

### 1.4 systemd

```bash
cp /opt/bgremove/bgremove.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now bgremove
systemctl status bgremove
```

### 1.5 Nginx + HTTPS

```bash
# Point your DNS A record at the VPS IP first, then:
cp /opt/bgremove/nginx.conf /etc/nginx/sites-available/bgremove

# Edit server_name in nginx.conf
sed -i 's/api.example.com/your.actual.domain.com/g' \
    /etc/nginx/sites-available/bgremove

ln -s /etc/nginx/sites-available/bgremove /etc/nginx/sites-enabled/
nginx -t

# Obtain TLS certificate (auto-renews via systemd timer)
certbot --nginx -d your.actual.domain.com
systemctl reload nginx
```

---

## 2. Production Run Command

```bash
# Direct Gunicorn invocation (the systemd unit does this automatically)
/opt/bgremove/venv/bin/gunicorn -c gunicorn.conf.py main:app
```

### Worker count guidance

| vCPUs | RAM  | Recommended `WEB_CONCURRENCY` |
|-------|------|-------------------------------|
| 1     | 2 GB | 2                             |
| 2     | 4 GB | 3–4                           |
| 4     | 8 GB | 5–8                           |

Each worker holds one copy of the onnxruntime session in memory
(≈ 180 MB for u2net). On 4 GB RAM with 4 workers, expect ≈ 1.5 GB
model memory plus OS + app overhead.

---

## 3. API Usage

### Remove background

```bash
# With API key
curl -s -u ":your_api_key" \
     -F "file=@photo.jpg" \
     https://your.domain.com/v1/remove-background \
     -o result.png

# Without API key (when API_KEY is unset)
curl -s -F "file=@photo.jpg" \
     https://your.domain.com/v1/remove-background \
     -o result.png
```

### Health checks

```bash
curl https://your.domain.com/health
# {"status":"ok","uptime_seconds":42.1}

curl https://your.domain.com/ready
# {"ready":true,"model_loaded":true}
```

### HTTP status codes

| Code | Meaning |
|------|---------|
| 200  | Success — body is a transparent PNG |
| 400  | Bad image (wrong type, too large dimensions, magic bytes mismatch) |
| 401  | Missing or invalid API key |
| 413  | File too large (> MAX_FILE_SIZE) |
| 429  | Rate limit exceeded |
| 503  | Model not yet loaded (retry after a few seconds) |
| 500  | Unexpected server error |

---

## 4. Benchmarking

### Prerequisites

```bash
# Install hey (Go-based load tester)
go install github.com/rakyll/hey@latest
# or: apt install hey  (some distros)

# Or use wrk
apt install wrk

# Or Apache Bench
apt install apache2-utils
```

### Single-endpoint test

```bash
# hey: 100 requests, 10 concurrent
hey -n 100 -c 10 -m POST \
    -H "Authorization: Basic $(echo -n ':apikey' | base64)" \
    -F "file=@test.jpg" \
    https://your.domain.com/v1/remove-background

# wrk (multipart requires a pre-recorded body file)
# 1. Capture a multipart body:
curl -s -o /dev/null -D - -F "file=@test.jpg" http://127.0.0.1:8000/v1/remove-background \
  --trace-ascii /tmp/trace.txt

# ab: note ab doesn't handle multipart well; hey or wrk preferred
```

### Warm-up before benchmarking

Always send 5–10 warm-up requests first so any JIT effects in onnxruntime
are excluded from your numbers:

```bash
for i in {1..5}; do
  curl -s -o /dev/null -F "file=@test.jpg" \
       http://127.0.0.1:8000/v1/remove-background
done
```

---

## 5. Performance Tuning — CPU-only VPS

### 5.1 ONNX Runtime threading

By default, onnxruntime spawns threads equal to physical cores. On a
shared VPS, cap it to avoid contention:

```bash
# Set before starting gunicorn
export OMP_NUM_THREADS=2
export OMP_WAIT_POLICY=PASSIVE
export ONNXRUNTIME_INTRAOP_THREAD_AFFINITY="0,1"
```

### 5.2 Use a faster model

rembg ships several models with different speed/quality trade-offs:

| Model         | Quality | Speed (CPU) | RAM    |
|---------------|---------|-------------|--------|
| `u2net`       | Best    | Slow        | 175 MB |
| `u2netp`      | Good    | 3× faster   | 4 MB   |
| `isnet-general-use` | Excellent | Moderate | 180 MB |
| `birefnet-lite` | Great | Fast        | 50 MB  |

Set `REMBG_MODEL=u2netp` in `/etc/bgremove.env` for latency-sensitive
deployments.

### 5.3 PNG encoding

Setting `compress_level=1` in `processing.py` makes PNG encoding ~5×
faster than the default (level 6) at the cost of ~20% larger files.
For API use-cases this is almost always the right trade-off.

### 5.4 Input resizing (optional)

If your use-case tolerates it, resize inputs to ≤ 1024 px on the long
edge before inference — this is the single biggest speed lever:

```python
# Add to process_image_bytes() before rembg.remove()
MAX_SIDE = 1024
if max(input_image.size) > MAX_SIDE:
    input_image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
```

### 5.5 OS-level tuning

```bash
# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535

# Apply
sysctl -p
```

### 5.6 Memory swap

On 4 GB RAM with large images, add a 2 GB swapfile as a safety net:

```bash
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

---

## 6. Security Hardening Checklist

```
Infrastructure
  [x] Nginx terminates TLS (Let's Encrypt — auto-renewal via certbot.timer)
  [x] FastAPI bound to 127.0.0.1 only (not publicly reachable)
  [x] Dedicated unprivileged OS user (bgremove)
  [x] systemd ProtectSystem=strict, NoNewPrivileges=true
  [x] UFW / iptables: only ports 22, 80, 443 open

API layer
  [x] API key (Basic Auth) — set API_KEY in /etc/bgremove.env
  [x] Rate limiting: slowapi (app) + limit_req_zone (Nginx)
  [x] File size cap: MAX_FILE_SIZE (default 10 MB)
  [x] Magic-byte validation (not just MIME or extension)
  [x] Decompression-bomb guard: MAX_MEGAPIXELS + PIL header-only read
  [x] Maximum resolution check (MAX_IMAGE_WIDTH × MAX_IMAGE_HEIGHT)
  [x] No disk writes — all processing in memory
  [x] No directory traversal — no file system paths involved
  [x] Request timeout: Gunicorn worker_timeout + Nginx proxy_read_timeout
  [x] Structured JSON logs for SIEM ingestion

Headers
  [x] Strict-Transport-Security (HSTS)
  [x] X-Content-Type-Options: nosniff
  [x] X-Frame-Options: DENY
  [x] Cache-Control: no-store on responses

To do manually
  [ ] Enable fail2ban for repeated 401/429 responses
  [ ] Set up unattended-upgrades for security patches
  [ ] Configure logrotate for /var/log/nginx/bgremove_*.log
  [ ] Monitor with Prometheus / Grafana (add prometheus-fastapi-instrumentator)
  [ ] Set up uptime monitoring (BetterStack / UptimeRobot)
```

---

## 7. Reliability & Operations

### Graceful restart (zero-downtime deploy)

```bash
# Signal Gunicorn master to reload workers one-by-one
systemctl kill -s HUP bgremove

# Or by PID
kill -HUP $(cat /run/bgremove.pid)
```

### Log tailing

```bash
journalctl -u bgremove -f --output=json | jq .
```

### Model cache location

rembg downloads model weights to `~/.u2net` (i.e., `/opt/bgremove/.u2net`
for the bgremove user). Pre-download and commit to a known path to avoid
any first-start delay:

```bash
su -s /bin/bash bgremove -c \
  "python3 -c \"import rembg; rembg.new_session('u2net')\""
```

### Memory limits

Add to `bgremove.service` if you want hard memory protection on a shared VPS:

```ini
[Service]
MemoryMax=3G
MemorySwapMax=1G
```

### Automatic certificate renewal

Certbot installs a systemd timer automatically. Verify:

```bash
systemctl list-timers | grep certbot
```

---

## 8. Changelog / Versioning

The `/v1/` prefix in the endpoint URL follows API versioning best practice.
Future breaking changes → `/v2/remove-background`, old version kept alive
for a deprecation window.
