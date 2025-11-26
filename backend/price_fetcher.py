"""Fetch actual cryptocurrency prices for evaluation (from CSV files)."""
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
import logging

from backend.price_csv_loader import PriceCSVLoader

logger = logging.getLogger(__name__)


class PriceFetcher:
    """Fetch actual prices from various sources."""
    
    @staticmethod
    async def fetch_prices_batch(asset: str, eval_times: List[datetime]) -> Dict[datetime, Optional[float]]:
        """
        Fetch multiple prices at once from CSV files.
        
        Args:
            asset: Asset symbol (btc, eth, tao)
            eval_times: List of evaluation times to fetch
            
        Returns:
            Dictionary mapping evaluation_time -> price (or None if failed)
        """
        return await PriceCSVLoader.fetch_prices_batch(asset, eval_times)
    
    
    @staticmethod
    async def get_price_at_time(asset: str, eval_time: datetime) -> Optional[float]:
        """Get actual price at evaluation time from CSV files (using in-memory cache)."""
        # Normalize asset name
        asset_map = {
            'tao_bittensor': 'tao',
            'tao': 'tao',
            'btc': 'btc',
            'eth': 'eth',
        }
        api_asset = asset_map.get(asset.lower(), asset.lower())
        
        # Load from CSV (uses in-memory cache)
        return await PriceCSVLoader.get_price_at_time(api_asset, eval_time)
    
