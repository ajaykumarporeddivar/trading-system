# Deploy to Railway - 24/7 Continuous Trading Engine

## Why Not Vercel?

Vercel is for **serverless functions** with 10-60 second timeouts. Your trading engine needs **continuous execution**.

**Railway.app** is the right choice - it runs persistent processes 24/7.

## Deploy to Railway (5 minutes)

### Step 1: Push to GitHub

`ash
cd D:\TRADING_SIGNAL\trading_system
git init
git add .
git commit -m "Initial commit: AI trading system"
git remote add origin https://github.com/YOUR_USERNAME/trading-system.git
git push -u origin main
`

### Step 2: Create Railway Project

1. Go to https://railway.app
2. Sign in with GitHub
3. Click **New Project** -> **Deploy from GitHub repo**
4. Select your 	rading-system repository
5. Railway auto-detects Python and installs requirements

### Step 3: Set Environment Variables

In Railway dashboard, click **Variables** and add:

| Variable | Value |
|----------|-------|
| EXCHANGE | binance |
| EXCHANGE_API_KEY | your_api_key |
| EXCHANGE_API_SECRET | your_api_secret |
| USE_TESTNET | true |
| TELEGRAM_BOT_TOKEN | your_bot_token |
| TELEGRAM_CHAT_ID | your_chat_id |
| EMAIL_USER | your_email@gmail.com |
| EMAIL_PASSWORD | your_app_password |
| ALERT_EMAIL | your_email@gmail.com |

### Step 4: Deploy

Railway auto-deploys. Your engine runs 24/7.

## How It Continuously Learns

1. **Arena generates trades** -> Each trade saved to orders/training_data.jsonl
2. **ML retrains hourly** -> ml/retrain_scheduler.py checks for new data every 3600s
3. **Model updates** -> New model saved to ml/models/trading_model.pkl
4. **Strategy adjusts** -> ml/strategy_updater.py analyzes agent performance
5. **Agents improve** -> Next cycle uses updated ML predictions

## Data Persistence

Railway provides persistent storage. All data survives restarts:
- orders/*.json - Agent positions
- orders/training_data.jsonl - ML training data
- ml/models/trading_model.pkl - Trained model
- 	rading_journal.db - SQLite database
- logs/*.json - System logs

## Monitoring

### Health Check
`ash
python monitor/health_check.py
`

### View Training Data
`ash
wc -l orders/training_data.jsonl
`

### Check Model Status
`ash
python -c "from ml.trainer import get_model_status; print(get_model_status())"
`

### Force ML Retrain
`ash
python -c "from ml.strategy_updater import StrategyUpdater; StrategyUpdater().retrain_and_update()"
`

## Cost

- **Railway Hobby**: /month (enough for this engine)
- **Binance Testnet**: Free
- **Telegram Alerts**: Free
- **Email Alerts**: Free (Gmail)

Total: **/month for 24/7 AI trading system**
