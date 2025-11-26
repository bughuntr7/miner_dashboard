"""Configuration management for the dashboard backend."""
import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Local CSV files path (relative to project root)
    # Points to precog_lstm/data/miner directory
    MINER_DATA_DIR: str = os.getenv("MINER_DATA_DIR", "../precog_lstm/data/miner")
    
    # Real price CSV files path (relative to project root)
    # Points to precog_lstm/data/real_price directory
    REAL_PRICE_DIR: str = os.getenv("REAL_PRICE_DIR", "../precog_lstm/data/real_price")
    
    # Dashboard Configuration
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8000"))
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:3001"
    ).split(",")
    
    # Miner Configuration
    MINERS: Dict[str, str] = {}
    _miners_str = os.getenv("MINERS", "miner1:Miner 1,miner2:Miner 2")
    for pair in _miners_str.split(","):
        if ":" in pair:
            name, display = pair.split(":", 1)
            MINERS[name.strip()] = display.strip()
        else:
            MINERS[pair.strip()] = pair.strip().title()
    
    # File Watching (optional - for watching CSV changes)
    POLL_INTERVAL_SECONDS: float = float(os.getenv("POLL_INTERVAL_SECONDS", "60"))  # 60 seconds default
    MAX_HISTORICAL_ROWS: int = int(os.getenv("MAX_HISTORICAL_ROWS", "1000"))
    
    @classmethod
    def get_miner_csv_path(cls, miner_name: str) -> str:
        """Get the local CSV file path for a miner."""
        # Get project root (parent of backend directory)
        project_root = Path(__file__).parent.parent
        # Try my_predictions_history.csv first, fallback to miner_predictions_history.csv
        csv_path = project_root / cls.MINER_DATA_DIR / miner_name / "my_predictions_history.csv"
        if not csv_path.exists():
            # Fallback to the old filename
            csv_path = project_root / cls.MINER_DATA_DIR / miner_name / "miner_predictions_history.csv"
        return str(csv_path)
    
    @classmethod
    def discover_miners(cls) -> Dict[str, str]:
        """
        Automatically discover miners from the file system.
        Scans the miner directory for subdirectories containing my_predictions_history.csv files.
        
        Returns:
            Dictionary mapping miner_name -> display_name
        """
        project_root = Path(__file__).parent.parent
        miner_dir = project_root / cls.MINER_DATA_DIR
        
        discovered_miners = {}
        
        if not miner_dir.exists():
            return discovered_miners
        
        # Scan for miner directories
        for miner_path in miner_dir.iterdir():
            if miner_path.is_dir():
                miner_name = miner_path.name
                # Try my_predictions_history.csv first, fallback to miner_predictions_history.csv
                csv_file = miner_path / "my_predictions_history.csv"
                if not csv_file.exists():
                    csv_file = miner_path / "miner_predictions_history.csv"
                
                # Check if this directory has a valid CSV file
                if csv_file.exists():
                    # Use configured display name if available, otherwise generate one
                    display_name = cls.MINERS.get(miner_name, miner_name.replace('_', ' ').title())
                    discovered_miners[miner_name] = display_name
        
        return discovered_miners
    
    @classmethod
    def get_all_miners(cls) -> Dict[str, str]:
        """
        Get all miners (configured + discovered).
        Combines manually configured miners with auto-discovered ones.
        
        Returns:
            Dictionary mapping miner_name -> display_name
        """
        # Start with configured miners
        all_miners = cls.MINERS.copy()
        
        # Add discovered miners (will override configured ones if they exist)
        discovered = cls.discover_miners()
        all_miners.update(discovered)
        
        return all_miners
    
    @classmethod
    def get_real_price_dir(cls) -> Path:
        """Get the real price CSV files directory path."""
        project_root = Path(__file__).parent.parent
        return project_root / cls.REAL_PRICE_DIR

