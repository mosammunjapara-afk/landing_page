# AutoBid Pro — Car Dealer Platform

## Tech Stack
- **Backend**: Python 3 + Flask
- **Database**: SQLite (auto-created on first run)
- **Frontend**: HTML + CSS (no framework)

## Pages
| Page | URL | Purpose |
|------|-----|---------|
| Landing | `/` | Marketing + CTA |
| Signup | `/signup` | Create dealer account |
| Login | `/login` | Dealer login |
| Onboarding | `/onboarding?step=1..4` | 4-step verification |
| Dashboard | `/dashboard` | Browse, bid, track |

## Setup & Run

```bash
# 1. Install dependency
pip install flask

# 2. Run the app
cd cardealership
python app.py
```

Open http://localhost:5000

## Database Tables
- **dealers** — dealer accounts + KYC + bank
- **cars** — pre-owned car inventory (seeded with 6 cars)
- **bids** — all bid records
- **orders** — won auctions / purchases

## API Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/bid` | Place a bid (JSON) |
| GET  | `/api/cars` | Get filtered car list |

## Flow
Landing → Signup → Onboarding (4 steps) → Dashboard → Bid → Order
