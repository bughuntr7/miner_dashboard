"""File watcher for monitoring local CSV files."""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Optional, Callable, Any
from datetime import datetime

from backend.csv_parser import CSVParser
from backend.config import Config

logger = logging.getLogger(__name__)


class FileWatcher:
    """Watch local CSV files and notify on changes."""
    
    def __init__(self, miner_name: str, on_update: Callable):
        self.miner_name = miner_name
        self.on_update = on_update
        self.csv_path = Path(Config.get_miner_csv_path(miner_name))
        self.last_size: Optional[int] = None
        self.last_mtime: Optional[float] = None
        self.last_df = None
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start watching the file."""
        if self.running:
            return
        
        self.running = True
        
        # Do initial load
        try:
            await self._read_and_process()
        except Exception as e:
            logger.warning(f"Initial load failed for {self.miner_name}: {e}")
        
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watching {self.csv_path} for miner {self.miner_name}")
    
    async def stop(self):
        """Stop watching the file."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped watching {self.csv_path}")
    
    async def _watch_loop(self):
        """Main watching loop."""
        while self.running:
            try:
                await self._check_for_updates()
                await asyncio.sleep(Config.POLL_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Error in watch loop for {self.miner_name}: {e}")
                await asyncio.sleep(Config.POLL_INTERVAL_SECONDS * 2)  # Wait longer on error
    
    async def _check_for_updates(self):
        """Check if file has been updated."""
        try:
            if not self.csv_path.exists():
                if self.last_size is not None:
                    logger.warning(f"CSV file not found: {self.csv_path}")
                return
            
            # Check file modification time and size
            stat = self.csv_path.stat()
            current_size = stat.st_size
            current_mtime = stat.st_mtime
            
            # If file changed, read new content
            if current_size != self.last_size or current_mtime != self.last_mtime:
                await self._read_and_process()
                self.last_size = current_size
                self.last_mtime = current_mtime
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
    
    async def _read_and_process(self):
        """Read CSV file and process updates."""
        try:
            if not self.csv_path.exists():
                logger.warning(f"CSV file does not exist: {self.csv_path}")
                return
            
            # Read CSV file
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                # Read last N lines if file is large
                lines = f.readlines()
                if len(lines) > Config.MAX_HISTORICAL_ROWS:
                    csv_content = ''.join(lines[-Config.MAX_HISTORICAL_ROWS:])
                else:
                    csv_content = ''.join(lines)
            
            if not csv_content:
                return
            
            # Parse CSV
            new_df = CSVParser.parse_csv(csv_content)
            
            if new_df.empty:
                return
            
            # Get new rows if we have previous data
            if self.last_df is not None:
                new_rows = CSVParser.get_new_rows(self.last_df, new_df)
                if not new_rows.empty:
                    logger.info(f"New predictions detected for {self.miner_name}: {len(new_rows)} rows")
                    await self.on_update(self.miner_name, new_rows)
            else:
                # First read - send all data
                logger.info(f"Initial load for {self.miner_name}: {len(new_df)} rows")
                await self.on_update(self.miner_name, new_df)
            
            self.last_df = new_df
            
        except Exception as e:
            logger.error(f"Error reading/processing CSV for {self.miner_name}: {e}")
    
    async def get_current_data(self) -> Optional[object]:
        """Get current data snapshot."""
        try:
            if not self.csv_path.exists():
                return None
            
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > Config.MAX_HISTORICAL_ROWS:
                    csv_content = ''.join(lines[-Config.MAX_HISTORICAL_ROWS:])
                else:
                    csv_content = ''.join(lines)
            
            if not csv_content:
                return None
            
            df = CSVParser.parse_csv(csv_content)
            return df
            
        except Exception as e:
            logger.error(f"Error getting current data: {e}")
            return None
    
    async def manual_fetch(self) -> Dict[str, Any]:
        """Manually trigger a fetch from CSV file and return results."""
        try:
            logger.info(f"🔄 Manual fetch triggered for {self.miner_name}")
            await self._read_and_process()
            return {
                "success": True,
                "miner_name": self.miner_name,
                "message": f"Data loaded from CSV for {self.miner_name}"
            }
        except Exception as e:
            logger.error(f"Error in manual fetch for {self.miner_name}: {e}")
            return {
                "success": False,
                "miner_name": self.miner_name,
                "error": str(e)
            }
