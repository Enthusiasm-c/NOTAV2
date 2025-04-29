"""
Enhanced handlers for issue editing in Nota V2.

This module contains improved handlers for the issue editing workflow,
implementing a more user-friendly editing experience with proper field
validation and change tracking.
"""

from __future__ import annotations

import re
import structlog
from typing import Dict, Any, Union, Optional, List

from aiogram import Router, F
from aiogram.filters import Text
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, 
    CallbackQuery, 
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.invoice_state import InvoiceEditStates
from app.models.product import Product
from app.utils.keyboards import (
    kb_issue_actions, 
    kb_field_selector, 
    kb_after_edit,
    FieldCallback,
    IssueCallback
)
from app.utils.change_logger import log_change, log_delete, log_save_new

# Try to import fuzzy matching function, with fallback
try:
    from app.routers.fuzzy_match import fuzzy_match_product
except ImportError:
    # Fallback implementation if not available
    async def fuzzy_match_product(session, name, threshold=None):
        return None, 0.0

# Utilities for unit normalization
try:
    from app.utils.unit_converter import normalize_unit
except ImportError:
    # Simple fallback implementation
    def normalize_unit(unit_str: str) -> str:
        if not unit_str:
            return ""
        return unit_str.lower().strip()

logger = structlog.get_logger()
router = Router(name="issue_editor_enhanced")

# ───────────────────────── Templates ────────────────────────

def format_issue_card(issue: Dict[str, Any], is_edited: bool = False) -> str:
    """
    Format an issue card with HTML markup.
    
    Args:
        issue: The issue data dictionary
        is_edited: Whether the issue has been edited
        
    Returns:
        HTML formatted card text
    """
    index = issue.get("index", 0)
    original = issue.get("original", {})
    
    name = original.get("name", "Unknown")
    quantity = original.get("quantity", 0)
    unit = original.get("unit", "")
    price = original.get("price", "")
    sum_val = original.get("sum", "")
    
    # Determine issue type and icon
    issue_type = issue.get("issue", "Unknown issue")
    
    if "Not in database" in issue_type:
        icon = "⚠"
        issue_description = "Not in database"
    elif "incorrect match" in issue_type:
        icon = "❔"
        issue_description = "Low confidence match"
    elif "Unit" in issue_type:
        icon = "🔄"
        issue_description = "Unit measurement discrepancy"
    else:
        icon = "❓"
        issue_description = issue_type
        
    # Add edit indicator if needed
    edit_prefix = "📝 " if is_edited else ""
    
    # Build the message
    message = f"{edit_prefix}<b>Row {index}:</b> {name}\n\n"
    message += f"<b>Problem:</b> {icon} {issue_description}\n"
    message += f"<b>Qty:</b> {quantity} {unit}\n"
    
    if price:
        try:
            price_float = float(price)
            message += f"<b>Price:</b> {price_float:.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Price:</b> {price or '—'}\n"
    else:
        message += "<b>Price:</b> —\n"
        
    if sum_val:
        try:
            sum_float = float(sum_val)
            message += f"<b>Sum:</b> {sum_float:.2f}\n"
        except (ValueError, TypeError):
            message += f"<b>Sum:</b> {sum_val}\n"
    else:
        # Calculate sum if possible
        if price and quantity:
            try:
                price_float = float(price)
                qty_float = float(quantity)
                message += f"<b>Sum:</b> {price_float * qty_float:.2f}\n"
            except (ValueError, TypeError):
                message += "<b>Sum:</b> —\n"
        else:
            message += "<b>Sum:</b> —\n"
    
    message += "\n<i>Select an action:</i>"
    
    return message


def format_field_prompt(field: str, current_value: str) -> str:
    """
    Format a prompt for editing a specific field.
    
    Args:
        field: The field name being edited
        current_value: The current value of the field
        
    Returns:
        HTML formatted prompt text
    """
    field_labels = {
        "name": "name",
        "qty": "quantity",
        "unit": "unit of measurement",
        "price": "price"
    }
    
    field_label = field_labels.get(field, field)
    
    message = f"<b>Enter new {field_label}:</b>\n\n"
    message += f"Current value: {current_value}\n\n"
    
    field_hints = {
        "name": "Enter product name (max 100 characters)",
        "qty": "Enter numeric quantity (e.g., 5 or 2.5)",
        "unit": "Enter unit of measurement (e.g., kg, l, pcs)",
        "price": "Enter price (numbers only)"
    }
    
    if field in field_hints:
        message += f"<i>{field_hints[field]}</i>"
        
    return message


def format_edit_confirmation(field: str, old_value: str, new_value: str) -> str:
    """
    Format a confirmation message after editing a field.
    
    Args:
        field: The field name that was edited
        old_value: The previous value
        new_value: The new value
        
    Returns:
        HTML formatted confirmation text
    """
    field_labels = {
        "name": "Name",
        "qty": "Quantity",
        "unit": "Unit",
        "price": "Price"
    }
    
    field_label = field_labels.get(field, field.capitalize())
    
    message = f"✅ <b>{field_label} updated.</b>\n"
    message += f"{old_value} → {new_value}\n\n"
    message += "<i>What would you like to do next?</i>"
    
    return message


# ───────────────────────── Handlers ────────────────────────

@router.callback_query(IssueCallback.filter(F.action == "edit"))
async def handle_edit_request(c: CallbackQuery, state: FSMContext):
    """
    Handle the edit button click to show field selector.
    """
    await state.set_state(InvoiceEditStates.edit_field)
    
    await c.message.edit_text(
        "Which field would you like to edit?",
        reply_markup=kb_field_selector(),
        parse_mode="HTML"
    )
    
    await c.answer()


@router.callback_query(FieldCallback.filter())
async def handle_field_selection(
    c: CallbackQuery, 
    callback_data: FieldCallback,
    state: FSMContext
):
    """
    Handle field selection for editing.
    """
    action = callback_data.action
    
    # Get data from state
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    original = selected_issue.get("original", {})
    
    # Handle reset action
    if action == "reset":
        # Reset the issue to original state
        invoice_data = data.get("invoice", {})
        position_idx = selected_issue.get("index", 0) - 1
        
        if "original_data" in data and position_idx in data["original_data"]:
            # Restore from backup
            invoice_data["positions"][position_idx] = data["original_data"][position_idx].copy()
            
            # Remove from fixed issues
            fixed_issues = data.get("fixed_issues", {})
            if position_idx in fixed_issues:
                del fixed_issues[position_idx]
                await state.update_data(fixed_issues=fixed_issues)
            
            await state.update_data(invoice=invoice_data)
            
            # Return to issue review
            await state.set_state(InvoiceEditStates.issue_review)
            
            # Show updated issue
            is_edited = False
            message = format_issue_card(selected_issue, is_edited)
            
            await c.message.edit_text(
                message,
                reply_markup=kb_issue_actions(),
                parse_mode="HTML"
            )
        else:
            await c.answer("Cannot reset: original data not found")
        
        return
    
    # Handle save action
    if action == "save":
        # Save changes and return to issue list
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Get updated data
        data = await state.get_data()
        current_issues = data.get("current_issues", [])
        fixed_issues = data.get("fixed_issues", {})
        
        # Format issue list message
        from app.routers.issue_editor import format_issues_list
        message, keyboard = await format_issues_list(
            {"issues": current_issues}, 
            page=data.get("current_page", 0)
        )
        
        message = "✅ Changes saved.\n\n" + message
        
        await c.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await c.answer("Changes saved")
        return
    
    # Handle field edit actions (name, qty, unit, price)
    if action in ["name", "qty", "unit", "price"]:
        await state.set_state(InvoiceEditStates.input_value)
        await state.update_data(edit_field=action)
        
        # Get current value based on field
        current_value = ""
        if action == "name":
            current_value = original.get("name", "")
        elif action == "qty":
            current_value = str(original.get("quantity", ""))
        elif action == "unit":
            current_value = original.get("unit", "")
        elif action == "price":
            current_value = str(original.get("price", ""))
        
        # Show prompt with ForceReply
        message = format_field_prompt(action, current_value)
        
        await c.message.edit_text(message, parse_mode="HTML")
        
        # Request input with force reply
        sent_msg = await c.message.answer(
            "Enter the new value:",
            reply_markup=ForceReply(selective=True)
        )
        
        # Store message ID to be able to delete it later
        await state.update_data(prompt_message_id=sent_msg.message_id)
        
        await c.answer()
        return
    
    # If we get here, it's an unknown action
    await c.answer(f"Unsupported action: {action}")


@router.message(InvoiceEditStates.input_value)
async def process_field_input(message: Message, state: FSMContext):
    """
    Process user input for field editing.
    """
    # Get data from state
    data = await state.get_data()
    field = data.get("edit_field", "")
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    position_idx = selected_issue.get("index", 0) - 1
    
    # Check if we have valid data
    if not field or position_idx < 0 or position_idx >= len(positions):
        await message.reply("❌ Error: Invalid position or field.")
        return
    
    # Get position data
    position = positions[position_idx]
    
    # Store original data for potential reset
    if "original_data" not in data:
        await state.update_data(original_data={
            position_idx: position.copy()
        })
    elif position_idx not in data["original_data"]:
        original_data = data["original_data"]
        original_data[position_idx] = position.copy()
        await state.update_data(original_data=original_data)
    
    # Get the new value from user input
    new_value = message.text.strip()
    
    # Validate input based on field type
    valid_input = True
    validation_error = ""
    
    if field == "name":
        if len(new_value) > 100:
            valid_input = False
            validation_error = "❌ Name is too long (max 100 characters)"
        elif not new_value:
            valid_input = False
            validation_error = "❌ Name cannot be empty"
    
    elif field == "qty":
        try:
            # Replace comma with dot for decimal point
            new_value = new_value.replace(',', '.')
            quantity = float(new_value)
            if quantity <= 0:
                valid_input = False
                validation_error = "❌ Quantity must be greater than zero"
            new_value = str(quantity)  # Normalize
        except ValueError:
            valid_input = False
            validation_error = "❌ Invalid number. Please enter a valid quantity."
    
    elif field == "unit":
        if not new_value:
            # If empty, keep old value
            new_value = position.get("unit", "")
        else:
            # Normalize unit
            new_value = normalize_unit(new_value)
    
    elif field == "price":
        try:
            # Replace comma with dot for decimal point
            new_value = new_value.replace(',', '.')
            price = float(new_value)
            if price < 0:
                valid_input = False
                validation_error = "❌ Price cannot be negative"
            new_value = str(price)  # Normalize
        except ValueError:
            valid_input = False
            validation_error = "❌ Invalid number. Please enter a valid price."
    
    # If validation failed, ask again
    if not valid_input:
        await message.reply(validation_error)
        return
    
    # Get current value for logging and display
    old_value = ""
    if field == "name":
        old_value = position.get("name", "")
    elif field == "qty":
        old_value = str(position.get("quantity", ""))
    elif field == "unit":
        old_value = position.get("unit", "")
    elif field == "price":
        old_value = str(position.get("price", ""))
    
    # Update position data based on field
    if field == "name":
        position["name"] = new_value
        
        # Try to find match in database if name changed
        async with SessionLocal() as session:
            product_id, confidence = await fuzzy_match_product(
                session, new_value, settings.fuzzy_threshold
            )
            
            if product_id:
                position["match_id"] = product_id
                position["confidence"] = confidence
                
                # Get product details
                stmt = select(Product).where(Product.id == product_id)
                result = await session.execute(stmt)
                product = result.scalar_one_or_none()
                
                if product:
                    selected_issue["product"] = product
                    await state.update_data(selected_issue=selected_issue)
    
    elif field == "qty":
        position["quantity"] = float(new_value)
        
        # Recalculate sum if price exists
        if "price" in position and position["price"]:
            try:
                price = float(position["price"])
                position["sum"] = price * float(new_value)
            except (ValueError, TypeError):
                pass
    
    elif field == "unit":
        position["unit"] = new_value
    
    elif field == "price":
        position["price"] = float(new_value)
        
        # Recalculate sum if quantity exists
        if "quantity" in position and position["quantity"]:
            try:
                quantity = float(position["quantity"])
                position["sum"] = float(new_value) * quantity
            except (ValueError, TypeError):
                pass
    
    # Update data in state
    positions[position_idx] = position
    invoice_data["positions"] = positions
    await state.update_data(invoice=invoice_data)
    
    # Add to fixed issues
    fixed_issues = data.get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    if position_idx not in fixed_issues:
        fixed_issues[position_idx] = {"action": "manual_edit"}
    
    fixed_issues[position_idx][f"edit_{field}"] = {
        "old": old_value,
        "new": new_value
    }
    
    await state.update_data(fixed_issues=fixed_issues)
    
    # Log the change
    try:
        invoice_id = invoice_data.get("id", 0)
        user_id = message.from_user.id if message.from_user else 0
        
        await log_change(
            invoice_id=invoice_id,
            row_idx=position_idx,
            user_id=user_id,
            field=field,
            old=old_value,
            new=new_value
        )
    except Exception as e:
        logger.error("Failed to log change", error=str(e))
    
    # Try to delete the prompt message if we stored its ID
    prompt_message_id = data.get("prompt_message_id")
    if prompt_message_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_message_id)
        except Exception as e:
            logger.error("Failed to delete prompt message", error=str(e))
    
    # Set state to confirm edit
    await state.set_state(InvoiceEditStates.confirm_edit)
    
    # Format confirmation message
    confirmation = format_edit_confirmation(field, old_value, new_value)
    
    # Send confirmation
    await message.reply(
        confirmation,
        reply_markup=kb_after_edit(),
        parse_mode="HTML"
    )


@router.callback_query(IssueCallback.filter(F.action == "save_new"))
async def handle_save_as_new(c: CallbackQuery, state: FSMContext):
    """
    Handle saving an item as a new product.
    """
    # Get data from state
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    position_idx = selected_issue.get("index", 0) - 1
    
    # Mark as fixed
    fixed_issues = data.get("fixed_issues", {})
    if not fixed_issues:
        fixed_issues = {}
    
    fixed_issues[position_idx] = {"action": "new_product"}
    await state.update_data(fixed_issues=fixed_issues)
    
    # Log the action
    try:
        invoice_id = invoice_data.get("id", 0)
        user_id = c.from_user.id if c.from_user else 0
        item_name = selected_issue.get("original", {}).get("name", "")
        
        await log_save_new(
            invoice_id=invoice_id,
            row_idx=position_idx,
            user_id=user_id,
            item_name=item_name
        )
    except Exception as e:
        logger.error("Failed to log save_new action", error=str(e))
    
    # Return to issue list
    await state.set_state(InvoiceEditStates.issue_list)
    
    # Get updated issues
    current_issues = data.get("current_issues", [])
    
    # Update issue list to show fixed status
    from app.routers.issue_editor import format_issues_list
    message, keyboard = await format_issues_list(
        {"issues": current_issues}, 
        page=data.get("current_page", 0)
    )
    
    message = "✅ Item saved as new product.\n\n" + message
    
    await c.message.edit_text(
        message,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await c.answer("Saved as new product")


@router.callback_query(IssueCallback.filter(F.action == "delete"))
async def handle_delete_row(c: CallbackQuery, state: FSMContext):
    """
    Handle deleting a row from the invoice.
    """
    # Get data from state
    data = await state.get_data()
    selected_issue = data.get("selected_issue", {})
    invoice_data = data.get("invoice", {})
    positions = invoice_data.get("positions", [])
    position_idx = selected_issue.get("index", 0) - 1
    
    if 0 <= position_idx < len(positions):
        # Mark as deleted rather than removing
        positions[position_idx]["deleted"] = True
        
        # Update data in state
        invoice_data["positions"] = positions
        await state.update_data(invoice=invoice_data)
        
        # Mark as fixed
        fixed_issues = data.get("fixed_issues", {})
        if not fixed_issues:
            fixed_issues = {}
        
        fixed_issues[position_idx] = {"action": "delete"}
        await state.update_data(fixed_issues=fixed_issues)
        
        # Log the deletion
        try:
            invoice_id = invoice_data.get("id", 0)
            user_id = c.from_user.id if c.from_user else 0
            item_name = selected_issue.get("original", {}).get("name", "")
            
            await log_delete(
                invoice_id=invoice_id,
                row_idx=position_idx,
                user_id=user_id,
                item_name=item_name
            )
        except Exception as e:
            logger.error("Failed to log delete action", error=str(e))
        
        # Return to issue list
        await state.set_state(InvoiceEditStates.issue_list)
        
        # Get updated issues
        current_issues = data.get("current_issues", [])
        issue_idx = data.get("selected_issue_idx", 0)
        
        # Remove the deleted issue from current issues
        current_issues = [issue for i, issue in enumerate(current_issues) if i != issue_idx]
        await state.update_data(current_issues=current_issues)
        
        # Format updated issue list
        from app.routers.issue_editor import format_issues_list
        message, keyboard = await format_issues_list(
            {"issues": current_issues}, 
            page=data.get("current_page", 0)
        )
        
        message = "✅ Item deleted from invoice.\n\n" + message
        
        await c.message.edit_text(
            message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await c.answer("❌ Error: Invalid position")
    
    await c.answer()


@router.callback_query(IssueCallback.filter(F.action == "review_back"))
async def handle_back_to_issues(c: CallbackQuery, state: FSMContext):
    """
    Handle going back to the issue list.
    """
    # Return to issue list
    await state.set_state(InvoiceEditStates.issue_list)
    
    # Get data from state
    data = await state.get_data()
    current_issues = data.get("current_issues", [])
    
    # Format issue list
    from app.routers.issue_editor import format_issues_list
    message, keyboard = await format_issues_list(
        {"issues": current_issues}, 
        page=data.get("current_page", 0)
    )
    
    await c.message.edit_text(
        message,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await c.answer()


# Register handlers in the router
def setup_edit_handlers(main_router: Router):
    """
    Register all edit handlers with the main router.
    
    Args:
        main_router: The main aiogram router
    """
    main_router.include_router(router)
