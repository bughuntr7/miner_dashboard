"""Data manager for storing and serving miner data."""
import asyncio
from typing import Dict, Optional
import pandas as pd
import logging

from backend.csv_parser import CSVParser
from backend.metrics import MetricsCalculator

logger = logging.getLogger(__name__)


class DataManager:
    """Manage data for all miners."""
    
    def __init__(self):
        self.miner_data: Dict[str, pd.DataFrame] = {}
        self.miner_stats: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def update_miner_data(self, miner_name: str, df: pd.DataFrame):
        """Update data for a miner."""
        async with self._lock:
            if miner_name in self.miner_data:
                # Merge with existing data
                existing = self.miner_data[miner_name]
                # Combine and remove duplicates
                combined = pd.concat([existing, df], ignore_index=True)
                timestamp_col = 'timestamp' if 'timestamp' in combined.columns else 'datetime'
                if timestamp_col in combined.columns:
                    combined = combined.drop_duplicates(subset=[timestamp_col], keep='last')
                    combined = combined.sort_values(timestamp_col, ascending=False)
                self.miner_data[miner_name] = combined
            else:
                self.miner_data[miner_name] = df
            
            # Update stats
            await self._update_stats(miner_name)
    
    async def _update_stats(self, miner_name: str):
        """Update statistics for a miner."""
        df = self.miner_data.get(miner_name)
        if df is None or df.empty:
            return
        
        assets = CSVParser.detect_assets(df)
        
        stats = {
            'miner_name': miner_name,
            'total_predictions': len(df),
            'assets': {},
            'recent_predictions': len(MetricsCalculator.get_recent_predictions(df, hours=24)),
            'pending_evaluations': len(MetricsCalculator.get_pending_evaluations(df)),
            'validator_stats': MetricsCalculator.get_validator_stats(df),
        }
        
        # Stats per asset
        for asset in assets:
            stats['assets'][asset] = {
                'basic_stats': MetricsCalculator.calculate_basic_stats(df, asset),
                'trends': MetricsCalculator.calculate_prediction_trends(df, asset),
            }
        
        self.miner_stats[miner_name] = stats
    
    async def get_miner_data(self, miner_name: str) -> Optional[pd.DataFrame]:
        """Get data for a miner."""
        return self.miner_data.get(miner_name)
    
    async def get_miner_stats(self, miner_name: str) -> Optional[Dict]:
        """Get statistics for a miner."""
        return self.miner_stats.get(miner_name)
    
    async def get_all_miners_stats(self) -> Dict:
        """Get statistics for all miners."""
        return self.miner_stats.copy()
    
    async def get_latest_predictions(self, miner_name: str, limit: int = 100) -> list:
        """Get latest predictions for a miner."""
        df = self.miner_data.get(miner_name)
        if df is None or df.empty:
            return []
        
        return CSVParser.get_latest_predictions(df, limit=limit)

