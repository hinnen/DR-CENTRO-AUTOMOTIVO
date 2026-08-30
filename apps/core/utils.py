"""Normalizações compartilhadas entre as apps."""

import re

DIGITS_RE = re.compile(r"\D+")


def only_digits(value: str | None) -> str:
    if not value:
        return ""
    return DIGITS_RE.sub("", value)


def normalize_phone(value: str | None) -> str:
    """Guarda telefone como dígitos, descartando o +55 quando redundante.

    Armazenar normalizado é o que permite detectar cliente duplicado de forma
    confiável, independente de como cada atendente digitou.
    """
    digits = only_digits(value)
    if len(digits) > 11 and digits.startswith("55"):
        digits = digits[2:]
    return digits[:11]


def format_phone(value: str | None) -> str:
    """Formata para exibição: (13) 99999-9999 ou (13) 3333-3333."""
    digits = normalize_phone(value)
    if len(digits) == 11:
        return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return digits


def format_cpf_cnpj(value: str | None) -> str:
    digits = only_digits(value)
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits


def humanize_duration(delta) -> str:
    """Converte timedelta em algo legível na operação: "1d 4h", "2h 18min"."""
    if delta is None:
        return "—"

    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 1:
        return "agora"

    days, rest = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(rest, 60)

    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}min" if minutes else f"{hours}h"
    return f"{minutes}min"
