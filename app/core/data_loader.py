"""
Модуль для загрузки и кеширования данных из CSV-файлов.

Заменяет работу с базой данных на чтение локальных CSV-файлов
для упрощения MVP-версии приложения.
"""
from __future__ import annotations

import structlog
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from functools import lru_cache
import json

import pandas as pd
from rapidfuzz import fuzz

from app.config.storage import get_data_dir
from app.core.csv_storage import CSVStorage

logger = structlog.get_logger()

# Пути к CSV файлам
DATA_DIR = Path("data")
SUPPLIERS_CSV = DATA_DIR / "base_suppliers.csv"
PRODUCTS_CSV = DATA_DIR / "base_products.csv"

# Глобальные DataFrame для кеширования данных
SUPPLIERS: Optional[pd.DataFrame] = None
PRODUCTS: Optional[pd.DataFrame] = None

# Глобальные переменные для кэширования данных
PRODUCTS_LIST: List[Dict[str, Any]] = []
SUPPLIERS_LIST: List[Dict[str, Any]] = []

# Инициализация хранилища
storage = CSVStorage(get_data_dir())

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
            
        # Загружаем данные, заменяя пустые значения на None
        SUPPLIERS = pd.read_csv(SUPPLIERS_CSV, na_values=['', 'nan', 'NaN'], keep_default_na=True)
        PRODUCTS = pd.read_csv(PRODUCTS_CSV, na_values=['', 'nan', 'NaN'], keep_default_na=True)
        
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
    
    # Получаем данные и заменяем NaN на None
    product_dict = matches.iloc[0].to_dict()
    return {k: None if pd.isna(v) else v for k, v in product_dict.items()}

async def load_data_async() -> None:
    """Загружает данные из CSV файлов."""
    global PRODUCTS_LIST, SUPPLIERS_LIST
    
    logger.info("Загрузка данных из CSV файлов...")
    
    try:
        PRODUCTS_LIST = await storage.load_products()
        SUPPLIERS_LIST = await storage.load_suppliers()
        
        logger.info(
            "Данные загружены",
            suppliers_count=len(SUPPLIERS_LIST),
            products_count=len(PRODUCTS_LIST)
        )
    except Exception as e:
        logger.error("Ошибка загрузки данных", error=str(e))
        raise

@lru_cache(maxsize=1000)
def get_product_alias_async(name: str) -> Optional[str]:
    """
    Возвращает стандартизированное название продукта.
    
    Args:
        name: Название продукта для поиска
        
    Returns:
        Optional[str]: Стандартизированное название или None если не найдено
    """
    name = name.lower().strip()
    logger.debug("searching_product", name=name, products_count=len(PRODUCTS_LIST))
    
    for product in PRODUCTS_LIST:
        logger.debug("checking_product", 
                    product_name=product["name"],
                    product_aliases=product["aliases"])
        
        if name == product["name"].lower():
            logger.debug("found_exact_match", name=name)
            return product["name"]
            
        if name in [a.lower() for a in product["aliases"]]:
            logger.debug("found_alias_match", 
                        name=name, 
                        product_name=product["name"])
            return product["name"]
            
    logger.debug("product_not_found", name=name)
    return None

@lru_cache(maxsize=1000)
def get_supplier_async(name: str) -> Optional[str]:
    """
    Возвращает стандартизированное название поставщика.
    
    Args:
        name: Название поставщика для поиска
        
    Returns:
        Optional[str]: Стандартизированное название или None если не найдено
    """
    name = name.lower().strip()
    logger.debug("searching_supplier", name=name, suppliers_count=len(SUPPLIERS_LIST))
    
    for supplier in SUPPLIERS_LIST:
        logger.debug("checking_supplier", 
                    supplier_name=supplier["name"],
                    supplier_aliases=supplier["aliases"])
        
        if name == supplier["name"].lower():
            logger.debug("found_exact_match", name=name)
            return supplier["name"]
            
        if name in [a.lower() for a in supplier["aliases"]]:
            logger.debug("found_alias_match", 
                        name=name, 
                        supplier_name=supplier["name"])
            return supplier["name"]
            
    logger.debug("supplier_not_found", name=name)
    return None

async def save_invoice(invoice_data: Dict[str, Any]) -> None:
    """
    Сохраняет данные накладной.
    
    Args:
        invoice_data: Данные накладной для сохранения
    """
    try:
        await storage.save_invoice(invoice_data)
        logger.info("Накладная сохранена", invoice_id=invoice_data.get("id"))
    except Exception as e:
        logger.error("Ошибка сохранения накладной", error=str(e))
        raise 