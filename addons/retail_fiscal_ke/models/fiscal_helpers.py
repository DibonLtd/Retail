"""Pure string and number helpers for fiscal payloads.

Ported from the Odoo 17 Novitus ESD module. Kept free of ORM access so they
can be tested directly: fiscal devices reject payloads containing characters
outside a narrow set, and silently truncate overlong fields, so these rules
are worth pinning down with tests.
"""

import re

# Devices accept letters, digits, spaces and full stops only.
_ALLOWED = re.compile(r"[^a-zA-Z0-9 \n.]")
_ALPHANUMERIC = re.compile(r"[^a-zA-Z0-9]")

# Product descriptions longer than this are truncated by the device.
MAX_ITEM_NAME = 40


def format_amount(value):
    """Format a monetary value the way the device expects: absolute, 2dp."""
    return "{:.2f}".format(abs(value or 0.0))


def sanitize(text, max_length=MAX_ITEM_NAME):
    """Strip characters the device rejects, then trim to ``max_length``."""
    if not text:
        return ""
    cleaned = _ALLOWED.sub("", text)
    return cleaned[:max_length] if max_length else cleaned


def alphanumeric_tail(text, limit):
    """Keep only alphanumerics, then take the last ``limit`` characters.

    Used for reference numbers, where the device has a short field and the
    distinguishing part of an Odoo reference is at the end: POS/2025/00042
    matters far more in its tail than its prefix.
    """
    if not text:
        return ""
    cleaned = _ALPHANUMERIC.sub("", text)
    return cleaned[-limit:] if limit else cleaned


def trim_item_name(name, max_length=MAX_ITEM_NAME):
    """Trim a product name, marking that it was shortened.

    Truncating silently would put two different products on a receipt under
    the same description, so an ellipsis makes the truncation visible.
    """
    if not name:
        return ""
    if len(name) <= max_length:
        return name
    return "%s.." % name[: max_length - 2]
