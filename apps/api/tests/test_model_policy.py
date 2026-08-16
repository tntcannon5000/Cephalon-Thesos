from __future__ import annotations

import pytest

from veris_api.model_policy import (
    DEFAULT_OPENROUTER_FALLBACK_MODELS,
    DEFAULT_OPENROUTER_MODEL,
    GPT_OSS_120B,
    validate_model_route,
)


def test_default_route_is_approved_and_free() -> None:
    validate_model_route(
        DEFAULT_OPENROUTER_MODEL,
        DEFAULT_OPENROUTER_FALLBACK_MODELS,
        allow_paid=False,
    )


def test_generic_free_router_is_rejected() -> None:
    with pytest.raises(ValueError, match="unapproved"):
        validate_model_route("openrouter/free", (), allow_paid=False)


def test_paid_model_requires_explicit_opt_in() -> None:
    with pytest.raises(ValueError, match="OPENROUTER_ALLOW_PAID_MODELS"):
        validate_model_route(GPT_OSS_120B, (), allow_paid=False)

    validate_model_route(GPT_OSS_120B, (), allow_paid=True)
