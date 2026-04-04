# 24/7 Production Deployment Guide
**System:** Institutional Trading Loop V11 
**Requirement:** 24/7 Continuous Lifecycle via `run_247.py` and `web/app.py`

Deploying an autonomous ML-driven system trading real capital requires strict environmental constraints. Because this engine manages *stateful* json files, trains ML models on disk, and relies on asynchronous continuous looping, you **cannot use Serverless platforms (like Vercel, Netlify, or AWS Lambda)**. Serverless environments timeout within seconds and delete the disk after every run.

Below are the **two best operational environments** to run the V11 engine 24 hours a day, 7 days a week.

---

## 🏗️ Architecture Constraints to Know
1. **Persistent Storage requirement**: The ML models dynamically re-save to `ml/models/trading_model.pkl`. Trade logs accumulate in `orders/training_data.jsonl`. Without persistent file storage, your AI will have "amnesia" every time the application restarts.
2. **Dual-Thread Need**: You are running two environments:
   - *Worker Service*: `python run_247.py` (The brain).
   - *Web Service*: `python web/app.py` (The dashboard).

---

## Method A: Cloud PaaS (Railway.app)
*Best for hands-off server management, automatic GitHub deployments, and integrated logging.*

Railway is an infrastructure environment that can operate background `worker` processes unlike Serverless web nodes.

### Step-by-Step Setup:
1. **Connect GitHub**: Import your `trading-system` repository on Railway.app.
2. **Provision The Volume (CRITICAL)**: 
   - By default, Railway restarts and wipes the local directory on every Git Push. You **must** attach a persistent Volume to protect the agent's tracking.
   - Go to `Settings -> Volumes -> Add Volume`. Mount this volume to your project's root directory: `/app` or specifically map out directories `/app/orders`, `/app/ml/models`, and `/app/logs`.
3. **Configure Environment Variables**:
   - In the `Variables` tab, upload all configurations from your local `.env` (Exchange API Keys, Telegram IDs, `MIN_CONFIDENCE`, etc).
4. **Configure Services**:
   - For the **Trading Engine**: Under `Settings -> Deploy / Start Command`, explicitly override the command to: `python run_247.py`
   - *(Optional)* For the **Dashboard**: Spin up a second identical Railway Service pointing to the same Repo and Volume, but set the Start Command to `gunicorn web.app:app` (ensure Gunicorn is in `requirements.txt`).

---

## Method B: Bare-Metal VPS (DigitalOcean Droplet / AWS EC2 / GCP)
*Best for lowest execution latency to binance endpoints, maximum privacy, and granular OS-level process restarts.*

Operating an Ubuntu Linux VM gives you 100% control and zeroes out the threat of ephemeral volumes destroying your ML data.

### Step-by-Step Setup:

**1. Initial Server Setup**
SSH into your Linux machine, update packages, and pull your codebase natively.
```bash
sudo apt update && sudo apt install python3.12-venv git -y
git clone https://github.com/YOUR_GIT/trading-system.git
cd trading-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Setup `systemd` Services**
You should NOT use traditional tools like Docker or Tmux for the engine because they hide internal kernel crashes. Instead, register the engine directly to the operating system using `systemd`. This ensures the OS automatically boots it on a server restart.

**Create the Engine Service:**
```bash
sudo nano /etc/systemd/system/trading-engine.service
```
Insert the Daemon configuration:
```ini
[Unit]
Description=V11 Trading Engine Worker
After=network.target

[Service]
User=root
WorkingDirectory=/root/trading-system
Environment="PATH=/root/trading-system/venv/bin"
ExecStart=/root/trading-system/venv/bin/python run_247.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

**Create the Dashboard Service:**
```bash
sudo nano /etc/systemd/system/trading-dashboard.service
```
```ini
[Unit]
Description=V11 Web Dashboard
After=network.target

[Service]
User=root
WorkingDirectory=/root/trading-system
Environment="PATH=/root/trading-system/venv/bin"
ExecStart=/root/trading-system/venv/bin/gunicorn -w 1 -b 0.0.0.0:80 web.app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**3. Launch System**
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-engine
sudo systemctl enable trading-dashboard
sudo systemctl start trading-engine
sudo systemctl start trading-dashboard
```

---

## 🚨 Ongoing 24/7 Monitoring Protocol

Once the system is live, follow these monitoring invariants:
1. **The Crash Log Cache**: `run_247.py` has internal crash protection. Always monitor `logs/crash_log.jsonl`. An increasing file size indicates an internal logical fault failing over repeatedly.
2. **Watch the Telegram/SMTP Pipeline**: Let the bot contact you. Do not constantly SSH in to view positions. Ensure the `core/execution_logger.py` hooks successfully trigger your defined Telegram chat ID as your primary heartbeat monitor.
3. **Routine Vacuum**: Running 24/7 means database sizes grow forever. Approximately once a month, you must extract `trading_journal.db` and the continuous `logs/` arrays to cold storage or risk memory leak constraints when python loops accumulate too much JSON history over standard limits.
