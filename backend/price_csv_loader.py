"""Load actual cryptocurrency prices from CSV files."""
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class PriceCSVLoader:
    """Load actual prices from CSV files in the precog_lstm/data/real_price/ directory."""
    
    # Path to real price CSV files (now in precog_lstm/data/real_price/)
    REAL_PRICE_DIR = Path(__file__).parent.parent / "../precog_lstm/data/real_price"
    
    # Asset to CSV file mapping (using _7d.csv files)
    ASSET_CSV_MAP = {
        'btc': 'btc_7d.csv',
        'eth': 'eth_7d.csv',
        'tao': 'tao_7d.csv',
    }
    
    # Fallback filenames (without _7d suffix)
    ASSET_CSV_FALLBACK = {
        'btc': 'btc.csv',
        'eth': 'eth.csv',
        'tao': 'tao.csv',
    }
    
    # Cache for loaded DataFrames (to avoid reloading on every request)
    _price_cache: Dict[str, pd.DataFrame] = {}
    # Cache for price lookups: {asset: {rounded_timestamp: price}}
    _price_lookup_cache: Dict[str, Dict[datetime, float]] = {}
    # Cache for file modification times to detect updates
    _file_mtime_cache: Dict[str, float] = {}
    
    @classmethod
    def _load_price_csv(cls, asset: str, force_reload: bool = False) -> Optional[pd.DataFrame]:
        """Load price CSV file for an asset."""
        if asset.lower() not in cls.ASSET_CSV_MAP:
            logger.warning(f"Unknown asset: {asset}")
            return None
        
        # Try primary filename first, then fallback
        csv_file = cls.REAL_PRICE_DIR / cls.ASSET_CSV_MAP[asset.lower()]
        if not csv_file.exists():
            # Try fallback filename
            fallback_name = cls.ASSET_CSV_FALLBACK.get(asset.lower())
            if fallback_name:
                csv_file = cls.REAL_PRICE_DIR / fallback_name
        
        # Check if file exists
        if not csv_file.exists():
            logger.warning(f"Price CSV file not found: {csv_file}")
            return None
        
        # Check if file has been modified (if cached)
        if not force_reload and asset.lower() in cls._price_cache:
            try:
                current_mtime = csv_file.stat().st_mtime
                cached_mtime = cls._file_mtime_cache.get(asset.lower(), 0)
                # If file hasn't changed, return cached version
                if current_mtime <= cached_mtime:
                    return cls._price_cache[asset.lower()]
                else:
                    # File has been updated, clear cache for this asset
                    logger.info(f"🔄 Price CSV file {csv_file.name} has been updated, reloading...")
                    del cls._price_cache[asset.lower()]
                    if asset.lower() in cls._price_lookup_cache:
                        del cls._price_lookup_cache[asset.lower()]
            except Exception as e:
                logger.debug(f"Error checking file modification time: {e}")
        
        # Load from file (or reload if cache was cleared)
        try:
            df = pd.read_csv(csv_file)
            
            # Parse timestamp column
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            
            # Use 'close' price as the actual price
            if 'close' not in df.columns:
                logger.error(f"CSV file {csv_file} missing 'close' column")
                return None
            
            # Cache the DataFrame
            cls._price_cache[asset.lower()] = df
            
            # Store file modification time
            try:
                cls._file_mtime_cache[asset.lower()] = csv_file.stat().st_mtime
            except Exception:
                pass
            
            # Build lookup cache for fast access
            df['timestamp_rounded'] = df['timestamp'].apply(
                lambda dt: dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
            )
            lookup = {}
            for _, row in df.iterrows():
                lookup[row['timestamp_rounded']] = float(row['close'])
            cls._price_lookup_cache[asset.lower()] = lookup
            
            logger.info(f"✅ Loaded {len(df)} price records from {csv_file}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading price CSV {csv_file}: {e}")
            return None
    
    @classmethod
    async def load_prices(cls, asset: str = None) -> Dict[str, int]:
        """
        Load all prices from CSV files into memory cache.
        
        Args:
            asset: Specific asset to load (btc, eth, tao). If None, loads all assets.
            
        Returns:
            Dictionary mapping asset -> count of prices loaded
        """
        assets_to_load = [asset] if asset else list(cls.ASSET_CSV_MAP.keys())
        results = {}
        
        for asset_name in assets_to_load:
            df = cls._load_price_csv(asset_name)
            if df is None or df.empty:
                results[asset_name] = 0
                continue
            
            # Count is already cached in _load_price_csv
            count = len(cls._price_lookup_cache.get(asset_name, {}))
            results[asset_name] = count
            logger.info(f"✅ Loaded {count} {asset_name.upper()} prices from CSV into memory cache")
        
        return results
    
    @classmethod
    async def get_price_at_time(cls, asset: str, eval_time: datetime) -> Optional[float]:
        """
        Get price at a specific time from CSV file (using in-memory cache).
        
        Args:
            asset: Asset symbol (btc, eth, tao)
            eval_time: Evaluation time
            
        Returns:
            Price at that time, or None if not found
        """
        # Normalize asset name
        asset_map = {
            'tao_bittensor': 'tao',
            'tao': 'tao',
            'btc': 'btc',
            'eth': 'eth',
        }
        api_asset = asset_map.get(asset.lower(), asset.lower())
        
        # Load CSV file (this will populate the cache)
        df = cls._load_price_csv(api_asset)
        if df is None or df.empty:
            return None
        
        # Round to nearest 5 minutes for matching
        eval_minute = eval_time.minute
        rounded_minute = (eval_minute // 5) * 5
        eval_rounded = eval_time.replace(minute=rounded_minute, second=0, microsecond=0)
        
        # Use lookup cache for fast access
        lookup = cls._price_lookup_cache.get(api_asset, {})
        
        # Try exact match first
        if eval_rounded in lookup:
            price = lookup[eval_rounded]
            logger.debug(f"📦 Found {api_asset} price in CSV: ${price:.2f} at {eval_rounded}")
            return price
        
        # Try to find closest match (within 5 minutes)
        closest_time = None
        min_diff = float('inf')
        for price_time in lookup.keys():
            diff = abs((price_time - eval_rounded).total_seconds())
            if diff < min_diff and diff <= 300:  # Within 5 minutes
                min_diff = diff
                closest_time = price_time
        
        if closest_time is not None:
            price = lookup[closest_time]
            logger.debug(f"📦 Found closest {api_asset} price in CSV: ${price:.2f} at {closest_time}")
            return price
        
        logger.debug(f"❌ No {api_asset} price found in CSV for {eval_rounded}")
        return None
    
    @classmethod
    async def fetch_prices_batch(cls, asset: str, eval_times: List[datetime]) -> Dict[datetime, Optional[float]]:
        """
        Fetch multiple prices at once from CSV file (using in-memory cache).
        
        Args:
            asset: Asset symbol (btc, eth, tao)
            eval_times: List of evaluation times to fetch
            
        Returns:
            Dictionary mapping evaluation_time -> price (or None if failed)
        """
        if not eval_times:
            return {}
        
        # Normalize asset name
        asset_map = {
            'tao_bittensor': 'tao',
            'tao': 'tao',
            'btc': 'btc',
            'eth': 'eth',
        }
        api_asset = asset_map.get(asset.lower(), asset.lower())
        
        # Load CSV file (this will populate the cache)
        df = cls._load_price_csv(api_asset)
        if df is None or df.empty:
            return {}
        
        # Use lookup cache for fast access
        lookup = cls._price_lookup_cache.get(api_asset, {})
        result = {}
        
        # Round all times to nearest 5 minutes and look up prices
        for eval_time in eval_times:
            eval_minute = eval_time.minute
            rounded_minute = (eval_minute // 5) * 5
            rounded = eval_time.replace(minute=rounded_minute, second=0, microsecond=0)
            
            # Try exact match first
            if rounded in lookup:
                result[eval_time] = lookup[rounded]
            else:
                # Try to find closest match (within 5 minutes)
                closest_time = None
                min_diff = float('inf')
                for price_time in lookup.keys():
                    diff = abs((price_time - rounded).total_seconds())
                    if diff < min_diff and diff <= 300:  # Within 5 minutes
                        min_diff = diff
                        closest_time = price_time
                
                if closest_time is not None:
                    result[eval_time] = lookup[closest_time]
                else:
                    result[eval_time] = None
        
        found_count = sum(1 for v in result.values() if v is not None)
        logger.debug(f"✅ {api_asset.upper()}: Found {found_count}/{len(eval_times)} prices from CSV cache")
        
        return result
    
    @classmethod
    def clear_cache(cls, asset: str = None):
        """Clear the price CSV cache (useful for reloading after CSV updates)."""
        if asset:
            asset_lower = asset.lower()
            if asset_lower in cls._price_cache:
                del cls._price_cache[asset_lower]
            if asset_lower in cls._price_lookup_cache:
                del cls._price_lookup_cache[asset_lower]
            if asset_lower in cls._file_mtime_cache:
                del cls._file_mtime_cache[asset_lower]
            logger.debug(f"Cleared price CSV cache for {asset}")
        else:
            cls._price_cache.clear()
            cls._price_lookup_cache.clear()
            cls._file_mtime_cache.clear()
            logger.debug("Cleared all price CSV cache")

