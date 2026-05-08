from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


def _coerce_decimal(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _format_decimal(value, places: int) -> str:
    quantizer = Decimal('1').scaleb(-places)
    decimal_value = _coerce_decimal(value).quantize(quantizer, rounding=ROUND_HALF_UP)
    return format(decimal_value, f',.{places}f')


@register.filter(name='money')
def money(value) -> str:
    return _format_decimal(value, 2)


@register.filter(name='number')
def number(value) -> str:
    return _format_decimal(value, 0)


@register.filter(name='pct')
def pct(value) -> str:
    return f"{_format_decimal(value, 2)}%"
