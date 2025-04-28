#!/usr/bin/env python3

import sys
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path}")

try:
    import app
    print("✅ Импорт app успешен")
    
    import app.models
    print("✅ Импорт app.models успешен")
    
    from app.models import Base
    print("✅ Импорт Base успешен")
    
    from app.db import engine
    print("✅ Импорт engine успешен")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    
    # Проверить структуру директорий
    import os
    print("\nСтруктура директорий:")
    for root, dirs, files in os.walk(".", topdown=True, maxdepth=2):
        for name in dirs:
            print(os.path.join(root, name))
