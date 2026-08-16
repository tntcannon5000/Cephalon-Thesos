from __future__ import annotations

from veris_api.prompts import ARCHIVES_UNAVAILABLE_COPY, OPERATIONAL_PROMPT


def test_archive_copy_is_generic() -> None:
    assert "inquiry" in ARCHIVES_UNAVAILABLE_COPY
    assert "cannot help with" not in ARCHIVES_UNAVAILABLE_COPY.lower()


def test_first_turn_title_instruction_is_bounded() -> None:
    assert "two-to-six word topic label" in OPERATIONAL_PROMPT
    assert "Otherwise set conversation_title to null" in OPERATIONAL_PROMPT


def test_display_name_is_explicitly_untrusted_and_sparse() -> None:
    assert "untrusted" in OPERATIONAL_PROMPT
    assert "Use it sparingly" in OPERATIONAL_PROMPT
