from loguru import logger

# Configure logging
logger.add("logs/pigeonator_{time:YYYYMMDD}.log", rotation="00:00", retention="7 days")

# Export the logger
__all__ = ["logger"]