__all__ = ["log"]

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

def log(message: str):
    """Простой логгер"""
    logging.info(message)
