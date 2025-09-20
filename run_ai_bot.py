#!/usr/bin/env python3
"""
Main entry point for Advanced CID Telegram Bot
Run this file to start the bot with all admin panel features
"""

import sys
import os
from pathlib import Path

# Add the project directory to Python path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))
sys.path.insert(0, str(Path(__file__).parent))

from bot import AdvancedCIDBot

def main():
    """Main function to run the Advanced CID Bot"""
    print("🚀 Starting Advanced CID Telegram Bot...")
    print("📋 Features available:")
    print("  ✅ CID Generation from Installation ID or Image")
    print("  ✅ Package System (25-10000 CID)")
    print("  ✅ USDT Payment Processing")
    print("  ✅ Voucher Code System")
    print("  ✅ Complete Admin Panel")
    print("  ✅ User Balance Management")
    print("  ✅ Operations Logging")
    print()
    
    try:
        # Initialize and run the bot
        bot = AdvancedCIDBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
