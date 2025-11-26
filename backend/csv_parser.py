"""CSV parser for miner prediction history."""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class CSVParser:
    """Parser for miner prediction history CSV files."""
    
    @staticmethod
    def parse_csv(csv_content: str) -> pd.DataFrame:
        """Parse CSV content into DataFrame."""
        if not csv_content or not csv_content.strip():
            return pd.DataFrame()
        
        try:
            from io import StringIO
            df = pd.read_csv(StringIO(csv_content))
            
            # Parse timestamp column
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            if 'datetime' in df.columns:
                df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
            
            return df
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            return pd.DataFrame()
    
    @staticmethod
    def detect_assets(df: pd.DataFrame) -> List[str]:
        """Detect assets from CSV columns."""
        assets = []
        for col in df.columns:
            if col.endswith('_prediction') and not col.endswith('_raw_prediction'):
                asset_key = col.replace('_prediction', '')
                assets.append(asset_key)
        return assets
    
    @staticmethod
    def get_latest_predictions(df: pd.DataFrame, limit: int = 100) -> List[Dict]:
        """Get latest predictions from DataFrame."""
        if df.empty:
            return []
        
        # Sort by timestamp (most recent first)
        if 'timestamp' in df.columns:
            df_sorted = df.sort_values('timestamp', ascending=False)
        elif 'datetime' in df.columns:
            df_sorted = df.sort_values('datetime', ascending=False)
        else:
            df_sorted = df.iloc[::-1]  # Reverse order
        
        latest = df_sorted.head(limit)
        
        predictions = []
        assets = CSVParser.detect_assets(df)
        
        for _, row in latest.iterrows():
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
        
        return predictions
    
    @staticmethod
    def get_new_rows(
        old_df: pd.DataFrame, 
        new_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Get new rows that appeared in new_df but not in old_df."""
        if old_df.empty:
            return new_df
        
        if new_df.empty:
            return pd.DataFrame()
        
        # Use timestamp as unique identifier
        timestamp_col = 'timestamp' if 'timestamp' in new_df.columns else 'datetime'
        
        if timestamp_col not in new_df.columns:
            # Fallback: compare all rows
            return new_df[~new_df.isin(old_df).all(axis=1)]
        
        # Get timestamps from both dataframes
        old_timestamps = set(old_df[timestamp_col].astype(str))
        new_timestamps = set(new_df[timestamp_col].astype(str))
        
        # Find new timestamps
        added_timestamps = new_timestamps - old_timestamps
        
        if not added_timestamps:
            return pd.DataFrame()
        
        # Return rows with new timestamps
        mask = new_df[timestamp_col].astype(str).isin(added_timestamps)
        return new_df[mask]

