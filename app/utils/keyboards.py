"""
Keyboard builder utilities for the Telegram bot.

This module contains functions to create consistent keyboards for various
parts of the invoice editing flow.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData


# ────────────────────── Callback Data Classes ──────────────────────

class FieldCallback(CallbackData, prefix="field"):
    """Callback for field editing operations."""
    action: str  # name, qty, unit, price, reset, save, back


class IssueCallback(CallbackData, prefix="issue"):
    """Callback for issue-related operations."""
    action: str  # edit, save_new, delete, review_back


# ────────────────────── Keyboard Builders ──────────────────────

def kb_issue_actions() -> InlineKeyboardMarkup:
    """
    Create keyboard for main actions on an issue.
    
    Returns:
        InlineKeyboardMarkup: Keyboard with edit, save as new, delete and back buttons
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit", callback_data=IssueCallback(action="edit").pack())],
        [InlineKeyboardButton(text="📥 Save as new", callback_data=IssueCallback(action="save_new").pack())],
        [InlineKeyboardButton(text="❌ Delete row", callback_data=IssueCallback(action="delete").pack())],
        [InlineKeyboardButton(text="↩️ Back to issues", callback_data=IssueCallback(action="review_back").pack())]
    ])


def kb_field_selector() -> InlineKeyboardMarkup:
    """
    Create keyboard for selecting which field to edit.
    
    Returns:
        InlineKeyboardMarkup: Keyboard with field selection options
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Name", callback_data=FieldCallback(action="name").pack()),
            InlineKeyboardButton(text="123 Qty", callback_data=FieldCallback(action="qty").pack())
        ],
        [
            InlineKeyboardButton(text="⚖️ Unit", callback_data=FieldCallback(action="unit").pack()),
            InlineKeyboardButton(text="💲 Price", callback_data=FieldCallback(action="price").pack())
        ],
        [InlineKeyboardButton(text="🔄 Reset changes", callback_data=FieldCallback(action="reset").pack())],
        [InlineKeyboardButton(text="↩️ Cancel", callback_data=IssueCallback(action="review_back").pack())]
    ])


def kb_after_edit() -> InlineKeyboardMarkup:
    """
    Create keyboard for actions after editing a field.
    
    Returns:
        InlineKeyboardMarkup: Keyboard with save, edit more, back buttons
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Save", callback_data=FieldCallback(action="save").pack())],
        [InlineKeyboardButton(text="✏️ Edit more", callback_data=IssueCallback(action="edit").pack())],
        [InlineKeyboardButton(text="↩️ Back", callback_data=IssueCallback(action="review_back").pack())]
    ])


# Legacy compatibility functions
def kb_legacy_issue_list(issues: List[Dict[str, Any]], fixed_issues: Dict[int, Dict[str, Any]], page: int = 0) -> InlineKeyboardMarkup:
    """Legacy-compatible function for issue list keyboard with edited indicators."""
    page_size = 5
    total_pages = math.ceil(len(issues) / page_size)
    page = max(0, min(page, total_pages - 1))
    
    buttons = []
    
    # Get issues for current page
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(issues))
    current_issues = issues[start_idx:end_idx]
    
    # Add buttons for each issue, marking edited ones
    for issue in current_issues:
        index = issue.get("index", 0)
        position_idx = index - 1  # Convert to 0-based
        original = issue.get("original", {})
        name = original.get("name", "")[:15]
        
        # Check if this issue has been fixed
        is_fixed = position_idx in fixed_issues
        
        issue_type = issue.get("issue", "")
        
        # Choose icon based on issue type and fixed status
        if is_fixed:
            icon = "📝"  # Mark as edited
        elif "Not in database" in issue_type:
            icon = "⚠"
        elif "incorrect match" in issue_type:
            icon = "❔"
        elif "Unit" in issue_type:
            icon = "🔄"
        else:
            icon = "❓"
            
        btn_text = f"{index}. {icon} {name}"
        buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"issue:{index}")
        ])
    
    # Add pagination buttons
    pagination_row = []
    
    if page > 0:
        pagination_row.append(
            InlineKeyboardButton(text="◀️ Prev", callback_data=f"page:{page-1}")
        )
    
    if page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(text="Next ▶️", callback_data=f"page:{page+1}")
        )
    
    if pagination_row:
        buttons.append(pagination_row)
    
    # Add "Done" button
    buttons.append([
        InlineKeyboardButton(text="✅ Done", callback_data="inv_ok")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)
