"""
Производственный календарь РФ. Основан на данных проекта http://xmlcalendar.ru
Встроенные функции кеширования загруженных календарей и повторного выкачивания апдейта при устаревании копии в локальном кеше.

Пример использования:

>>> from ProdCalendar import ProdCalendar
>>> from datetime import date, time, timedelta, datetime
>>> 
>>> workCalendar = ProdCalendar(cache_dir='.cache/', cacheTTL=timedelta(days=5))
>>> dt = datetime(2025, 12, 31)
>>> workCalendar.isWorkDay(dt)  # -> False
False
>>> workCalendar.isHoliday(dt)  # -> True
True
"""

from datetime import date, timedelta, datetime, timezone
from pathlib import Path
import json
import logging
import requests

from ._version import __version__


class ProdCalServiceNotRespond(Exception):
    """Exception для случаев ошибки скачивания обновлений"""
    pass


class ProdCalError(Exception):
    """Exception для всех остальных ошибок при работе с календарём"""
    pass


class ProdCalendar:
    """Производственный календарь на основе обновляемых данных с сайта http://xmlcalendar.ru/"""
    URL_CAL_MAIN = r'http://xmlcalendar.ru/data/ru/'  # URL, используемый для выкачивания обновлений календаря
    CACHE_FILE_NAME = '%sprod_calend_%i_%s.json'
    CACHE_DWNLD_DT_FORMAT = '%Y-%m-%d %H:%M:%S'
    _cache_data = None
    COUNTRY_CODE = 'RU'

    def __init__(self, cache: bool = True, cache_dir: str = '.cache/', preload_year: int = date.today().year,
        cacheTTL: timedelta = timedelta(days=60),
        overrideDates: dict[date, int] = {}):
        """Инициализация класса производственного календаря.
        
        Args:
            cache (bool): включить кеширование (default: ``True``)
            cache_dir (str): каталог для файлов кеша (default: '.cache/')
            preload_year (int): предзагрузка указанного года (default: ``date.today().year``)
            cacheTTL (timedelta): время жизни кешированных данных (default: ``datetime.timedelta(days)``)
            overrideDates (dict[datetime.date, int]): переназначение отдельных дат. Необходимо передать массив в котором ключом
                                            является дата (``datetime.date``), а значением ``int`` (0 - рабочий день, 1 - выходной)
        """
        self.isCache = cache
        self.cache_dir = cache_dir
        self.cacheTTL = cacheTTL
        self.overrided_dates = overrideDates
        if self.isCache and preload_year:
            self.cache_year(preload_year, forced=False)

    def isWorkDay(self, day: date) -> bool:
        """Проверяет, что переданная дата - это рабочий день"""
        if day in self.overrided_dates:
            return not bool(self.overrided_dates[day])
        cal_year = self._getYear(day.year)
        cal_m = next((x for x in cal_year['months'] if x['month'] == day.month), None)
        if cal_m is None:  # на случай, если есть непредусмотренный сбой и месяц отсутствует в загруженных данных
            return day.weekday() < 5
        # Все нерабочие дни месяца перечислены в массиве 'days_int'.
        if day.day in cal_m['days_int']:
            return False
        return True

    def isHoliday(self, day: date) -> bool:
        """Проверяет, что переданная дата - это **выходной** или **праздничный** день"""
        return not self.isWorkDay(day)

    def _getYear(self, year: int) -> dict:
        if self.isCache:
            if self._is_cache_mem_data_valid() and self._cache_data['year'] == year:
                return self._cache_data
            cache_file = Path(self.cacheFPath(year))
            cal_year = self._get_cache(year)
            if not self._is_cache_file_valid(cache_file) or cal_year is None:
                cal_year = self.cache_year(year, forced=True)
            return cal_year
        else:
            return self._downloadYear(year)

    def cacheFPath(self, year: int) -> str:
        """Путь до файла кеша. Служебная функция."""
        return Path(self.CACHE_FILE_NAME % (self.cache_dir, year, self.COUNTRY_CODE))

    def _downloadYear(self, year: int) -> dict:
        url = self.URL_CAL_MAIN + str(year) + '/calendar.json'
        logging.debug(f"ProdCalendar. Downloading new {url}")
        try:
            resp = requests.get(url)
        except requests.exceptions.RequestException:
            logging.debug("Error downloading JSON data")
            raise ProdCalServiceNotRespond
        if resp.status_code != 200:
            logging.debug("Error downloading JSON data")
            raise ProdCalServiceNotRespond
        cal = resp.json()
        if year != cal['year'] or 'months' not in cal:
            logging.debug("Downloaded calendar data is corrupted")
            raise ProdCalError("Downloaded calendar data is corrupted")
        cal['downloaded_dt_utc'] = datetime.utcnow().strftime(self.CACHE_DWNLD_DT_FORMAT)
        # некоторые дни помечены знаками + и * (предпраздничные дни и др.) Оставим только цифры для int()
        # '*' - рабочий и сокращенный день. '+' - нерабочий день (перенесенный за счет другогоб подробности в секции transitions)
        for m in cal['months']:
            m['days_int'] = [int(''.join([y for y in x if y.isdigit()])) for x in m['days'].split(',') if not x.endswith('*')]
        return cal

    def cache_year(self, year: int, forced: bool = True) -> dict:
        Path(self.cache_dir).mkdir(exist_ok=True, parents=True)
        cache_file = Path(self.cacheFPath(year))
        if forced or not cache_file.is_file():
            return self._write_cache(year, cache_file)
        elif not self._is_cache_file_valid(cache_file):
            logging.debug(f"ProdCalendar. Cache file {cache_file.absolute()} is expired.")
            return self._write_cache(year, cache_file)

    def _write_cache(self, year, cache_file) -> dict:
        calend = self._downloadYear(year)
        with open(cache_file.absolute(), 'w', encoding='utf-8') as f:
            json.dump(calend, f, ensure_ascii=False, indent=1)
        self._cache_data = calend
        return calend

    def _get_cache(self, year: int) -> dict:
        cache_file = Path(self.cacheFPath(year))
        if not cache_file.is_file() or not self._is_cache_file_valid(cache_file):
            return None
        with open(cache_file.absolute(), 'r', encoding='utf-8') as f:
            calend = json.load(f)
            self._cache_data = calend
            return calend

    def _is_cache_file_valid(self, cache_file) -> bool:
        if not cache_file.is_file():
            return False
        mtime = cache_file.stat().st_mtime
        mtime = datetime.fromtimestamp(mtime)
        return mtime + self.cacheTTL >= datetime.now()

    def _is_cache_mem_data_valid(self) -> bool:
        if not self._cache_data or 'downloaded_dt_utc' not in self._cache_data:
            return False
        dwnl_dt = datetime.strptime(self._cache_data['downloaded_dt_utc'], self.CACHE_DWNLD_DT_FORMAT)
        return dwnl_dt + self.cacheTTL >= datetime.utcnow()
