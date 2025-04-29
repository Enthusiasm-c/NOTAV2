"""
FSM states for invoice processing workflow.

This module defines the states used in the finite state machine (FSM)
for managing the flow of invoice processing.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class InvoiceStates(StatesGroup):
    """Base states for invoice processing."""
    upload = State()         # Waiting for photo upload
    ocr = State()            # OCR in progress
    preview = State()        # Showing invoice preview
    exporting = State()      # Exporting to Syrve
    complete = State()       # Processing completed


class InvoiceEditStates(StatesGroup):
    """States for editing invoice data."""
    summary = State()        # A. Invoice summary view
    issue_list = State()     # B. List of problematic items
    issue_review = State()   # C. Viewing single issue details
    edit_field = State()     # D. Choosing which field to edit
    input_value = State()    # E. Waiting for user input
    confirm_edit = State()   # F. Confirm changes
    field_input = State()    # Legacy state for backward compatibility
    
    # Legacy states for backward compatibility
    issue_edit = State()     # Old editor state
    product_select = State() # Product selection
    confirm = State()        # Final confirmation
    bulk_add = State()       # Mass add operations
