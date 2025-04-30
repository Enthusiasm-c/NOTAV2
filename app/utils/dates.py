"""
Модуль для работы с датами и временем.
Адаптирован для индонезийского рынка.
"""

from datetime import datetime, date, timedelta
from typing import Optional, Union, List, Dict
import pytz
import json
from pathlib import Path

# Загружаем индонезийские праздники
HOLIDAYS_FILE = Path(__file__).parent.parent / "data" / "id_holidays.json"

def load_holidays() -> Dict[str, str]:
    """Загружает список индонезийских праздников."""
    try:
        with open(HOLIDAYS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Загружаем праздники при импорте модуля
INDONESIAN_HOLIDAYS = load_holidays()

def get_current_date() -> date:
    """Возвращает текущую дату."""
    return date.today()

def get_current_datetime() -> datetime:
    """Возвращает текущую дату и время."""
    return datetime.now()

def parse_date(date_str: str, format: str = "%Y-%m-%d") -> Optional[date]:
    """Парсит строку в дату."""
    try:
        return datetime.strptime(date_str, format).date()
    except ValueError:
        return None

def format_date(d: date, format: str = "%d.%m.%Y") -> str:
    """Форматирует дату в строку."""
    return d.strftime(format)

def format_datetime(dt: datetime, format: str = "%d.%m.%Y %H:%M") -> str:
    """Форматирует дату и время в строку."""
    return dt.strftime(format)

def add_days(d: date, days: int) -> date:
    """Добавляет указанное количество дней к дате."""
    return d + timedelta(days=days)

def add_months(d: date, months: int) -> date:
    """Добавляет указанное количество месяцев к дате."""
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)

def get_date_range(start_date: date, end_date: date) -> List[date]:
    """Возвращает список дат в указанном диапазоне."""
    dates = []
    current_date = start_date
    while current_date <= end_date:
        dates.append(current_date)
        current_date = add_days(current_date, 1)
    return dates

def is_weekend(d: date) -> bool:
    """Проверяет, является ли дата выходным днем."""
    return d.weekday() >= 5

def is_holiday(d: date) -> bool:
    """Проверяет, является ли дата индонезийским праздником."""
    date_str = d.strftime("%Y-%m-%d")
    return date_str in INDONESIAN_HOLIDAYS

def get_holiday_name(d: date) -> Optional[str]:
    """Возвращает название индонезийского праздника, если дата является праздником."""
    date_str = d.strftime("%Y-%m-%d")
    return INDONESIAN_HOLIDAYS.get(date_str)

def is_workday(d: date) -> bool:
    """Проверяет, является ли дата рабочим днем."""
    return not (is_weekend(d) or is_holiday(d))

def get_next_workday(d: date) -> date:
    """Возвращает следующий рабочий день."""
    next_day = add_days(d, 1)
    while not is_workday(next_day):
        next_day = add_days(next_day, 1)
    return next_day

def get_previous_workday(d: date) -> date:
    """Возвращает предыдущий рабочий день."""
    prev_day = add_days(d, -1)
    while not is_workday(prev_day):
        prev_day = add_days(prev_day, -1)
    return prev_day

def convert_timezone(dt: datetime, from_tz: str, to_tz: str) -> datetime:
    """Конвертирует время между часовыми поясами."""
    from_zone = pytz.timezone(from_tz)
    to_zone = pytz.timezone(to_tz)
    
    # Локализуем время в исходной временной зоне
    localized_dt = from_zone.localize(dt)
    
    # Конвертируем в целевую временную зону
    return localized_dt.astimezone(to_zone)

def get_workdays_in_range(start_date: date, end_date: date) -> List[date]:
    """Возвращает список рабочих дней в указанном диапазоне."""
    return [d for d in get_date_range(start_date, end_date) if is_workday(d)]

def get_holidays_in_range(start_date: date, end_date: date) -> Dict[date, str]:
    """Возвращает словарь праздников в указанном диапазоне."""
    holidays = {}
    for d in get_date_range(start_date, end_date):
        if is_holiday(d):
            holidays[d] = get_holiday_name(d)
    return holidays 