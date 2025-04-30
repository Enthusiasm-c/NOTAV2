"""
Константы для модуля issue_editor.

Этот модуль содержит все константы, используемые в issue_editor и его подмодулях.
"""

# Размер страницы для пагинации
PAGE_SIZE = 5

# Префиксы для callback-данных
CB_ISSUE_PREFIX = "issue:"
CB_PAGE_PREFIX = "page:"
CB_PRODUCT_PREFIX = "product:"
CB_ACTION_PREFIX = "action:"
CB_UNIT_PREFIX = "unit:"
CB_CONVERT_PREFIX = "convert:"

# Действия
CB_ADD_NEW = "add_new"
CB_ADD_ALL = "add_all_missing"
CB_SEARCH = "search"
CB_BACK = "back"
CB_CANCEL = "cancel"
CB_CONFIRM = "inv_ok"        # Для совместимости с существующим кодом
CB_REVIEW = "review"

# Константы для полуфабрикатов
SEMIFINISHED_PATTERNS = [
    r's/f',
    r's/finished',
    r'semi.?finished',
    r'semi.?fabricated'
]

# Минимальная уверенность для автообучения
MIN_CONFIDENCE_FOR_LEARNING = 0.90

# Пороговые значения для нечеткого поиска
FUZZY_MATCH_THRESHOLD = 0.7
MAX_SIMILAR_PRODUCTS = 3 