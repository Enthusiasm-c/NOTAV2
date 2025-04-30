#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import engine
from app.models import Base

print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

try:
    import app
    print("✅ Импорт app успешен")
    
    import app.models
    print("✅ Импорт app.models успешен")
    
    from app.models import Base
    print("✅ Импорт Base успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    
    # Проверить структуру директорий
    import os
    print("\nСтруктура директорий:")
    for root, dirs, files in os.walk(".", topdown=True, maxdepth=2):
        for name in dirs:
            print(os.path.join(root, name))
