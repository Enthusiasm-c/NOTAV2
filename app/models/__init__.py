"""Central export hub for all ORM models."""

from __future__ import annotations

from .product import Product            # noqa: F401
from .invoice import Invoice            # noqa: F401
from .invoice_item import InvoiceItem   # noqa: F401
from .invoice_name_lookup import InvoiceNameLookup  # noqa: F401
from .product_name_lookup import ProductNameLookup  # legacy alias  # noqa: F401

__all__ = [
    "Product",
    "Invoice",
    "InvoiceItem",
    "InvoiceNameLookup",
    "ProductNameLookup",  # alias for backward-compatibility
]
