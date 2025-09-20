import logging
import os
from datetime import datetime

def setup_logging():
    """Setup logging configuration for the bot"""
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Create log filename with current date
    log_filename = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler()  # Also log to console
        ]
    )
    
    # Create logger
    logger = logging.getLogger('AdvancedCIDBot')
    
    # Log startup message
    logger.info("=" * 50)
    logger.info("Advanced CID Bot Starting...")
    logger.info(f"Log file: {log_filename}")
    logger.info("=" * 50)
    
    return logger

def get_logger(name=None):
    """Get logger instance"""
    return logging.getLogger(name or 'AdvancedCIDBot')
