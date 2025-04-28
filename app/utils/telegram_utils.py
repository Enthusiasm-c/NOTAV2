"""
Telegram utilities for NOTA V2.

Common functions for working with Telegram files and messages.
"""
from __future__ import annotations

import structlog
from aiogram import Bot

logger = structlog.get_logger()

async def download_file(bot: Bot, file_id: str) -> bytes:
    """
    Download file from Telegram and return bytes.

    Args:
        bot: Bot instance
        file_id: Telegram file ID
        
    Returns:
        bytes: File content
    """
    tg_file = await bot.get_file(file_id)
    stream = await bot.download_file(tg_file.file_path)  # coroutine → BytesIO
    return stream.read()  # BytesIO → bytes
