# Miner Dashboard

Real-time dashboard for monitoring precog subnet miners performance.

## Features

- ✅ Multi-miner support (miner1, miner2)
- ✅ Performance metrics (MAPE, MAE, RMSE, Bias, Coverage)
- ✅ Individual asset charts (BTC, ETH, TAO) with predictions, intervals, and actual prices
- ✅ Prediction trends visualization
- ✅ Latest predictions feed
- ✅ Manual price fetching from crypto APIs
- ✅ MongoDB storage for actual prices (fast lookups)

## Architecture

```
CSV Files (predictions) → Backend API → Frontend Dashboard
                              ↓
                    MongoDB (actual prices)
                              ↓
                    Crypto APIs (on-demand fetch)
```

### Why We Need a Backend

The frontend (Next.js) runs in the browser and **cannot**:
- ❌ Read local CSV files (browser security)
- ❌ Connect to MongoDB directly (no DB access from browser)
- ❌ Call crypto APIs directly (CORS, rate limits, API keys)

The backend **provides**:
- ✅ File system access (read CSV files)
- ✅ Database access (MongoDB queries)
- ✅ API integration (crypto price APIs)
- ✅ Metrics calculation (MAPE, MAE, RMSE, etc.)
- ✅ REST API endpoints (for frontend)

## Setup

### Backend Setup

1. Install Python dependencies:
```bash
cd /home/cipher/github_repo/miner_dashboard
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure environment:
```bash
# Edit .env file with MongoDB connection (optional - dashboard works without it)
# MongoDB is used for caching actual prices for fast lookups
```

3. Run backend:
```bash
python -m backend.main
# Or with uvicorn directly:
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Run development server:
```bash
npm run dev
```

3. Open browser:
```
http://localhost:3000
```

## Configuration

Edit `.env` file to configure:

- `MINER_DATA_DIR` - Path to miner CSV files (default: `./miner`)
- `MONGODB_URI` - MongoDB connection string (optional)
- `MONGODB_DB_NAME` - MongoDB database name (default: `miner_dashboard`)
- `DASHBOARD_HOST` - Backend host (default: `0.0.0.0`)
- `DASHBOARD_PORT` - Backend port (default: `8000`)

## API Endpoints

### Essential Endpoints
- `GET /api/health` - Health check
- `GET /api/miners` - List all miners
- `GET /api/miners/{miner_name}/stats` - Get miner statistics
- `GET /api/miners/{miner_name}/asset/{asset_name}` - Get asset chart data (predictions + actuals + metrics)
- `POST /api/fetch-data` - Fetch actual prices from crypto APIs and save to MongoDB

### Additional Endpoints
- `GET /api/miners/{miner_name}/predictions` - Get latest predictions
- `GET /api/miners/{miner_name}/data` - Get raw data
- `WS /ws` - WebSocket for real-time updates (optional)

## Development

### Backend Structure

```
backend/
├── main.py              # FastAPI application (REST API endpoints)
├── config.py            # Configuration management
├── csv_parser.py        # CSV parser (read predictions from CSV)
├── metrics.py           # Metrics calculator (MAPE, MAE, RMSE, etc.)
├── price_fetcher.py     # Fetch actual prices from crypto APIs
├── price_database.py    # MongoDB operations for price storage
├── file_watcher.py      # CSV file watcher (optional, for real-time updates)
└── data_manager.py      # In-memory data management
```

### Frontend Structure

```
frontend/
├── app/
│   ├── page.tsx     # Main dashboard page
│   └── layout.tsx   # Root layout
├── components/
│   ├── MinerSelector.tsx
│   ├── StatsCards.tsx
│   ├── PredictionChart.tsx
│   └── LatestPredictions.tsx
└── hooks/
    ├── useWebSocket.ts
    └── useMinerStats.ts
```

## Troubleshooting

### Dashboard Not Loading

- Check backend is running: `curl http://localhost:8000/api/health`
- Verify CSV files exist in `miner/` directory
- Check browser console for errors

### No Actual Prices in Charts

- Click "Fetch Data" button to fetch prices from APIs
- Prices are cached in MongoDB for fast lookups
- Only predictions with evaluation time in the past will have actual prices

### MongoDB Connection Issues

- Dashboard works without MongoDB (prices won't be cached)
- If MongoDB is unavailable, prices will be fetched from APIs each time
- Check MongoDB connection string in `.env`

### WebSocket Disconnection

- WebSocket is optional - dashboard works without it
- Check backend is running on port 8000
- Verify CORS settings in `config.py`

## How It Works

1. **Read Predictions**: Backend reads CSV files from `miner/` directory
2. **Fetch Prices**: Click "Fetch Data" button to fetch actual prices from crypto APIs
3. **Store in MongoDB**: Prices are cached in MongoDB for fast lookups
4. **Display Charts**: Frontend displays predictions, intervals, and actual prices with metrics

## Data Flow

1. Miner generates predictions → Saved to CSV files
2. User clicks "Fetch Data" → Backend reads CSV, checks MongoDB for existing prices
3. Missing prices → Fetched from crypto APIs (CryptoCompare, Binance, CoinMetrics)
4. Prices saved → Stored in MongoDB with 5-minute precision
5. Frontend requests → Backend reads CSV + MongoDB → Returns combined data
6. Charts display → Predictions, intervals, actual prices, and metrics

