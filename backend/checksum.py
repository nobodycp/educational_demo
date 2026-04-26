"""
Educational checksum utilities.

Maps the classic **Luhn (mod 10)** algorithm used for payment-card integrity checks
to a **Corporate Access Token** checksum in this lab. The mathematics are identical;
only the semantic framing changes for defensive-security coursework.
"""

from __future__ import annotations


def _luhn_sum_mod10(digits: str) -> int:
    """
    Luhn sum: walk from the right; index 0 = rightmost (check digit in a full PAN);
    double indices 1,3,5,…, then collapse >9. Sum must be 0 (mod 10) for a valid PAN.
    """
    total = 0
    for i, ch in enumerate(digits[::-1]):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total


def luhn_checksum_digit(ident: str) -> int | None:
    """
    Compute the Luhn check digit for a numeric *body* (no check digit) — same
    mod-10 rule as payment-card PANs (e.g. Visa test 4111…1 + check 1).
    """
    body = "".join(ch for ch in ident if ch.isdigit())
    if not body:
        return None
    return (10 - (_luhn_sum_mod10(body + "0") % 10)) % 10


def luhn_validate(ident: str) -> bool:
    """
    Validate a full digit string (including final check digit) with Luhn mod 10.
    Rejects the body+check split bug that used to mark ``4111 1111 1111 1111`` invalid.
    """
    digits = "".join(ch for ch in ident if ch.isdigit())
    if len(digits) < 2:
        return False
    return _luhn_sum_mod10(digits) % 10 == 0


def expected_cvv_len_for_pan(pan_digits: str) -> int:
    """
    Heuristic CVV width by first PAN digit: Amex and some ``3``-series issuers
    use 4-digit security codes; Visa (4), Mastercard (5), Discover (6) use 3.
    """
    d = "".join(c for c in (pan_digits or "") if c.isdigit())
    if not d:
        return 3
    first = d[0]
    if first == "3":
        return 4
    if first in "456":
        return 3
    return 3


def normalize_corporate_access_token(raw: str) -> str:
    """
    Strip non-digits from user input so spaces/dashes in a masked token still validate.

    **Original PHP logic:** `preg_replace('/\D+/', '', $input)` before checksum in kits.

    **Security concept:** *Input canonicalization* — attackers often fuzz separators;
    normalization reduces parser differentials between client and server.
    """
    return "".join(ch for ch in (raw or "") if ch.isdigit())
