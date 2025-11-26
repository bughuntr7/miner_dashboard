"""Metrics calculator for miner predictions."""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculate performance metrics for miner predictions."""
    
    @staticmethod
    def calculate_basic_stats(df: pd.DataFrame, asset: str) -> Dict:
        """Calculate basic statistics for an asset."""
        pred_col = f"{asset}_prediction"
        
        if pred_col not in df.columns:
            return {}
        
        # Filter valid predictions
        valid_df = df[df[pred_col].notna()].copy()
        
        if valid_df.empty:
            return {
                'total_predictions': 0,
                'avg_processing_time': 0,
            }
        
        stats = {
            'total_predictions': len(valid_df),
            'avg_processing_time': float(valid_df['processing_time_seconds'].mean()) if 'processing_time_seconds' in valid_df.columns else 0,
            'min_processing_time': float(valid_df['processing_time_seconds'].min()) if 'processing_time_seconds' in valid_df.columns else 0,
            'max_processing_time': float(valid_df['processing_time_seconds'].max()) if 'processing_time_seconds' in valid_df.columns else 0,
            'latest_prediction': float(valid_df[pred_col].iloc[-1]) if len(valid_df) > 0 else None,
        }
        
        # Get latest timestamp
        if 'timestamp' in valid_df.columns:
            stats['latest_timestamp'] = str(valid_df['timestamp'].iloc[-1])
        elif 'datetime' in valid_df.columns:
            stats['latest_timestamp'] = str(valid_df['datetime'].iloc[-1])
        
        return stats
    
    @staticmethod
    def get_recent_predictions(df: pd.DataFrame, hours: int = 24) -> pd.DataFrame:
        """Get predictions from the last N hours."""
        if df.empty:
            return df
        
        timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
        if timestamp_col not in df.columns:
            return df
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        mask = pd.to_datetime(df[timestamp_col]) >= cutoff
        return df[mask]
    
    @staticmethod
    def calculate_prediction_trends(df: pd.DataFrame, asset: str) -> Dict:
        """Calculate prediction trends over time."""
        pred_col = f"{asset}_prediction"
        
        if pred_col not in df.columns or df.empty:
            return {}
        
        valid_df = df[df[pred_col].notna()].copy()
        
        if len(valid_df) < 2:
            return {}
        
        # Sort by timestamp
        timestamp_col = 'timestamp' if 'timestamp' in valid_df.columns else 'datetime'
        if timestamp_col in valid_df.columns:
            valid_df = valid_df.sort_values(timestamp_col)
        
        predictions = valid_df[pred_col].values
        
        # Calculate trend
        if len(predictions) >= 2:
            recent_avg = float(predictions[-10:].mean()) if len(predictions) >= 10 else float(predictions[-1])
            older_avg = float(predictions[:-10].mean()) if len(predictions) >= 10 else float(predictions[0])
            trend = recent_avg - older_avg
            trend_pct = (trend / older_avg * 100) if older_avg != 0 else 0
        else:
            trend = 0
            trend_pct = 0
        
        return {
            'current_prediction': float(predictions[-1]) if len(predictions) > 0 else None,
            'trend': float(trend),
            'trend_percentage': float(trend_pct),
            'prediction_count': len(predictions),
        }
    
    @staticmethod
    def get_pending_evaluations(df: pd.DataFrame) -> List[Dict]:
        """Get predictions that are pending evaluation (less than 1 hour old)."""
        from backend.csv_parser import CSVParser
        
        if df.empty:
            return []
        
        timestamp_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
        if timestamp_col not in df.columns:
            return []
        
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)
        
        # Filter predictions from last hour
        df['pred_time'] = pd.to_datetime(df[timestamp_col], utc=True)
        pending = df[df['pred_time'] >= one_hour_ago].copy()
        
        if pending.empty:
            return []
        
        pending_list = []
        assets = CSVParser.detect_assets(df)
        
        for _, row in pending.iterrows():
            eval_time = row['pred_time'] + timedelta(hours=1)
            time_until_eval = (eval_time - now).total_seconds()
            
            pending_data = {
                'timestamp': str(row[timestamp_col]),
                'eval_time': eval_time.isoformat(),
                'time_until_eval_seconds': max(0, time_until_eval),
                'assets': [],
            }
            
            # Add asset predictions
            for asset in assets:
                pred_col = f"{asset}_prediction"
                if pred_col in row and pd.notna(row[pred_col]):
                    pending_data['assets'].append({
                        'name': asset,
                        'prediction': float(row[pred_col]),
                    })
            
            pending_list.append(pending_data)
        
        return pending_list
    
    @staticmethod
    def get_validator_stats(df: pd.DataFrame) -> Dict:
        """Get statistics about validators."""
        if df.empty or 'validator_hotkey' not in df.columns:
            return {}
        
        validator_counts = df['validator_hotkey'].value_counts().to_dict()
        
        return {
            'total_validators': len(validator_counts),
            'top_validators': [
                {'hotkey': k[:20] + '...', 'count': int(v)}
                for k, v in list(validator_counts.items())[:5]
            ],
        }
    
    @staticmethod
    def calculate_prediction_metrics(
        predictions: List[float],
        actuals: List[float],
        intervals_lower: Optional[List[float]] = None,
        intervals_upper: Optional[List[float]] = None
    ) -> Dict:
        """
        Calculate prediction accuracy metrics.
        
        Args:
            predictions: List of predicted values
            actuals: List of actual values (must match predictions length)
            intervals_lower: Optional list of lower interval bounds
            intervals_upper: Optional list of upper interval bounds
            
        Returns:
            Dictionary with metrics: MAPE, MAE, RMSE, Bias, Bias%, Coverage, Interval Width%
        """
        if not predictions or not actuals:
            return {}
        
        if len(predictions) != len(actuals):
            logger.warning(f"Predictions ({len(predictions)}) and actuals ({len(actuals)}) length mismatch")
            min_len = min(len(predictions), len(actuals))
            predictions = predictions[:min_len]
            actuals = actuals[:min_len]
        
        if len(predictions) == 0:
            return {}
        
        # Convert to numpy arrays
        preds = np.array(predictions)
        acts = np.array(actuals)
        errors = acts - preds
        
        # Point prediction metrics
        mape = (np.abs(errors) / acts * 100).mean()
        mae = np.abs(errors).mean()
        rmse = np.sqrt((errors ** 2).mean())
        bias = errors.mean()
        bias_pct = (bias / acts.mean()) * 100 if acts.mean() != 0 else 0
        
        metrics = {
            'n_predictions': len(predictions),
            'mape': float(mape),
            'mae': float(mae),
            'rmse': float(rmse),
            'bias': float(bias),
            'bias_pct': float(bias_pct),
        }
        
        # Interval metrics (only if intervals are available)
        if intervals_lower and intervals_upper:
            if len(intervals_lower) == len(actuals) and len(intervals_upper) == len(actuals):
                intervals_lower_arr = np.array(intervals_lower)
                intervals_upper_arr = np.array(intervals_upper)
                
                # Calculate coverage (% of actuals within interval)
                in_interval = ((acts >= intervals_lower_arr) & (acts <= intervals_upper_arr))
                coverage = (in_interval.sum() / len(acts)) * 100
                
                # Calculate average interval width
                interval_widths = intervals_upper_arr - intervals_lower_arr
                avg_interval_width = interval_widths.mean()
                avg_interval_width_pct = (avg_interval_width / acts.mean()) * 100 if acts.mean() != 0 else 0
                
                metrics['coverage'] = float(coverage)
                metrics['avg_interval_width'] = float(avg_interval_width)
                metrics['avg_interval_width_pct'] = float(avg_interval_width_pct)
            else:
                logger.warning(f"Interval length mismatch: lower={len(intervals_lower)}, upper={len(intervals_upper)}, actuals={len(actuals)}")
        
        return metrics

