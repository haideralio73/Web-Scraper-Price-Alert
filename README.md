# Price Tracker — Web Scraper + Email Alert System

Scrapes product prices, stores them in **SQLite**, and sends **Gmail alerts** when prices drop below your target.

## Features

- `add` — scrape any product page, extract name + price, store in DB
- `list` — show all tracked products in a formatted table
- `check` — re-scrape every product and compare against target price
- `history` — view timestamped price history for any product
- `remove` — delete a product from tracking
- `serve` — run the scheduler (checks every N hours automatically)
- HTML email alerts with price, savings, and product link

## Requirements

- Python 3.10+
- Gmail account with [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification enabled)

## Quick Start

### 1. Setup

```bash
# Clone or download the project, then install dependencies
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env
```

Edit `.env` with your Gmail credentials:

```
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=your-16-character-app-password
ALERT_RECIPIENT=your.email@gmail.com
```

### 2. Track a product

```bash
python main.py add https://example.com/product 25.00
```

Scrapes the page, extracts the price, stores it. Alerts will fire when the price drops to £25.00 or below.

### 3. Check prices

```bash
python main.py check
```

Scrapes all tracked products. If any price is at or below target, sends an email alert and deactivates that product.

### 4. Run scheduled mode (every 6 hours)

```bash
python main.py serve
```

### Other commands

```bash
python main.py list                   # show tracked products
python main.py history 1              # price history for product ID 1
python main.py remove 1               # remove product ID 1
```

## Which files to upload to GitHub

Drag and drop these **files and folders** into your GitHub repository:

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point + scheduler |
| `scraper.py` | Web scraping with requests + BeautifulSoup |
| `database.py` | SQLite database operations |
| `email_alert.py` | Gmail SMTP email alerts |
| `config.py` | Environment variable loader |
| `requirements.txt` | Python dependencies |
| `render.yaml` | Render.com deployment config |
| `.gitignore` | Ignores `*.db`, `.env`, `__pycache__` |
| `.env.example` | Credential template (safe to share) |
| `README.md` | This file |

**Do NOT upload** `.env` (contains secrets) or `*.db` files — they're already in `.gitignore`.

## Deploy to Render.com

1. Push to GitHub
2. In Render.com dashboard → **New +** → **Background Worker**
3. Connect your repository
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `python main.py serve`
6. Add environment variables: `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `ALERT_RECIPIENT`
7. Deploy

The worker will run 24/7 and check prices every 6 hours.
