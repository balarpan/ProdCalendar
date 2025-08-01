# intended to use with pytest

from ProdCalendar import ProdCalendar
from datetime import date, time, timedelta, datetime

workCalendar = ProdCalendar(cache_dir='.cache/', cacheTTL=timedelta(days=30))

def test_2025_11_01():
    assert workCalendar.isHoliday(date(2025, 11, 1)) is False  # суббота 1 ноября 2025 объявлен рабочим днём

def test_2025_08_02():
    assert workCalendar.isHoliday(date(2025, 8, 2)) is True

def test_2025_05_05():
    assert workCalendar.isHoliday(date(2025, 5, 5)) is False

def test_2025_05_09():
    assert workCalendar.isHoliday(date(2025, 5, 9)) is True

def test_2025_12_31_wrk():
    assert workCalendar.isWorkDay(date(2025, 12, 31)) is False

def test_2025_12_31_hld():
    assert workCalendar.isHoliday(date(2025, 12, 31)) is True

def test_custom_wrk():
    customCalendar = ProdCalendar(cache_dir='.cache/', cacheTTL=timedelta(days=720), overrideDates={date(2025, 12, 31): 0})
    assert customCalendar.isWorkDay(date(2025, 12, 31)) is True
    assert customCalendar.isWorkDay(date(2025, 12, 30)) is True

def test_custom_hld():
    customCalendar = ProdCalendar(cache_dir='.cache/', cacheTTL=timedelta(days=720), overrideDates={date(2025, 12, 31): 0})
    assert customCalendar.isHoliday(date(2025, 12, 28)) is True
    assert customCalendar.isHoliday(date(2025, 12, 31)) is False
