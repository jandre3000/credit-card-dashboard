---
title: Credit Card Dashboard
tags: [finance, credit-cards, dashboard, web-app]
updated: 2026-10-08
---

# Credit Card Dashboard

Web application for parsing Amex Cobalt statements, tracking spending, and visualizing points.

## Quick Start (Docker)

```bash
cd /opt/data/projects/credit-card-dashboard
docker build -t credit-cards-dashboard .
docker run -d --name credit-cards -p 8501:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/statements:/app/statements \
  credit-cards-dashboard
```

Open http://localhost:8501

## Quick Start (Local)

```bash
cd /opt/data/projects/credit-card-dashboard
uv venv .venv --python python3
uv pip install --python .venv/bin/python3 -r app/requirements.txt
DB_PATH=$(pwd)/data/credit_cards.db STATEMENTS_DIR=$(pwd)/statements \
  .venv/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8501 --app-dir app
```

## Features

- **Upload** Amex Cobalt statement PDFs via web UI
- **Parse** transactions automatically with points categories
- **View** original PDFs in-browser
- **Line chart** with zoom/pan (scroll wheel + drag):
  - Total daily spending
  - Per category (5x food, 3x streaming, 2x gas, 1x other)
  - Per vendor (top 15)
  - Points over time (with cumulative line)
- **Transaction table** with all details
- **Date range filtering**
- **Statement management** (view, delete)

## Points Categories (Amex Cobalt)

| Rate | Category | Examples |
|---|---|---|
| 5x | Eligible Food/Drink | Restaurants, grocery, delivery |
| 3x | Eligible Streaming | Apple, Spotify, Amazon Prime |
| 2x | Eligible Gas/Transit/Ride Share | Gas stations, Uber trips |
| 1x | All Other Purchases | Everything else |

## API Endpoints

- `GET /` — Dashboard UI
- `POST /api/upload` — Upload statement PDF
- `GET /api/transactions` — List transactions (filter: start, end, card, category, vendor)
- `GET /api/spending/daily` — Daily spending totals
- `GET /api/spending/category` — Spending by points category
- `GET /api/spending/vendor` — Spending by vendor (top 15)
- `GET /api/points` — Points earned over time
- `GET /api/statements` — List uploaded statements
- `DELETE /api/statements/{id}` — Delete statement
- `GET /api/pdf/{filename}` — View original PDF
- `GET /api/health` — Health check

## Project Structure

```
credit-card-dashboard/
├── Dockerfile
├── docker-compose.yml
├── README.md
├── app/
│   ├── main.py          # FastAPI application
│   ├── database.py      # SQLite layer
│   ├── parser.py        # Amex Cobalt statement parser
│   ├── requirements.txt
│   ├── templates/
│   │   └── index.html   # Dashboard UI
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── data/                # SQLite database (mounted volume)
└── statements/          # Uploaded PDFs (mounted volume)
```

## Related

- Card knowledge base (benefits, insurance, transfer partners): `../credit-cards/`