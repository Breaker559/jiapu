"""Structured dates: preserve input, calculate only when the calendar is known."""
from datetime import date, timedelta
from functools import lru_cache
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from lunar_python import Lunar, Solar, LunarYear


@lru_cache(maxsize=20000)
def _lunar_to_solar(year, month, day, leap):
    try:
        value=Lunar.fromYmd(year,-month if leap else month,day).getSolar()
        return date(value.getYear(),value.getMonth(),value.getDay())
    except Exception as exc:
        raise ValueError('该农历年月日不存在') from exc


class LunarDate:
    """Small application adapter over the MIT-licensed lunar-python library."""
    def __init__(self,year,month,day,isLeapMonth=False):
        self.year,self.month,self.day,self.isLeapMonth=year,month,day,isLeapMonth
    def toSolarDate(self):return _lunar_to_solar(self.year,self.month,self.day,self.isLeapMonth)
    @staticmethod
    @lru_cache(maxsize=20000)
    def fromSolarDate(year,month,day):
        value=Solar.fromYmd(year,month,day).getLunar()
        return LunarDate(value.getYear(),abs(value.getMonth()),value.getDay(),value.getMonth()<0)
    @staticmethod
    @lru_cache(maxsize=300)
    def leapMonthForYear(year):return LunarYear.fromYear(year).getLeapMonth()


class FamilyDate(BaseModel):
    calendar: Literal['solar', 'lunar'] = 'solar'
    year: int | None = Field(default=None, ge=1, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    day: int | None = Field(default=None, ge=1, le=31)
    leap: bool = False
    approximate: bool = False
    original: str = Field(default='', max_length=200)

    @model_validator(mode='after')
    def valid(self):
        if self.day and not self.month:
            raise ValueError('填写日期前请先选择月份')
        if self.calendar == 'solar' and self.leap:
            raise ValueError('闰月仅适用于农历')
        if self.calendar == 'lunar' and self.day and self.day > 30:
            raise ValueError('农历日期不能超过三十')
        if self.month and self.day:
            if self.calendar == 'solar':
                date(self.year or 2000, self.month, self.day)
            elif self.year and 1900 <= self.year <= 2099:
                LunarDate(self.year, self.month, self.day, self.leap).toSolarDate()
        if self.calendar == 'lunar' and self.year and self.month and 1900 <= self.year <= 2099:
            if self.leap and LunarDate.leapMonthForYear(self.year) != self.month:
                raise ValueError('该农历年没有这个闰月')
        return self


MONTHS = ['正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '冬', '腊']
DAYS = ['初一','初二','初三','初四','初五','初六','初七','初八','初九','初十','十一','十二','十三','十四','十五','十六','十七','十八','十九','二十','廿一','廿二','廿三','廿四','廿五','廿六','廿七','廿八','廿九','三十']


def date_info(value: dict | FamilyDate | None) -> dict:
    d = value if isinstance(value, FamilyDate) else FamilyDate(**(value or {}))
    prefix = '约 ' if d.approximate else ''
    if not any([d.year, d.month, d.day]):
        return {'label': d.original or '日期不详', 'solar': None, 'lunar': None, 'note': '尚无可换算日期'}
    if d.calendar == 'solar':
        label = prefix + (f'{d.year}年' if d.year else '') + (f'{d.month}月' if d.month else '') + (f'{d.day}日' if d.day else '')
    else:
        label = prefix + '农历 ' + (f'{d.year}年' if d.year else '') + ('闰' if d.leap else '') + (MONTHS[d.month-1]+'月' if d.month else '') + (DAYS[d.day-1] if d.day else '')
    out = {'label': label, 'solar': None, 'lunar': None, 'note': ''}
    if not all([d.year, d.month, d.day]):
        out['note'] = '日期不完整，保留原始记载'
        return out
    try:
        if d.calendar == 'solar':
            solar = date(d.year, d.month, d.day)
            out['solar'] = solar.isoformat()
            if not date(1900,1,31) <= solar <= date(2099,12,31):
                raise ValueError()
            lunar = LunarDate.fromSolarDate(solar.year, solar.month, solar.day)
        else:
            if not 1900 <= d.year <= 2099:
                raise ValueError()
            lunar = LunarDate(d.year, d.month, d.day, d.leap)
            solar = lunar.toSolarDate()
            if not date(1900,1,31) <= solar <= date(2099,12,31):
                raise ValueError()
            out['solar'] = solar.isoformat()
        out['lunar'] = f'{lunar.year}年{"闰" if lunar.isLeapMonth else ""}{MONTHS[lunar.month-1]}月{DAYS[lunar.day-1]}'
    except (ValueError, IndexError):
        out['note'] = '超出双历转换范围（1900-01-31 至 2099-12-31），原始日期已保留'
    return out


def next_anniversary(value: dict, calendar: str = 'original', leap_policy: str = 'regular', missing: str = 'last', today: date | None = None):
    today = today or date.today()
    d = FamilyDate(**value)
    if not d.month or not d.day or d.approximate:
        return None
    target = d.calendar if calendar == 'original' else calendar
    if target != d.calendar:
        info = date_info(d)
        if not info['solar'] or not info['lunar']:
            return None
        converted = date.fromisoformat(info['solar'])
        if target == 'solar':
            month, day, leap = converted.month, converted.day, False
        else:
            ld = LunarDate.fromSolarDate(converted.year,converted.month,converted.day)
            month, day, leap = ld.month, ld.day, ld.isLeapMonth
    else:
        month, day, leap = d.month, d.day, d.leap
    found = []
    for year in range(today.year - 1, min(today.year+13,2100)):
        if target == 'solar':
            try:
                candidate = date(year,month,day)
            except ValueError:
                if missing == 'skip': continue
                candidate = date(year,3,1) if missing == 'next' else date(year,2,28)
            found.append(candidate)
        elif year >= 1900:
            lm = LunarDate.leapMonthForYear(year)
            variants = [False]
            if leap:
                variants = ([True] if lm == month else []) if leap_policy == 'only' else ([False,True] if lm == month and leap_policy == 'both' else [lm == month])
            for is_leap in variants:
                try:
                    candidate = LunarDate(year,month,day,is_leap).toSolarDate()
                except ValueError:
                    if day != 30 or missing == 'skip': continue
                    candidate = LunarDate(year,month,29,is_leap).toSolarDate()
                    if missing == 'next': candidate += timedelta(days=1)
                found.append(candidate)
        future = sorted(set(x for x in found if x >= today))
        if future:
            return {'date': future[0].isoformat(), 'days': (future[0]-today).days, 'calendar': target}
    return None
