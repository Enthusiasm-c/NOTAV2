"""
Модуль для загрузки и кеширования данных из CSV-файлов.

Заменяет работу с базой данных на чтение локальных CSV-файлов
для упрощения MVP-версии приложения.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import pandas as pd
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Пути к CSV файлам
DATA_DIR = Path("data")
SUPPLIERS_CSV = DATA_DIR / "base_suppliers.csv"
PRODUCTS_CSV = DATA_DIR / "base_products.csv"

# Глобальные DataFrame для кеширования данных
SUPPLIERS: Optional[pd.DataFrame] = None
PRODUCTS: Optional[pd.DataFrame] = None

def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Загружает данные из CSV файлов в память.
    
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (suppliers_df, products_df)
    """
    global SUPPLIERS, PRODUCTS
    
    try:
        logger.info("Загрузка данных из CSV файлов...")
        
        if not SUPPLIERS_CSV.exists():
            raise FileNotFoundError(f"Файл поставщиков не найден: {SUPPLIERS_CSV}")
        if not PRODUCTS_CSV.exists():
            raise FileNotFoundError(f"Файл товаров не найден: {PRODUCTS_CSV}")
            
        SUPPLIERS = pd.read_csv(SUPPLIERS_CSV)
        PRODUCTS = pd.read_csv(PRODUCTS_CSV)
        
        # Проверяем наличие обязательных колонок
        required_supplier_cols = {"name", "id", "code"}
        required_product_cols = {"id", "name", "code", "measureName", "is_ingredient"}
        
        missing_supplier_cols = required_supplier_cols - set(SUPPLIERS.columns)
        missing_product_cols = required_product_cols - set(PRODUCTS.columns)
        
        if missing_supplier_cols:
            raise ValueError(f"Отсутствуют колонки в suppliers.csv: {missing_supplier_cols}")
        if missing_product_cols:
            raise ValueError(f"Отсутствуют колонки в products.csv: {missing_product_cols}")
        
        logger.info(
            "Данные загружены: %d поставщиков, %d товаров", 
            len(SUPPLIERS), len(PRODUCTS)
        )
        
        return SUPPLIERS, PRODUCTS
        
    except Exception as e:
        logger.error("Ошибка при загрузке данных: %s", str(e))
        raise

def get_supplier(name: str) -> Optional[Dict[str, Any]]:
    """
    Находит поставщика по имени.
    
    Args:
        name: Имя поставщика
        
    Returns:
        Dict[str, Any]: Данные поставщика или None
    """
    global SUPPLIERS
    if SUPPLIERS is None:
        load_data()
        
    # Ищем точное совпадение
    mask = SUPPLIERS["name"].str.lower() == name.lower()
    matches = SUPPLIERS[mask]
    
    if not matches.empty:
        return matches.iloc[0].to_dict()
        
    # Если точного совпадения нет, ищем по частичному
    ratios = SUPPLIERS["name"].apply(
        lambda x: fuzz.token_set_ratio(x.lower(), name.lower())
    )
    best_match_idx = ratios.argmax()
    
    if ratios[best_match_idx] >= 80:  # Порог схожести
        return SUPPLIERS.iloc[best_match_idx].to_dict()
        
    return None

def get_product_alias(alias: str) -> Optional[Dict[str, Any]]:
    """
    Находит товар по альтернативному названию.
    
    Args:
        alias: Альтернативное название товара
        
    Returns:
        Dict[str, Any]: Данные товара или None
    """
    global PRODUCTS
    if PRODUCTS is None:
        load_data()
        
    # Ищем точное совпадение
    mask = PRODUCTS["name"].str.lower() == alias.lower()
    matches = PRODUCTS[mask]
    
    if not matches.empty:
        return matches.iloc[0].to_dict()
        
    # Если точного совпадения нет, ищем по частичному
    ratios = PRODUCTS["name"].apply(
        lambda x: fuzz.token_set_ratio(x.lower(), alias.lower())
    )
    best_match_idx = ratios.argmax()
    
    if ratios[best_match_idx] >= 80:  # Порог схожести
        return PRODUCTS.iloc[best_match_idx].to_dict()
        
    return None

def get_product_details(product_id: int) -> Optional[Dict[str, Any]]:
    """
    Получает детали продукта по его ID.
    
    Args:
        product_id: ID продукта
        
    Returns:
        Dict[str, Any]: Данные продукта или None
    """
    global PRODUCTS
    if PRODUCTS is None:
        load_data()
    
    if not product_id:
        return None
    
    mask = PRODUCTS["id"] == product_id
    matches = PRODUCTS[mask]
    
    if matches.empty:
        return None
        
    return matches.iloc[0].to_dict() 