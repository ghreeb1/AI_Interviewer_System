#!/usr/bin/env python3
"""
AI Interviewer System - Entry Point

This script starts the AI Interviewer application with all necessary services.
"""

import uvicorn
import os
import sys
import logging

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

def main():
    """Main entry point for the application"""
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)
    # Start the server
    try:
        uvicorn.run(
            app,
            host="localhost",
            port=8000,
            log_level="info",
            reload=False  # Set to True for development
        )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
