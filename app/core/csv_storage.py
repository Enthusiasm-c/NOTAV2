"""
Модуль для работы с данными в формате CSV.
Заменяет предыдущую SQL-реализацию.
"""
from __future__ import annotations

import csv
import json
import pathlib
from typing import List, Dict, Any, Optional
import aiofiles
import structlog

logger = structlog.get_logger()

class CSVStorage:
    def __init__(self, data_dir: pathlib.Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Пути к файлам
        self.products_file = data_dir / "products.csv"
        self.suppliers_file = data_dir / "suppliers.csv"
        self.invoices_file = data_dir / "invoices.csv"
        
        # Создаем файлы если их нет
        self._ensure_files_exist()
    
    def _ensure_files_exist(self) -> None:
        """Создает CSV файлы с заголовками если они не существуют."""
        headers = {
            self.products_file: ["id", "name", "aliases"],
            self.suppliers_file: ["id", "name", "aliases"],
            self.invoices_file: ["id", "supplier", "date", "number", "total_sum", "items"]
        }
        
        for file_path, header in headers.items():
            if not file_path.exists():
                with open(file_path, "w", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                logger.info("created_csv_file", file=str(file_path))
    
    async def load_products(self) -> List[Dict[str, Any]]:
        """Загружает список продуктов."""
        async with aiofiles.open(self.products_file, mode="r") as f:
            content = await f.read()
            logger.debug("products_file_content", content=content)
            reader = csv.DictReader(content.splitlines())
            products = list(reader)
            # Преобразуем строки JSON в списки
            for product in products:
                try:
                    product["aliases"] = json.loads(product["aliases"])
                except Exception as e:
                    logger.error("json_parse_error", 
                               error=str(e), 
                               aliases=product.get("aliases", "None"))
                    product["aliases"] = []
            logger.info("loaded_products", count=len(products), first_product=str(products[0]) if products else "None")
            return products
    
    async def load_suppliers(self) -> List[Dict[str, Any]]:
        """Загружает список поставщиков."""
        async with aiofiles.open(self.suppliers_file, mode="r") as f:
            content = await f.read()
            logger.debug("suppliers_file_content", content=content)
            reader = csv.DictReader(content.splitlines())
            suppliers = list(reader)
            # Преобразуем строки JSON в списки
            for supplier in suppliers:
                try:
                    supplier["aliases"] = json.loads(supplier["aliases"])
                except Exception as e:
                    logger.error("json_parse_error", 
                               error=str(e), 
                               aliases=supplier.get("aliases", "None"))
                    supplier["aliases"] = []
            logger.info("loaded_suppliers", count=len(suppliers), first_supplier=str(suppliers[0]) if suppliers else "None")
            return suppliers
    
    async def save_invoice(self, invoice_data: Dict[str, Any]) -> None:
        """Сохраняет данные накладной."""
        async with aiofiles.open(self.invoices_file, mode="a", newline="") as f:
            writer = csv.writer(f)
            # Преобразуем items в строку JSON для хранения
            items_str = json.dumps(invoice_data.get("items", []), ensure_ascii=False)
            row = [
                invoice_data.get("id", ""),
                invoice_data.get("supplier", ""),
                invoice_data.get("date", ""),
                invoice_data.get("number", ""),
                invoice_data.get("total_sum", ""),
                items_str
            ]
            await f.write(",".join(map(str, row)) + "\n")
            logger.info("saved_invoice", invoice_id=invoice_data.get("id", "unknown"))
            
    async def find_product_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Ищет продукт по имени или алиасу."""
        products = await self.load_products()
        name = name.lower()
        logger.debug("searching_product", name=name, products_count=len(products))
        
        for product in products:
            if name == product["name"].lower():
                logger.info("found_product_by_name", product=product)
                return product
            
            aliases = product.get("aliases", [])
            if not isinstance(aliases, list):
                try:
                    aliases = json.loads(aliases)
                except Exception as e:
                    logger.error("json_parse_error_in_search", 
                               error=str(e), 
                               aliases=aliases)
                    aliases = []
            
            if name in [a.lower() for a in aliases]:
                logger.info("found_product_by_alias", product=product, matching_alias=name)
                return product
                
        logger.debug("product_not_found", search_name=name)
        return None
    
    async def find_supplier_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Ищет поставщика по имени или алиасу."""
        suppliers = await self.load_suppliers()
        name = name.lower()
        logger.debug("searching_supplier", name=name, suppliers_count=len(suppliers))
        
        for supplier in suppliers:
            if name == supplier["name"].lower():
                logger.info("found_supplier_by_name", supplier=supplier)
                return supplier
            
            aliases = supplier.get("aliases", [])
            if not isinstance(aliases, list):
                try:
                    aliases = json.loads(aliases)
                except Exception as e:
                    logger.error("json_parse_error_in_search", 
                               error=str(e), 
                               aliases=aliases)
                    aliases = []
            
            if name in [a.lower() for a in aliases]:
                logger.info("found_supplier_by_alias", supplier=supplier, matching_alias=name)
                return supplier
                
        logger.debug("supplier_not_found", search_name=name)
        return None 