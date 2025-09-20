"""
Configuration file for Advanced CID Telegram Bot
Contains all settings, API keys, and constants
"""

import os
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class DatabaseConfig:
    """Database configuration"""
    type: str = "sqlite"  # sqlite or mysql
    name: str = os.path.join(os.path.dirname(__file__), "advanced_cid_bot.db")  # Use local database with real data
    host: str = "localhost"
    user: str = ""
    password: str = ""
    port: int = 3306

@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str = "YOUR_BOT_TOKEN_HERE"
    admin_ids: List[int] = None
    
    def __post_init__(self):
        if self.admin_ids is None:
            self.admin_ids = [123456789]  # Replace with actual admin IDs

@dataclass
class BinanceConfig:
    """Binance payment configuration"""
    usdt_trc20_address: str = "أدخل عنوان محفظة USDT TRC20 هنا"  # Replace with actual address
    tronscan_api_url: str = "https://apilist.tronscanapi.com/api"
    confirmation_blocks: int = 1

@dataclass
class PIDKEYConfig:
    """PIDKEY API configuration"""
    api_url: str = "https://api.pidkey.com"  # Replace with actual API URL
    api_key: str = "YOUR_PIDKEY_API_KEY"
    cost_per_cid: float = 0.2  # Cost in USD per CID

@dataclass
class Package:
    """Package definition"""
    id: int
    name: str
    cid_amount: int
    price_sar: float
    price_usd: float

class Config:
    """Main configuration class"""
    
    def __init__(self):
        # Load from environment variables or use defaults
        self.database = DatabaseConfig()
        
        self.telegram = TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "7687105300:AAGGYs9L7DVmRZrDftLc-8S7afL_EFmUPpM"),
            admin_ids=[int(x) for x in os.getenv("ADMIN_IDS", "5255786759,990541").split(",")]
        )
        
        self.binance = BinanceConfig(
            usdt_trc20_address=os.getenv("USDT_TRC20_ADDRESS", "TFHirK1z8VTss4oDLeyQJ4JwQceMembFrQ")
        )
        
        self.pidkey = PIDKEYConfig(
            api_key=os.getenv("PIDKEY_API_KEY", "YOUR_PIDKEY_API_KEY")
        )
        
        # Exchange rates (update periodically)
        self.usd_to_sar = 3.75  # 1 USD = 3.75 SAR (approximate)
        
        # Define packages
        self.packages = [
            Package(1, "باقة صغيرة", 25, 20.0, 20.0 / self.usd_to_sar),
            Package(2, "باقة متوسطة", 50, 25.0, 25.0 / self.usd_to_sar),
            Package(3, "باقة كبيرة", 100, 47.0, 47.0 / self.usd_to_sar),
            Package(4, "باقة ممتازة", 500, 212.0, 212.0 / self.usd_to_sar),
            Package(5, "باقة فائقة", 1000, 385.0, 385.0 / self.usd_to_sar),
            Package(6, "باقة احترافية", 2000, 693.0, 693.0 / self.usd_to_sar),
            Package(7, "باقة المؤسسات", 5000, 1530.0, 1530.0 / self.usd_to_sar),
            Package(8, "باقة الشركات", 10000, 2860.14, 2860.14 / self.usd_to_sar),
        ]
    
    def get_package_by_id(self, package_id: int) -> Package:
        """Get package by ID"""
        for package in self.packages:
            if package.id == package_id:
                return package
        return None
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.telegram.admin_ids

# Global config instance
config = Config()
