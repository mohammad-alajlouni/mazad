"""Dates, times and numbers written the way the reference booklet writes them."""

from datetime import date, time
from decimal import Decimal, InvalidOperation

MONTHS_AR = (
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
)
MONTHS_EN = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
WEEKDAYS_AR = ("الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def as_date(value):
    if isinstance(value, date) or not value:
        return value or None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def as_time(value):
    if isinstance(value, time) or not value:
        return value or None
    try:
        return time.fromisoformat(str(value)[:8])
    except ValueError:
        return None


def auction_days(auction):
    if auction.get("auction_type") == "physical":
        day = as_date(auction.get("auction_date"))
        return day, day
    start = as_date(auction.get("auction_start_date"))
    return start, as_date(auction.get("auction_end_date")) or start


def clock(value, language):
    """10 : 00 صباحاً — the reference spaces the colon and names the period."""
    moment = as_time(value)
    if not moment:
        return ""
    hour = moment.hour % 12 or 12
    if language == "ar":
        return f"{hour:02d} : {moment.minute:02d} " + (
            "صباحاً" if moment.hour < 12 else "مساءً"
        )
    return f"{hour}:{moment.minute:02d} " + ("AM" if moment.hour < 12 else "PM")


def time_range(auction, language):
    start = clock(auction.get("start_time"), language)
    end = clock(auction.get("end_time"), language)
    return f"{start} - {end}" if start and end else start or end


def day_range(auction, language, weekday=True, suffix="", dash=" - "):
    """الإثنين 27 - 29 يوليو 2026 (weekday of the first day, shared month)."""
    start, end = auction_days(auction)
    if not start:
        return ""
    months = MONTHS_AR if language == "ar" else MONTHS_EN
    days = WEEKDAYS_AR if language == "ar" else WEEKDAYS_EN
    if not end or end == start:
        text = f"{start.day} {months[start.month - 1]} {start.year}"
    elif (start.year, start.month) == (end.year, end.month):
        text = f"{start.day}{dash}{end.day} {months[start.month - 1]} {start.year}"
    elif start.year == end.year:
        text = f"{start.day} {months[start.month - 1]} - {end.day} {months[end.month - 1]} {end.year}"
    else:
        text = (
            f"{start.day} {months[start.month - 1]} {start.year} - "
            f"{end.day} {months[end.month - 1]} {end.year}"
        )
    if weekday:
        text = f"{days[start.weekday()]} {text}"
    return text + suffix


def slash_date(value):
    """2026 / 07 / 29, as on the closing-time badge."""
    day = as_date(value)
    return f"{day.year} / {day.month:02d} / {day.day:02d}" if day else ""


def number(value, language="ar", grouping=False):
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return str(value)
    text = f"{amount.normalize():{',' if grouping else ''}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", "٫") if language == "ar" else text


def money(value, language="ar"):
    text = number(value, language, grouping=True)
    if not text:
        return ""
    return f"{text} ريال" if language == "ar" else f"SAR {text}"


def uses_digits(value):
    return any(c.isdigit() for c in str(value))
