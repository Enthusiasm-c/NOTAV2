"""
FSM states for invoice processing workflow.

This module defines the states used in the finite state machine (FSM)
for managing the flow of invoice processing.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup
from enum import Enum, auto


class InvoiceStates(StatesGroup):
    """Base states for invoice processing."""
    upload = State()         # Waiting for photo upload
    ocr = State()            # OCR in progress
    preview = State()        # Showing invoice preview
    exporting = State()      # Exporting to Syrve
    complete = State()       # Processing completed


class InvoiceEditStates(Enum):
    """
    Состояния для процесса редактирования накладной.
    
    Attributes:
        issue_list: Просмотр списка проблем
        issue_edit: Редактирование конкретной проблемы
        product_select: Выбор товара
        field_input: Ввод значения поля
    """
    issue_list = auto()  # Просмотр списка проблем
    issue_edit = auto()  # Редактирование конкретной проблемы
    product_select = auto()  # Выбор товара
    field_input = auto()  # Ввод значения поля
