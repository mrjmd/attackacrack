"""
Simple logger configuration for scripts.
Provides a consistent logging interface without Flask dependencies.
"""

import logging
import sys
from datetime import datetime

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Get a configured logger for scripts.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # Set level and add handler
        logger.setLevel(getattr(logging, level.upper()))
        logger.addHandler(console_handler)
    
    return logger