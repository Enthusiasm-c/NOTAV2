"""
Тесты для модуля dates.py
"""

import pytest
from datetime import datetime, date, timedelta
from app.utils.dates import (
    get_current_date,
    get_current_datetime,
    parse_date,
    format_date,
    format_datetime,
    add_days,
    add_months,
    get_date_range,
    is_weekend,
    is_holiday,
    get_holiday_name,
    is_workday,
    get_next_workday,
    get_previous_workday,
    convert_timezone,
    get_workdays_in_range,
    get_holidays_in_range
)

def test_get_current_date():
    """Тест получения текущей даты."""
    current_date = get_current_date()
    assert isinstance(current_date, date)
    assert current_date == date.today()

def test_get_current_datetime():
    """Тест получения текущей даты и времени."""
    current_datetime = get_current_datetime()
    assert isinstance(current_datetime, datetime)
    assert (datetime.now() - current_datetime).total_seconds() < 1

def test_parse_date():
    """Тест парсинга даты из строки."""
    # Корректный формат
    assert parse_date("2024-03-20") == date(2024, 3, 20)
    assert parse_date("20.03.2024", "%d.%m.%Y") == date(2024, 3, 20)
    
    # Некорректный формат
    assert parse_date("invalid") is None
    assert parse_date("20.03.2024") is None

def test_format_date():
    """Тест форматирования даты в строку."""
    test_date = date(2024, 3, 20)
    assert format_date(test_date) == "20.03.2024"
    assert format_date(test_date, "%Y-%m-%d") == "2024-03-20"

def test_format_datetime():
    """Тест форматирования даты и времени в строку."""
    test_datetime = datetime(2024, 3, 20, 15, 30)
    assert format_datetime(test_datetime) == "20.03.2024 15:30"
    assert format_datetime(test_datetime, "%Y-%m-%d %H:%M") == "2024-03-20 15:30"

def test_add_days():
    """Тест добавления дней к дате."""
    test_date = date(2024, 3, 20)
    assert add_days(test_date, 1) == date(2024, 3, 21)
    assert add_days(test_date, -1) == date(2024, 3, 19)
    assert add_days(test_date, 0) == test_date

def test_add_months():
    """Тест добавления месяцев к дате."""
    test_date = date(2024, 3, 20)
    assert add_months(test_date, 1) == date(2024, 4, 20)
    assert add_months(test_date, -1) == date(2024, 2, 20)
    assert add_months(test_date, 0) == test_date
    
    # Проверка перехода через год
    assert add_months(test_date, 10) == date(2025, 1, 20)
    
    # Проверка корректной обработки конца месяца
    test_date = date(2024, 1, 31)
    assert add_months(test_date, 1) == date(2024, 2, 29)  # 2024 - високосный год

def test_get_date_range():
    """Тест получения диапазона дат."""
    start_date = date(2024, 3, 20)
    end_date = date(2024, 3, 22)
    expected_dates = [
        date(2024, 3, 20),
        date(2024, 3, 21),
        date(2024, 3, 22)
    ]
    assert get_date_range(start_date, end_date) == expected_dates
    
    # Проверка пустого диапазона
    assert get_date_range(end_date, start_date) == []

def test_is_weekend():
    """Тест проверки выходного дня."""
    # Понедельник
    assert not is_weekend(date(2024, 3, 18))
    # Суббота
    assert is_weekend(date(2024, 3, 23))
    # Воскресенье
    assert is_weekend(date(2024, 3, 24))

def test_is_holiday():
    """Тест проверки индонезийских праздников."""
    # Обычный день
    assert not is_holiday(date(2024, 3, 20))
    # Новый год
    assert is_holiday(date(2024, 1, 1))
    # Ид аль-Фитр
    assert is_holiday(date(2024, 4, 10))
    assert is_holiday(date(2024, 4, 11))

def test_get_holiday_name():
    """Тест получения названия праздника."""
    # Обычный день
    assert get_holiday_name(date(2024, 3, 20)) is None
    # Новый год
    assert get_holiday_name(date(2024, 1, 1)) == "Tahun Baru 2024"
    # Ид аль-Фитр
    assert get_holiday_name(date(2024, 4, 10)) == "Hari Raya Idul Fitri 1445 Hijriyah"

def test_is_workday():
    """Тест проверки рабочего дня."""
    # Обычный рабочий день
    assert is_workday(date(2024, 3, 20))
    # Выходной
    assert not is_workday(date(2024, 3, 23))
    # Праздник
    assert not is_workday(date(2024, 1, 1))

def test_get_next_workday():
    """Тест получения следующего рабочего дня."""
    # Пятница -> Понедельник (если понедельник не праздник)
    assert get_next_workday(date(2024, 3, 22)) == date(2024, 3, 25)
    # Перед праздником -> следующий рабочий день после праздника
    assert get_next_workday(date(2024, 4, 9)) == date(2024, 4, 12)

def test_get_previous_workday():
    """Тест получения предыдущего рабочего дня."""
    # Понедельник -> Пятница (если пятница не праздник)
    assert get_previous_workday(date(2024, 3, 18)) == date(2024, 3, 15)
    # После праздника -> предыдущий рабочий день перед праздником
    assert get_previous_workday(date(2024, 4, 12)) == date(2024, 4, 9)

def test_convert_timezone():
    """Тест конвертации часовых поясов."""
    # Создаем время в UTC
    utc_time = datetime(2024, 3, 20, 12, 0)
    
    # Конвертируем в Джакарту (UTC+7)
    jakarta_time = convert_timezone(utc_time, "UTC", "Asia/Jakarta")
    assert jakarta_time.hour == 19
    
    # Конвертируем обратно в UTC
    back_to_utc = convert_timezone(jakarta_time, "Asia/Jakarta", "UTC")
    assert back_to_utc.hour == 12

def test_get_workdays_in_range():
    """Тест получения списка рабочих дней в диапазоне."""
    start_date = date(2024, 3, 18)  # Понедельник
    end_date = date(2024, 3, 22)    # Пятница
    workdays = get_workdays_in_range(start_date, end_date)
    assert len(workdays) == 5
    assert all(is_workday(d) for d in workdays)

def test_get_holidays_in_range():
    """Тест получения списка праздников в диапазоне."""
    start_date = date(2024, 3, 1)
    end_date = date(2024, 3, 31)
    holidays = get_holidays_in_range(start_date, end_date)
    assert len(holidays) == 2  # Nyepi и Wafat Isa Al Masih
    assert date(2024, 3, 11) in holidays
    assert date(2024, 3, 31) in holidays 