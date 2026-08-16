from __future__ import annotations

NEMOTRON_3_ULTRA_FREE = "nvidia/nemotron-3-ultra-550b-a55b:free"
NEMOTRON_3_SUPER_FREE = "nvidia/nemotron-3-super-120b-a12b:free"
GEMMA_4_26B_A4B_FREE = "google/gemma-4-26b-a4b-it:free"
GPT_OSS_120B = "openai/gpt-oss-120b"

APPROVED_OPENROUTER_MODELS = frozenset(
    {
        NEMOTRON_3_ULTRA_FREE,
        NEMOTRON_3_SUPER_FREE,
        GEMMA_4_26B_A4B_FREE,
        GPT_OSS_120B,
    }
)
PAID_OPENROUTER_MODELS = frozenset({GPT_OSS_120B})

DEFAULT_OPENROUTER_MODEL = NEMOTRON_3_ULTRA_FREE
DEFAULT_OPENROUTER_FALLBACK_MODELS = (
    NEMOTRON_3_SUPER_FREE,
    GEMMA_4_26B_A4B_FREE,
)


def validate_model_route(
    primary: str,
    fallbacks: tuple[str, ...],
    *,
    allow_paid: bool,
) -> None:
    route = (primary, *fallbacks)
    unknown = set(route) - APPROVED_OPENROUTER_MODELS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"OpenRouter route contains unapproved models: {names}")

    if len(route) != len(set(route)):
        raise ValueError("OpenRouter route contains duplicate models")

    paid = set(route) & PAID_OPENROUTER_MODELS
    if paid and not allow_paid:
        names = ", ".join(sorted(paid))
        raise ValueError(
            "Paid OpenRouter models require OPENROUTER_ALLOW_PAID_MODELS=true: " f"{names}"
        )
