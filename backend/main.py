"""Main FastAPI application."""
import asyncio
import logging
from typing import Dict, List
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
import pandas as pd
import numpy as np
from datetime import timedelta, datetime, timezone
from typing import Optional

from backend.config import Config
from backend.file_watcher import FileWatcher
from backend.data_manager import DataManager
from backend.csv_parser import CSVParser
from backend.metrics import MetricsCalculator
from backend.price_fetcher import PriceFetcher
from backend.price_csv_loader import PriceCSVLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Miner Dashboard API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global data manager
data_manager = DataManager()

# WebSocket connections
active_connections: List[WebSocket] = []

# File watchers
file_watchers: Dict[str, FileWatcher] = {}


def serialize_for_json(obj):
    """Recursively serialize objects for JSON."""
    if isinstance(obj, (pd.Timestamp, pd.DatetimeTZType)):
        return obj.isoformat()
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict('records')
    elif isinstance(obj, (np.integer, np.floating)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif pd.isna(obj):
        return None
    else:
        return obj


async def broadcast_update(miner_name: str, data):
    """Broadcast update to all WebSocket connections."""
    if not active_connections:
        return
    
    try:
        message = {
            'type': 'update',
            'miner': miner_name,
            'data': serialize_for_json(data),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Verify JSON serializable
        import json
        json.dumps(message)  # Will raise if not serializable
        
        # Send to all connections
        disconnected = []
        for connection in active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            if conn in active_connections:
                active_connections.remove(conn)
                
    except Exception as e:
        logger.error(f"Error broadcasting update: {e}")


async def on_file_update(miner_name: str, new_data):
    """Callback when file is updated."""
    await data_manager.update_miner_data(miner_name, new_data)
    await broadcast_update(miner_name, new_data)


@app.on_event("startup")
async def startup_event():
    """Initialize file watchers on startup."""
    logger.info("Starting dashboard backend...")
    
    # Discover miners from file system
    all_miners = Config.get_all_miners()
    logger.info(f"🔍 Discovered {len(all_miners)} miner(s): {', '.join(all_miners.keys())}")
    
    # Load prices from CSV files into memory cache
    try:
        logger.info("Loading prices from CSV files into memory cache...")
        results = await PriceCSVLoader.load_prices()
        total_loaded = sum(results.values())
        logger.info(f"✅ Loaded {total_loaded} prices from CSV files into memory cache")
    except Exception as e:
        logger.warning(f"Error loading prices from CSV: {e}")
    
    # Create file watchers for each discovered miner
    for miner_name in all_miners.keys():
        logger.info(f"Initializing file watcher for {miner_name}...")
        watcher = FileWatcher(miner_name, on_file_update)
        file_watchers[miner_name] = watcher
        # Optionally start watching (for real-time updates)
        # await watcher.start()
    
    logger.info("✅ Dashboard backend started (reading from local CSV files)")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down dashboard backend...")
    
    # Stop all file watchers
    for watcher in file_watchers.values():
        await watcher.stop()
    
    # Close all WebSocket connections
    for connection in active_connections:
        try:
            await connection.close()
        except Exception:
            pass
    
    logger.info("✅ Dashboard backend stopped")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Miner Dashboard API", "version": "1.0.0"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    # Dynamically discover miners
    all_miners = Config.get_all_miners()
    return {"status": "healthy", "miners": list(all_miners.keys())}


def _read_miner_csv(miner_name: str) -> pd.DataFrame:
    """Read CSV file for a miner."""
    csv_path = Path(Config.get_miner_csv_path(miner_name))
    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(csv_path)
        # Parse timestamp columns
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        return df
    except Exception as e:
        logger.error(f"Error reading CSV for {miner_name}: {e}")
        return pd.DataFrame()


@app.get("/api/miners")
async def get_miners():
    """
    Get list of all miners.
    Dynamically discovers miners from the file system on each request.
    """
    # Dynamically discover miners from file system
    all_miners = Config.get_all_miners()
    
    return {
        "miners": [
            {"name": name, "display_name": display}
            for name, display in sorted(all_miners.items())
        ]
    }


@app.get("/api/miners/{miner_name}/stats")
async def get_miner_stats(miner_name: str):
    """Get statistics for a miner."""
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read CSV file
    df = _read_miner_csv(miner_name)
    
    if df.empty:
        return {
            "miner_name": miner_name,
            "total_predictions": 0,
            "assets": [],
            "latest_prediction_time": None,
        }
    
    # Calculate stats
    assets = CSVParser.detect_assets(df)
    latest_time = None
    if 'timestamp' in df.columns:
        latest_time = df['timestamp'].max()
    elif 'datetime' in df.columns:
        latest_time = df['datetime'].max()
    
    return {
        "miner_name": miner_name,
        "total_predictions": len(df),
        "assets": assets,
        "latest_prediction_time": latest_time.isoformat() if latest_time else None,
    }


@app.get("/api/miners/{miner_name}/predictions")
async def get_predictions(miner_name: str, limit: int = 50):
    """Get latest predictions for a miner.
    
    Groups predictions by timestamp and returns only one prediction per timestamp.
    This is needed because miners handle up to 5 requests concurrently, resulting
    in multiple predictions at the same timestamp.
    """
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read CSV file
    df = _read_miner_csv(miner_name)
    
    if df.empty:
        return {"predictions": []}
    
    # Group by timestamp first, then get latest unique timestamps
    timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
    if timestamp_col not in df.columns:
        # Fallback: just get latest predictions without grouping
        predictions = CSVParser.get_latest_predictions(df, limit=limit)
        return {"predictions": predictions}
    
    # Group by timestamp and take the first row for each timestamp
    # This handles the case where up to 5 predictions exist per timestamp
    df_grouped = df.groupby(timestamp_col).first().reset_index()
    
    # Sort by timestamp (most recent first)
    df_sorted = df_grouped.sort_values(timestamp_col, ascending=False)
    
    # Get latest N unique timestamps
    df_latest = df_sorted.head(limit)
    
    # Convert to list of dicts
    predictions = []
    assets = CSVParser.detect_assets(df)
    
    for _, row in df_latest.iterrows():
        pred_data = {
            'timestamp': row.get('timestamp', row.get('datetime', '')),
            'datetime': str(row.get('datetime', '')),
            'validator_hotkey': row.get('validator_hotkey', ''),
            'assets': row.get('assets', ''),
            'processing_time_seconds': row.get('processing_time_seconds', 0),
        }
        
        # Add predictions for each asset
        for asset in assets:
            pred_col = f"{asset}_prediction"
            raw_col = f"{asset}_raw_prediction"
            lower_col = f"{asset}_interval_lower"
            upper_col = f"{asset}_interval_upper"
            
            if pred_col in row:
                pred_data[f"{asset}_prediction"] = float(row[pred_col]) if pd.notna(row[pred_col]) else None
            if raw_col in row:
                pred_data[f"{asset}_raw_prediction"] = float(row[raw_col]) if pd.notna(row[raw_col]) else None
            if lower_col in row:
                pred_data[f"{asset}_interval_lower"] = float(row[lower_col]) if pd.notna(row[lower_col]) else None
            if upper_col in row:
                pred_data[f"{asset}_interval_upper"] = float(row[upper_col]) if pd.notna(row[upper_col]) else None
        
        predictions.append(pred_data)
    
    return {"predictions": predictions}


@app.get("/api/miners/{miner_name}/incentives")
async def get_miner_incentives(miner_name: str, limit: int = 50):
    """Get incentive history for a specific miner."""
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read incentive CSV file
    df = _read_miner_incentive_csv(miner_name)
    
    if df.empty:
        return {"incentives": []}
    
    timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
    if timestamp_col not in df.columns:
        return {"incentives": []}
    
    # Get unique incentive values per timestamp to show more data points
    # Group by timestamp and get all unique incentive values, sorted
    grouped = df.groupby(timestamp_col)['incentive'].apply(lambda x: sorted(x.unique(), reverse=True)).reset_index()
    grouped = grouped.sort_values(timestamp_col, ascending=False).head(limit)
    
    # Convert to list of dicts - create a point for each unique incentive value
    incentives = []
    for _, row in grouped.iterrows():
        timestamp = row[timestamp_col]
        if pd.isna(timestamp):
            continue
        
        # Convert to ISO format
        if isinstance(timestamp, pd.Timestamp):
            timestamp_str = timestamp.isoformat()
        else:
            try:
                ts = pd.to_datetime(timestamp, utc=True)
                timestamp_str = ts.isoformat()
            except:
                continue
        
        # Add a point for each unique incentive value at this timestamp
        unique_incentives = row['incentive']
        if isinstance(unique_incentives, (list, pd.Series)):
            for incentive in unique_incentives:
                if pd.notna(incentive):
                    incentives.append({
                        'timestamp': timestamp_str,
                        'datetime': timestamp_str,
                        'incentive': float(incentive)
                    })
        else:
            if pd.notna(unique_incentives):
                incentives.append({
                    'timestamp': timestamp_str,
                    'datetime': timestamp_str,
                    'incentive': float(unique_incentives)
                })
    
    # Sort by timestamp (ascending - oldest to newest), then by incentive (descending) to show highest values first
    # Convert timestamp to datetime for proper sorting
    def sort_key(x):
        try:
            ts = pd.to_datetime(x['timestamp'], utc=True)
            return (ts, -x['incentive'])
        except:
            return (x['timestamp'], -x['incentive'])
    
    incentives.sort(key=sort_key)
    
    # Limit to requested number (take the most recent N)
    incentives = incentives[-limit:]
    
    # Return in oldest-to-newest order for proper timeline display
    return {"incentives": incentives}


@app.get("/api/miners/{miner_name}/trust")
async def get_miner_trust(miner_name: str, limit: int = 50):
    """Get trust history for a specific miner."""
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read incentive CSV file (which contains trust data)
    df = _read_miner_incentive_csv(miner_name)
    
    if df.empty:
        return {"trust": []}
    
    timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
    if timestamp_col not in df.columns:
        return {"trust": []}
    
    if 'trust' not in df.columns:
        return {"trust": []}
    
    # Get unique trust values per timestamp to show more data points
    # Group by timestamp and get all unique trust values, sorted
    grouped = df.groupby(timestamp_col)['trust'].apply(lambda x: sorted(x.unique(), reverse=True)).reset_index()
    grouped = grouped.sort_values(timestamp_col, ascending=False).head(limit)
    
    # Convert to list of dicts - create a point for each unique trust value
    trust_data = []
    for _, row in grouped.iterrows():
        timestamp = row[timestamp_col]
        if pd.isna(timestamp):
            continue
        
        # Convert to ISO format
        if isinstance(timestamp, pd.Timestamp):
            timestamp_str = timestamp.isoformat()
        else:
            try:
                ts = pd.to_datetime(timestamp, utc=True)
                timestamp_str = ts.isoformat()
            except:
                continue
        
        # Add a point for each unique trust value at this timestamp
        unique_trust = row['trust']
        if isinstance(unique_trust, (list, pd.Series)):
            for trust in unique_trust:
                if pd.notna(trust):
                    trust_data.append({
                        'timestamp': timestamp_str,
                        'datetime': timestamp_str,
                        'trust': float(trust)
                    })
        else:
            if pd.notna(unique_trust):
                trust_data.append({
                    'timestamp': timestamp_str,
                    'datetime': timestamp_str,
                    'trust': float(unique_trust)
                })
    
    # Sort by timestamp (ascending - oldest to newest), then by trust (descending) to show highest values first
    def sort_key(x):
        try:
            ts = pd.to_datetime(x['timestamp'], utc=True)
            return (ts, -x['trust'])
        except:
            return (x['timestamp'], -x['trust'])
    
    trust_data.sort(key=sort_key)
    
    # Limit to requested number (take the most recent N)
    trust_data = trust_data[-limit:]
    
    # Return in oldest-to-newest order for proper timeline display
    return {"trust": trust_data}


@app.get("/api/miners/{miner_name}/data")
async def get_miner_data(miner_name: str):
    """Get all data for a miner."""
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read CSV file
    df = _read_miner_csv(miner_name)
    
    if df.empty:
        return {"data": []}
    
    # Convert to dict
    data = df.to_dict('records')
    
    return {"data": serialize_for_json(data)}


def _read_miner_incentive_csv(miner_name: str) -> pd.DataFrame:
    """Read incentive history CSV file for a miner."""
    project_root = Path(__file__).parent.parent
    # Try my_incentive_history.csv first, fallback to incentive_history.csv
    csv_path = project_root / Config.MINER_DATA_DIR / miner_name / "my_incentive_history.csv"
    if not csv_path.exists():
        # Fallback to the old filename
        csv_path = project_root / Config.MINER_DATA_DIR / miner_name / "incentive_history.csv"
        if not csv_path.exists():
            logger.warning(f"Incentive CSV file not found: {csv_path}")
            return pd.DataFrame()
    
    try:
        df = pd.read_csv(csv_path)
        # Parse timestamp columns
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
        return df
    except Exception as e:
        logger.error(f"Error reading incentive CSV for {miner_name}: {e}")
        return pd.DataFrame()


@app.get("/api/miners/incentives")
async def get_all_miners_incentives(limit: int = 50):
    """Get incentive history for all miners, aggregated by timestamp."""
    all_miners = Config.get_all_miners()
    
    # Step 1: Collect all data points from all miners
    all_miner_data: Dict[str, List[Dict]] = {}  # miner_name -> list of {timestamp, incentive}
    
    for miner_name in all_miners.keys():
        df = _read_miner_incentive_csv(miner_name)
        
        if df.empty:
            continue
        
        timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
        if timestamp_col not in df.columns:
            continue
        
        # Group by timestamp and get max incentive per timestamp
        grouped = df.groupby(timestamp_col)['incentive'].max().reset_index()
        grouped = grouped.sort_values(timestamp_col, ascending=False)
        
        miner_data = []
        for _, row in grouped.iterrows():
            timestamp = row[timestamp_col]
            if pd.isna(timestamp):
                continue
            
            # Convert to datetime if needed
            if isinstance(timestamp, pd.Timestamp):
                ts = timestamp
            else:
                try:
                    ts = pd.to_datetime(timestamp, utc=True)
                except:
                    continue
            
            incentive = row['incentive']
            if pd.notna(incentive):
                miner_data.append({
                    'timestamp': ts,
                    'incentive': float(incentive)
                })
        
        if miner_data:
            all_miner_data[miner_name] = miner_data
    
    if not all_miner_data:
        return {"data": [], "miners": list(all_miners.keys())}
    
    # Step 2: Collect all unique timestamps and normalize to nearest 5 seconds
    all_timestamps = set()
    for miner_data in all_miner_data.values():
        for point in miner_data:
            ts = point['timestamp']
            # Round to nearest 5 seconds
            seconds = ts.second
            rounded_seconds = (seconds // 5) * 5
            normalized_ts = ts.replace(second=rounded_seconds, microsecond=0)
            all_timestamps.add(normalized_ts)
    
    # Step 3: For each normalized timestamp, find closest data from each miner (within 10 seconds)
    sorted_timestamps = sorted(all_timestamps)
    recent_timestamps = sorted_timestamps[-limit:] if len(sorted_timestamps) > limit else sorted_timestamps
    
    chart_data = []
    for normalized_ts in recent_timestamps:
        point: Dict[str, any] = {
            'timestamp': normalized_ts.isoformat(),
            'time': normalized_ts.isoformat()
        }
        
        # For each miner, find the closest data point within 10 seconds
        for miner_name in all_miners.keys():
            if miner_name not in all_miner_data:
                continue
            
            miner_data = all_miner_data[miner_name]
            best_match = None
            min_diff_seconds = 10.0  # 10 second window
            
            for data_point in miner_data:
                ts = data_point['timestamp']
                diff_seconds = abs((ts - normalized_ts).total_seconds())
                if diff_seconds < min_diff_seconds:
                    min_diff_seconds = diff_seconds
                    best_match = data_point
            
            if best_match:
                point[miner_name] = best_match['incentive']
        
        chart_data.append(point)
    
    return {
        "data": chart_data,
        "miners": list(all_miners.keys())
    }


class FetchDataRequest(BaseModel):
    miner_name: Optional[str] = None
    fetch_prices: bool = True


@app.post("/api/fetch-data")
async def fetch_data(request: FetchDataRequest):
    """
    Load actual prices from CSV files for predictions in CSV files.
    
    Fetch Period Logic:
    1. Reads all predictions from CSV files
    2. Calculates evaluation time for each (prediction_time + 1 hour)
    3. Loads prices from CSV files (using in-memory cache) for predictions that have passed evaluation time
    4. Reports the time range of predictions being processed
    """
    results = {}
    # Dynamically discover miners
    all_miners = Config.get_all_miners()
    miners_to_fetch = [request.miner_name] if request.miner_name else list(all_miners.keys())
    
    # Load actual prices from CSV files
    if request.fetch_prices:
        now = datetime.now(timezone.utc)
        
        # STEP 1: Collect all unique evaluation times across ALL miners
        # This allows us to share prices between miners and batch fetch
        all_eval_times_by_asset = {}  # {asset: set(eval_times)} - shared across miners
        miner_eval_times = {}  # {miner: {asset: [eval_times]}} - per miner tracking
        
        for miner in miners_to_fetch:
            if miner not in all_miners:
                results[miner] = {"success": False, "error": "Miner not found"}
                continue
            
            # Read CSV to get predictions
            df = _read_miner_csv(miner)
            if df.empty:
                results[miner] = {"success": False, "error": "No data in CSV file"}
                continue
            
            csv_assets = CSVParser.detect_assets(df)
            
            # Map CSV asset names to API asset names
            api_asset_map = {
                'btc': 'btc',
                'eth': 'eth',
                'tao_bittensor': 'tao',
                'tao': 'tao',
            }
            
            # Collect evaluation times for this miner
            miner_eval_times[miner] = {}
            future_count = 0
            
            for csv_asset in csv_assets:
                api_asset = api_asset_map.get(csv_asset.lower(), csv_asset.lower())
                if api_asset not in all_eval_times_by_asset:
                    all_eval_times_by_asset[api_asset] = set()
                if api_asset not in miner_eval_times[miner]:
                    miner_eval_times[miner][api_asset] = []
            
            # Collect all evaluation times from this miner
            for _, row in df.iterrows():
                timestamp = row.get('timestamp') or row.get('datetime')
                if not timestamp:
                    continue
                
                if isinstance(timestamp, str):
                    pred_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                else:
                    pred_time = pd.Timestamp(timestamp).to_pydatetime()
                    if pred_time.tzinfo is None:
                        pred_time = pred_time.replace(tzinfo=timezone.utc)
                
                # Evaluation time is 1 hour after prediction
                eval_time = pred_time + timedelta(hours=1)
                
                # Only process if evaluation time has passed
                if eval_time <= now:
                    for csv_asset in csv_assets:
                        pred_col = f"{csv_asset}_prediction"
                        if pred_col not in row or pd.isna(row[pred_col]):
                            continue
                        
                        api_asset = api_asset_map.get(csv_asset.lower(), csv_asset.lower())
                        # Add to global set (shared across miners)
                        all_eval_times_by_asset[api_asset].add(eval_time)
                        # Also track per miner
                        miner_eval_times[miner][api_asset].append(eval_time)
                else:
                    future_count += len(csv_assets)
        
        # STEP 2: Batch load all unique prices from CSV files
        logger.info(f"🔄 Loading prices from CSV files for {len(all_eval_times_by_asset)} assets...")
        all_prices = {}  # {asset: {eval_time: price}}
        
        for api_asset, eval_times_set in all_eval_times_by_asset.items():
            if not eval_times_set:
                continue
            
            eval_times_list = sorted(list(eval_times_set))
            logger.info(f"   {api_asset.upper()}: Loading {len(eval_times_list)} unique prices from CSV (shared across all miners)")
            
            # Batch load all prices for this asset from CSV
            prices = await PriceFetcher.fetch_prices_batch(api_asset, eval_times_list)
            all_prices[api_asset] = prices
        
        # STEP 3: Calculate results per miner
        logger.info(f"📊 Calculating results per miner...")
        
        for miner in miners_to_fetch:
            if miner not in all_miners:
                results[miner] = {"success": False, "error": "Miner not found"}
                continue
            
            # Read CSV again to get time range info
            df = _read_miner_csv(miner)
            if df.empty:
                results[miner] = {"success": False, "error": "No data in CSV file"}
                continue
            
            fetched_count = 0
            failed_count = 0
            skipped_count = 0
            future_count = 0
            
            # Count prices for this miner
            for api_asset, eval_times in miner_eval_times.get(miner, {}).items():
                if api_asset not in all_prices:
                    continue
                
                prices = all_prices[api_asset]
                for eval_time in eval_times:
                    price = prices.get(eval_time)
                    if price is not None:
                        fetched_count += 1
                    else:
                        failed_count += 1
            
            # Calculate time range
            if not df.empty:
                timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
                if timestamp_col in df.columns:
                    df[timestamp_col] = pd.to_datetime(df[timestamp_col], utc=True)
                    earliest_pred = df[timestamp_col].min()
                    latest_pred = df[timestamp_col].max()
                    earliest_eval = earliest_pred + timedelta(hours=1)
                    latest_eval = latest_pred + timedelta(hours=1)
                    
                    time_range = {
                        'earliest_prediction': earliest_pred.isoformat(),
                        'latest_prediction': latest_pred.isoformat(),
                        'earliest_evaluation': earliest_eval.isoformat(),
                        'latest_evaluation': latest_eval.isoformat(),
                        'total_predictions': len(df),
                    }
                else:
                    time_range = {'total_predictions': len(df)}
            else:
                time_range = {}
            
            results[miner] = {
                "success": True,
                "miner_name": miner,
            "prices_fetched": fetched_count,
            "prices_failed": failed_count,
            "prices_skipped": skipped_count,  # Already in cache
            "future_predictions": future_count,  # Not yet evaluable
                "time_range": time_range,
            }
            
            logger.info(
                f"💰 {miner}: Found {fetched_count} prices from CSV, "
                f"{skipped_count} already in cache, {failed_count} failed, "
                f"{future_count} future predictions"
            )
    
    return {
        "success": True,
        "results": results,
        "message": "Actual prices loaded from CSV files into memory cache"
    }


@app.post("/api/reload-prices")
async def reload_prices():
    """Reload prices from CSV files (clears cache and reloads)."""
    try:
        PriceCSVLoader.clear_cache()
        results = await PriceCSVLoader.load_prices()
        total_loaded = sum(results.values())
        return {
            "success": True,
            "message": f"Reloaded {total_loaded} prices from CSV files",
            "results": results
        }
    except Exception as e:
        logger.error(f"Error reloading prices: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/miners/{miner_name}/asset/{asset_name}")
async def get_asset_data(
    miner_name: str, 
    asset_name: str, 
    limit: int = 100, 
    fetch_actuals: bool = False,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None
):
    """Get predictions and actual prices for a specific asset from CSV files.
    
    This endpoint is optimized for fast analysis:
    - Reads predictions from CSV files
    - Looks up actual prices from CSV files (using in-memory cache)
    - Fast lookups from pre-loaded price cache
    """
    # Check if miner exists (either configured or discovered)
    all_miners = Config.get_all_miners()
    if miner_name not in all_miners:
        raise HTTPException(status_code=404, detail="Miner not found")
    
    # Read CSV file
    df = _read_miner_csv(miner_name)
    
    if df.empty:
        return {
            "miner_name": miner_name,
            "asset": asset_name,
            "data": [],
            "count": 0,
            "metrics": {},
            "price_fetch_stats": {'total_evaluable': 0, 'fetched': 0, 'failed': 0, 'future': 0, 'missing': 0},
        }
    
    # Normalize asset name
    asset_map = {
        'btc': 'btc',
        'eth': 'eth',
        'tao': 'tao_bittensor',
        'tao_bittensor': 'tao_bittensor',
    }
    asset_key = asset_map.get(asset_name.lower(), asset_name)
    
    # Map to API asset names (for price fetching)
    api_asset_map = {
        'btc': 'btc',
        'eth': 'eth',
        'tao': 'tao',
        'tao_bittensor': 'tao',
    }
    api_asset = api_asset_map.get(asset_name.lower(), asset_name.lower())
    
    # Extract asset data from CSV
    pred_col = f"{asset_key}_prediction"
    lower_col = f"{asset_key}_interval_lower"
    upper_col = f"{asset_key}_interval_upper"
    
    if pred_col not in df.columns:
        return {
            "miner_name": miner_name,
            "asset": asset_name,
            "data": [],
            "count": 0,
            "metrics": {},
            "price_fetch_stats": {'total_evaluable': 0, 'fetched': 0, 'failed': 0, 'future': 0, 'missing': 0},
        }
    
    # Prepare data
    now = datetime.now(timezone.utc)
    chart_data = []
    
    # Collect data for metrics calculation
    predictions_list = []
    actuals_list = []
    intervals_lower_list = []
    intervals_upper_list = []
    
    # Track price fetching stats
    price_fetch_stats = {
        'total_evaluable': 0,
        'fetched': 0,
        'failed': 0,
        'future': 0,
    }
    
    # Group by timestamp first to handle cases where multiple predictions exist at the same timestamp
    # (miners handle up to 5 requests concurrently, resulting in multiple predictions per timestamp)
    timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
    if timestamp_col in df.columns:
        # Group by timestamp and take the first row for each timestamp
        df_grouped = df.groupby(timestamp_col).first().reset_index()
        # Sort by timestamp (most recent first)
        df_sorted = df_grouped.sort_values(timestamp_col, ascending=False)
        
        # Filter by time range if provided
        if start_time or end_time:
            try:
                if start_time:
                    start_dt = pd.to_datetime(start_time, utc=True)
                    df_sorted = df_sorted[df_sorted[timestamp_col] >= start_dt]
                if end_time:
                    end_dt = pd.to_datetime(end_time, utc=True)
                    df_sorted = df_sorted[df_sorted[timestamp_col] <= end_dt]
            except Exception as e:
                logger.warning(f"Error parsing time range: {e}")
    else:
        df_sorted = df.iloc[::-1]
    
    # Process rows - now we get unique timestamps
    # If time range is specified, use all matching rows; otherwise limit
    if start_time or end_time:
        rows_to_process = df_sorted
    else:
        rows_to_process = df_sorted.head(limit)
    
    for _, row in rows_to_process.iterrows():
        timestamp = row.get('timestamp') or row.get('datetime')
        if not timestamp:
            continue
        
        if isinstance(timestamp, str):
            pred_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        else:
            pred_time = pd.Timestamp(timestamp).to_pydatetime()
            if pred_time.tzinfo is None:
                pred_time = pred_time.replace(tzinfo=timezone.utc)
        
        # Evaluation time is 1 hour after prediction
        eval_time = pred_time + timedelta(hours=1)
        
        prediction = float(row[pred_col]) if pd.notna(row[pred_col]) else None
        interval_lower = float(row[lower_col]) if lower_col in row and pd.notna(row[lower_col]) else None
        interval_upper = float(row[upper_col]) if upper_col in row and pd.notna(row[upper_col]) else None
        
        data_point = {
            'timestamp': pred_time.isoformat(),
            'prediction_time': pred_time.isoformat(),
            'evaluation_time': eval_time.isoformat(),
            'prediction': prediction,
            'interval_lower': interval_lower,
            'interval_upper': interval_upper,
            'actual_price': None,
            'has_actual': False,
        }
        
        # Get actual price from CSV (using in-memory cache)
        if eval_time <= now:
            price_fetch_stats['total_evaluable'] += 1
            if fetch_actuals:
                # Explicitly requested - load from CSV
                actual_price = await PriceFetcher.get_price_at_time(api_asset, eval_time)
                data_point['actual_price'] = actual_price
                data_point['has_actual'] = actual_price is not None
                
                if actual_price is not None:
                    price_fetch_stats['fetched'] += 1
                else:
                    price_fetch_stats['failed'] += 1
            else:
                # Not explicitly requested - try to load anyway (it's fast from cache)
                actual_price = await PriceFetcher.get_price_at_time(api_asset, eval_time)
                data_point['actual_price'] = actual_price
                data_point['has_actual'] = actual_price is not None
                if actual_price is None:
                    price_fetch_stats['missing'] = price_fetch_stats.get('missing', 0) + 1
        elif eval_time > now:
            price_fetch_stats['future'] += 1
        
        # Collect for metrics (only if we have both prediction and actual)
        if data_point['prediction'] is not None and data_point['actual_price'] is not None:
            predictions_list.append(data_point['prediction'])
            actuals_list.append(data_point['actual_price'])
            if data_point['interval_lower'] is not None and data_point['interval_upper'] is not None:
                intervals_lower_list.append(data_point['interval_lower'])
                intervals_upper_list.append(data_point['interval_upper'])
        
        chart_data.append(data_point)
    
    # Reverse to show oldest to newest
    chart_data.reverse()
    
    # Calculate metrics
    metrics = MetricsCalculator.calculate_prediction_metrics(
        predictions=predictions_list,
        actuals=actuals_list,
        intervals_lower=intervals_lower_list if intervals_lower_list else None,
        intervals_upper=intervals_upper_list if intervals_upper_list else None
    )
    
    return {
        "miner_name": miner_name,
        "asset": asset_name,
        "data": chart_data,
        "count": len(chart_data),
        "metrics": metrics,
        "price_fetch_stats": price_fetch_stats,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    try:
        await websocket.accept()
        active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total connections: {len(active_connections)}")
        
        # Send initial data for all miners
        try:
            all_stats = await data_manager.get_all_miners_stats()
            serialized_stats = serialize_for_json(all_stats) if all_stats else {}
            # Verify it's JSON serializable before sending
            import json
            json.dumps(serialized_stats)  # This will raise if not serializable
            await websocket.send_json({
                'type': 'initial',
                'data': serialized_stats
            })
        except Exception as e:
            logger.warning(f"Error sending initial data: {e}")
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                # Echo back or handle client messages
                await websocket.send_json({'type': 'pong', 'data': data})
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total connections: {len(active_connections)}")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=Config.DASHBOARD_HOST,
        port=Config.DASHBOARD_PORT,
        reload=True,
        log_level="info"
    )
