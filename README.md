Background Removal API — Production Deployment Guide (AWS + FastAPI)

High-performance background removal microservice built with FastAPI + rembg (ONNX Runtime).

Designed for:

AWS EC2 (Ubuntu 22.04)

Nginx reverse proxy

systemd process management

Production security hardening

Project Structure
backremove/
├── main.py                  # FastAPI entry point
├── app/                     # Modular app components
│   ├── config.py
│   ├── logger.py
│   ├── model.py
│   ├── security.py
│   └── processing.py
├── requirements.txt
├── bgremove.service         # systemd service
├── nginx.conf               # Reverse proxy config
├── .env.example
├── README.md
└── .gitignore


⚠️ Not committed to Git:

venv/

.env

*.pem

__pycache__/

1️⃣ Local Development
Create virtual environment
python -m venv venv


Activate:

Windows:

venv\Scripts\activate


Linux/macOS:

source venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Run dev server:

uvicorn main:app --reload


Open:

http://127.0.0.1:8000/docs

2️⃣ AWS EC2 Deployment (Ubuntu 22.04)
2.1 Connect to server
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP

2.2 Update system
sudo apt update && sudo apt upgrade -y


Install dependencies:

sudo apt install python3-pip python3-venv nginx git -y

2.3 Upload project

From your local machine:

scp -i your-key.pem -r backremove ubuntu@YOUR_PUBLIC_IP:/home/ubuntu/


Then SSH again.

2.4 Setup Python environment
cd backremove
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt


Pre-download model:

python3 -c "import rembg; rembg.new_session('u2net')"

3️⃣ Run in Production (Gunicorn)

Install gunicorn:

pip install gunicorn


Test:

gunicorn -w 3 -k uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 main:app

4️⃣ Setup systemd (Auto Start on Boot)

Copy service file:

sudo cp bgremove.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bgremove
sudo systemctl start bgremove


Check status:

sudo systemctl status bgremove

5️⃣ Nginx Reverse Proxy

Copy nginx config:

sudo cp nginx.conf /etc/nginx/sites-available/backremove


Edit domain:

sudo nano /etc/nginx/sites-available/backremove


Enable:

sudo ln -s /etc/nginx/sites-available/backremove /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

6️⃣ HTTPS (Let's Encrypt)

After DNS A record points to your EC2 IP:

sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com


Auto-renewal is handled by systemd timer.

7️⃣ Security Checklist

Infrastructure:

FastAPI bound to 127.0.0.1

Only ports 22, 80, 443 open

No public access to port 8000

Run under non-root user

systemd service protection enabled

API Layer:

API Key authentication

File size limits

Magic-byte validation

Decompression bomb guard

No disk writes (memory only)

Rate limiting

Headers:

HSTS

X-Frame-Options

X-Content-Type-Options

Cache-Control: no-store

8️⃣ Performance Optimization
Recommended EC2 instance

Minimum:

t3.medium (2 vCPU, 4GB RAM)

Worker guideline
vCPU	RAM	Workers
1	2GB	2
2	4GB	3–4
4	8GB	5–8
Faster Model Option

In .env:

REMBG_MODEL=u2netp


Faster but slightly lower quality.

9️⃣ API Usage
Remove Background
curl -F "file=@photo.jpg" \
https://yourdomain.com/v1/remove-background \
-o result.png


With API key:

curl -u ":YOUR_API_KEY" \
-F "file=@photo.jpg" \
https://yourdomain.com/v1/remove-background \
-o result.png

🔟 Health Checks
GET /health
GET /ready

11️⃣ Monitoring & Logs

View logs:

journalctl -u bgremove -f

12️⃣ Benchmarking

Install hey:

sudo apt install hey


Run test:

hey -n 100 -c 10 -m POST \
-F "file=@test.jpg" \
https://yourdomain.com/v1/remove-background

13️⃣ Zero-Downtime Restart
sudo systemctl reload bgremove

Versioning Strategy

Endpoints are versioned:

/v1/remove-background


Future breaking changes → /v2/

Important Security Note

Never commit:

.env

.pem

venv/

If private key was exposed:

Delete EC2 keypair

Create new key

Restart instance access

License

Private project — internal use only.