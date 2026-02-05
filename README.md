# Polymarket Stop-Loss Bot

Automated stop-loss monitoring for Polymarket positions. Closes positions at market price when they drop below a configurable threshold.

> *Built for personal use.*

## Features

- Monitors open positions via Polymarket Data API
- Auto-executes stop-loss at configurable percentage
- Telegram notifications (new position, stop-loss triggered, market resolved)
- Trade history logging to Turso database
- Rotating file logs

## Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. **Run the bot**
   ```bash
   python main.py
   ```

## Configuration

Edit `config.yaml`:
```yaml
stop_loss:
  percentage: 10.0  # Trigger at 10% loss
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `POLYMARKET_WALLET_PRIVATE_KEY` | Your wallet private key (required for signing orders) |
| `POLYMARKET_FUNDER_ADDRESS` | Your Polymarket proxy wallet address |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/group ID |
| `TURSO_DATABASE_URL` | Turso database URL |
| `TURSO_AUTH_TOKEN` | Turso auth token |

## Security Note

Use a dedicated wallet with limited funds. The private key is required to sign each trade order - there's no API-only trading option on Polymarket.
