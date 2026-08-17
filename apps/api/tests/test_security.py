from __future__ import annotations

import pytest

from veris_api.security import PasswordPolicyError, normalize_password


def test_password_policy_accepts_all_required_character_classes() -> None:
    assert normalize_password("Valid1!x") == "Valid1!x"


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("Short1!", "at least 8 characters"),
        ("lowercase1!", "an uppercase letter"),
        ("UPPERCASE1!", "a lowercase letter"),
        ("NoNumber!", "a number"),
        ("NoSymbol1", "a symbol"),
        ("Password1 ", "a symbol"),
    ],
)
def test_password_policy_explains_missing_requirement(password: str, expected: str) -> None:
    with pytest.raises(PasswordPolicyError, match=expected):
        normalize_password(password)
