"""
Logger for tracking changes to invoice data.

This module provides utility functions for logging changes made to invoice data,
particularly during the editing process of invoice items.
"""

from __future__ import annotations

import structlog
from typing import Any, Optional, Union

logger = structlog.get_logger()

async def log_change(
    invoice_id: int, 
    row_idx: int, 
    user_id: int,
    field: str, 
    old: Any, 
    new: Any
):
    """
    Log a change to an invoice field.
    
    Args:
        invoice_id: ID of the invoice being modified
        row_idx: Index of the row in the invoice
        user_id: Telegram user ID of the person making the change
        field: Field name that was changed (name, quantity, unit, price)
        old: Previous value
        new: New value
    """
    logger.info(
        "EDIT",
        invoice_id=invoice_id, 
        row_idx=row_idx, 
        field=field, 
        old=old, 
        new=new, 
        user_id=user_id,
    )

async def log_delete(
    invoice_id: int, 
    row_idx: int, 
    user_id: int,
    item_name: str
):
    """
    Log a row deletion from an invoice.
    
    Args:
        invoice_id: ID of the invoice being modified
        row_idx: Index of the row in the invoice
        user_id: Telegram user ID of the person making the change
        item_name: Name of the deleted item
    """
    logger.info(
        "DELETE",
        invoice_id=invoice_id,
        row_idx=row_idx,
        item_name=item_name,
        user_id=user_id,
    )

async def log_save_new(
    invoice_id: int,

    row_idx: int, 
    user_id: int,
    item_name: str
):
    """
    Log saving a row as a new product.
    
    Args:
        invoice_id: ID of the invoice being modified
        row_idx: Index of the row in the invoice
        user_id: Telegram user ID of the person making the change
        item_name: Name of the item saved as new
    """
    logger.info(
        "SAVE_NEW",
        invoice_id=invoice_id,
        row_idx=row_idx,
        item_name=item_name,
        user_id=user_id,
    )
