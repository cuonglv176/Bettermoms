# -*- coding: utf-8 -*-
# Vietnamese diacritics normalization utility
# Copied from ntp_payment_support/utils/normalize.py to avoid cross-module dependency

# fmt: off
SOURCE_CHARACTERS = [
    '\u00c0', '\u00c1', '\u00c2', '\u00c3', '\u00c8', '\u00c9',
    '\u00ca', '\u00cc', '\u00cd', '\u00d2', '\u00d3', '\u00d4', '\u00d5',
    '\u00d9', '\u00da', '\u00dd', '\u00e0', '\u00e1', '\u00e2',
    '\u00e3', '\u00e8', '\u00e9', '\u00ea', '\u00ec', '\u00ed', '\u00f2',
    '\u00f3', '\u00f4', '\u00f5', '\u00f9', '\u00fa', '\u00fd',
    '\u0102', '\u0103', '\u0110', '\u0111', '\u0128', '\u0129',
    '\u0168', '\u0169', '\u01a0', '\u01a1', '\u01af', '\u01b0',
    '\u1ea0', '\u1ea1', '\u1ea2', '\u1ea3', '\u1ea4', '\u1ea5',
    '\u1ea6', '\u1ea7', '\u1ea8', '\u1ea9', '\u1eaa', '\u1eab',
    '\u1eac', '\u1ead', '\u1eae', '\u1eaf', '\u1eb0', '\u1eb1',
    '\u1eb2', '\u1eb3', '\u1eb4', '\u1eb5', '\u1eb6', '\u1eb7',
    '\u1eb8', '\u1eb9', '\u1eba', '\u1ebb', '\u1ebc', '\u1ebd',
    '\u1ebe', '\u1ebf', '\u1ec0', '\u1ec1', '\u1ec2', '\u1ec3',
    '\u1ec4', '\u1ec5', '\u1ec6', '\u1ec7', '\u1ec8', '\u1ec9',
    '\u1eca', '\u1ecb', '\u1ecc', '\u1ecd', '\u1ece', '\u1ecf',
    '\u1ed0', '\u1ed1', '\u1ed2', '\u1ed3', '\u1ed4', '\u1ed5',
    '\u1ed6', '\u1ed7', '\u1ed8', '\u1ed9', '\u1eda', '\u1edb',
    '\u1edc', '\u1edd', '\u1ede', '\u1edf', '\u1ee0', '\u1ee1',
    '\u1ee2', '\u1ee3', '\u1ee4', '\u1ee5', '\u1ee6', '\u1ee7',
    '\u1ee8', '\u1ee9', '\u1eea', '\u1eeb', '\u1eec', '\u1eed',
    '\u1eee', '\u1eef', '\u1ef0', '\u1ef1',
]

DESTINATION_CHARACTERS = [
    'A', 'A', 'A', 'A', 'E',
    'E', 'E', 'I', 'I', 'O', 'O', 'O', 'O', 'U', 'U', 'Y', 'a', 'a',
    'a', 'a', 'e', 'e', 'e', 'i', 'i', 'o', 'o', 'o', 'o', 'u', 'u',
    'y', 'A', 'a', 'D', 'd', 'I', 'i', 'U', 'u', 'O', 'o', 'U', 'u',
    'A', 'a', 'A', 'a', 'A', 'a', 'A', 'a', 'A', 'a', 'A', 'a', 'A',
    'a', 'A', 'a', 'A', 'a', 'A', 'a', 'A', 'a', 'A', 'a', 'E', 'e',
    'E', 'e', 'E', 'e', 'E', 'e', 'E', 'e', 'E', 'e', 'E', 'e', 'E',
    'e', 'I', 'i', 'I', 'i', 'O', 'o', 'O', 'o', 'O', 'o', 'O', 'o',
    'O', 'o', 'O', 'o', 'O', 'o', 'O', 'o', 'O', 'o', 'O', 'o', 'O',
    'o', 'O', 'o', 'U', 'u', 'U', 'u', 'U', 'u', 'U', 'u', 'U', 'u',
    'U', 'u', 'U', 'u',
]
# fmt: on

# Build lookup dict for O(1) character mapping instead of O(n) list.index()
_CHAR_MAP = dict(zip(SOURCE_CHARACTERS, DESTINATION_CHARACTERS))


def normalize_string(text):
    """Strip Vietnamese diacritics from text, converting to ASCII equivalents.

    Examples:
        normalize_string("Ha Noi") -> "Ha Noi"  (already ASCII)
        normalize_string("Thanh pho Ho Chi Minh") -> "Thanh pho Ho Chi Minh"
    """
    if not text:
        return ""
    return "".join(_CHAR_MAP.get(c, c) for c in text)
