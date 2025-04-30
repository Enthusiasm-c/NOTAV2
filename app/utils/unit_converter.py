"""
Unit conversion module for invoice processing.

This module provides functionality for normalizing and converting units of measurement.
It supports various unit types including volume, weight, and countable items.
The module handles both English and Indonesian unit aliases.

Example:
    >>> from app.utils.unit_converter import normalize_unit, convert
    >>> normalize_unit("liter")  # Returns "l"
    >>> convert(1000, "ml", "l")  # Returns 1.0
"""

from typing import Dict, Tuple, Optional, Set

# Unit normalization dictionary
UNIT_ALIASES: Dict[str, str] = {
    # English volume units
    "l": "l", "ltr": "l", "liter": "l", "liters": "l", "litre": "l", "litres": "l",
    "ml": "ml", "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    
    # English weight units
    "kg": "kg", "kilo": "kg", "kilogram": "kg", "kilograms": "kg",
    "g": "g", "gr": "g", "gram": "g", "grams": "g",
    
    # English countable units
    "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs",
    "pack": "pack", "package": "pack", "pkg": "pack",
    "box": "box", "boxes": "box",
    
    # Indonesian volume units
    "liter": "l", "lt": "l",
    "mililiter": "ml", "mili": "ml",
    
    # Indonesian weight units
    "kilogram": "kg", "kilo": "kg",
    "gram": "g",
    
    # Indonesian countable units
    "buah": "pcs", "biji": "pcs", "pcs": "pcs", "potong": "pcs",
    "paket": "pack", "pak": "pack",
    "kotak": "box", "dus": "box", "kardus": "box",
    
    # Common abbreviations
    "ea": "pcs",  # each
    "btl": "pcs",  # bottle/botol
}

# Conversion factors between units
CONVERSION_FACTORS: Dict[Tuple[str, str], float] = {
    ("ml", "l"): 0.001,
    ("l", "ml"): 1000,
    ("g", "kg"): 0.001,
    ("kg", "g"): 1000,
}

# Unit categories for compatibility checking
VOLUME_UNITS: Set[str] = {"l", "ml"}
WEIGHT_UNITS: Set[str] = {"kg", "g"}
COUNTABLE_UNITS: Set[str] = {"pcs", "pack", "box"}

def normalize_unit(unit_str: str) -> str:
    """
    Normalize unit string to standard format.
    
    Args:
        unit_str: Input unit string to normalize
        
    Returns:
        Normalized unit string (e.g., "liter" -> "l")
        
    Example:
        >>> normalize_unit("liter")
        'l'
        >>> normalize_unit("KILOGRAM")
        'kg'
    """
    if not unit_str:
        return ""
    
    unit_str = unit_str.lower().strip()
    return UNIT_ALIASES.get(unit_str, unit_str)

def convert(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    """
    Convert value from one unit to another.
    
    Args:
        value: Source value to convert
        from_unit: Source unit
        to_unit: Target unit
        
    Returns:
        Converted value or None if conversion is not possible
        
    Example:
        >>> convert(1000, "ml", "l")
        1.0
        >>> convert(1, "kg", "g")
        1000.0
    """
    from_unit = normalize_unit(from_unit)
    to_unit = normalize_unit(to_unit)
    
    # If units already match
    if from_unit == to_unit:
        return value
    
    # Find conversion factor
    factor = CONVERSION_FACTORS.get((from_unit, to_unit))
    if factor is not None:
        return value * factor
    
    # No conversion found
    return None

def is_compatible_unit(unit1: str, unit2: str) -> bool:
    """
    Check if two units are compatible (can be converted between each other).
    
    Args:
        unit1: First unit to check
        unit2: Second unit to check
        
    Returns:
        True if units are compatible, False otherwise
        
    Example:
        >>> is_compatible_unit("ml", "l")
        True
        >>> is_compatible_unit("kg", "pcs")
        False
    """
    unit1 = normalize_unit(unit1)
    unit2 = normalize_unit(unit2)
    
    # Same normalized units are always compatible
    if unit1 == unit2:
        return True
    
    # Check if there's a direct conversion factor
    if (unit1, unit2) in CONVERSION_FACTORS or (unit2, unit1) in CONVERSION_FACTORS:
        return True
    
    # Check unit categories
    if unit1 in VOLUME_UNITS and unit2 in VOLUME_UNITS:
        return True
    if unit1 in WEIGHT_UNITS and unit2 in WEIGHT_UNITS:
        return True
    if unit1 in COUNTABLE_UNITS and unit2 in COUNTABLE_UNITS:
        # Countable units technically aren't directly convertible without 
        # additional knowledge (e.g., how many pieces in a pack)
        return False
    
    return False 