"""
Compatibility layer for legacy imports.

Old code/tests expect:
    from app.models.product_name_lookup import ProductNameLookup

The real model is now `InvoiceNameLookup`.  
We export it under the previous name to avoid breaking changes.
"""

from __future__ import annotations

from .invoice_name_lookup import InvoiceNameLookup  # actual model

# legacy alias
ProductNameLookup = InvoiceNameLookup

__all__ = ["ProductNameLookup"]
