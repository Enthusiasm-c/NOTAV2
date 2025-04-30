"""Константы приложения."""

# Настройки базы данных
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./nota.db"
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Настройки Telegram бота
DEFAULT_TELEGRAM_BOT_TOKEN = None
DEFAULT_TELEGRAM_CHAT_ID = None

# Настройки OpenAI
DEFAULT_OPENAI_API_KEY = None
DEFAULT_OPENAI_MODEL = "gpt-3.5-turbo"

# Настройки Anthropic
DEFAULT_ANTHROPIC_API_KEY = None
DEFAULT_ANTHROPIC_MODEL = "claude-3-opus"

# Настройки приложения
APP_NAME = "NOTA"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Система учета накладных и товаров"
APP_AUTHOR = "Denis"
APP_EMAIL = "denis@example.com"

# Настройки логирования
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Настройки API
API_PREFIX = "/api"
API_VERSION = "v1"
API_TITLE = f"{APP_NAME} API"
API_DESCRIPTION = f"API для {APP_DESCRIPTION}"

# Настройки безопасности
SECRET_KEY = "your-secret-key-here"  # Заменить на реальный ключ
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Настройки кэширования
CACHE_TTL = 3600  # 1 час
CACHE_PREFIX = "nota:"

# Настройки поиска
FUZZY_MATCH_THRESHOLD = 80  # Порог совпадения для нечеткого поиска
MAX_SEARCH_RESULTS = 10  # Максимальное количество результатов поиска

# Настройки валидации
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 32
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32

# Настройки файлов
UPLOAD_DIR = "uploads"
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Настройки уведомлений
NOTIFICATION_TYPES = {
    "invoice_created": "Создана новая накладная",
    "invoice_updated": "Накладная обновлена",
    "invoice_deleted": "Накладная удалена",
    "product_created": "Создан новый товар",
    "product_updated": "Товар обновлен",
    "product_deleted": "Товар удален",
    "supplier_created": "Создан новый поставщик",
    "supplier_updated": "Поставщик обновлен",
    "supplier_deleted": "Поставщик удален",
} 