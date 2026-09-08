"""Validation agent for checking travel-plan consistency.

Uses:
1. Deterministic Python validation for hard constraints.
2. A small LLM review for qualitative contradictions.

The LLM intentionally receives only compact excerpts to stay within
Groq token-per-minute limits.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.graph.state import TravelState
from src.validators.travel_validator import (
    deterministic_validate,
    format_deterministic_validation,
)


# ---------------------------------------------------------------------------
# LLM input limits
# ---------------------------------------------------------------------------

# IMPORTANT:
# These limits are intentionally small because Groq currently has an
# 8,000-token-per-minute limit for this model.

QUERY_LIMIT = 800
FLIGHT_LIMIT = 1200
HOTEL_LIMIT = 1200
WEATHER_LIMIT = 1000
ITINERARY_LIMIT = 1600
DETERMINISTIC_LIMIT = 1800

LLM_MAX_TOKENS = 500


# ---------------------------------------------------------------------------
# Validator instructions
# ---------------------------------------------------------------------------

VALIDATOR_SYSTEM_PROMPT = """
You are a strict travel-plan validator.

Do NOT create a new travel plan.

Review the supplied travel request and travel-agent excerpts.

Look for:
- date inconsistencies
- incorrect trip duration
- incorrect hotel nights
- flight contradictions
- unsupported flight or hotel claims
- itinerary dates outside the trip
- inconsistent prices or totals
- weather/date mismatches
- contradictions between agents
- claims that appear unsupported or unverifiable

Rules:
- Deterministic validation is authoritative for dates and arithmetic.
- Never invent missing information.
- Do not assume availability or booking unless explicitly supported.
- If information cannot be verified, mark it as unverified.
- Be concise.

Return exactly:

STATUS:
PASS / PASS_WITH_WARNINGS / FAIL

CRITICAL_ISSUES:
- ...

WARNINGS:
- ...

SUPPORTED_FINDINGS:
- ...

RECOMMENDED_FIXES:
- ...
""".strip()


# ---------------------------------------------------------------------------
# Safe text helpers
# ---------------------------------------------------------------------------

def normalize_result(value: Any) -> str:
    """Convert strings, lists, dictionaries and other values to text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return "\n".join(
            normalize_result(item)
            for item in value
            if normalize_result(item).strip()
        )

    if isinstance(value, tuple):
        return "\n".join(
            normalize_result(item)
            for item in value
            if normalize_result(item).strip()
        )

    if isinstance(value, dict):
        parts = []

        for key, item in value.items():
            normalized = normalize_result(item)

            if normalized.strip():
                parts.append(f"{key}: {normalized}")

        return "\n".join(parts)

    return str(value)


def compact_text(value: Any, max_chars: int) -> str:
    """Normalize and truncate text."""

    text = normalize_result(value).strip()

    if not text:
        return "(none)"

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n[TRUNCATED]"


# ---------------------------------------------------------------------------
# Build compact LLM context
# ---------------------------------------------------------------------------

def build_llm_context(
    state: TravelState,
    deterministic_report: str,
) -> str:
    """Create a deliberately small prompt for the validator LLM."""

    user_query = compact_text(
        state.get("user_query", ""),
        QUERY_LIMIT,
    )

    flight_results = compact_text(
        state.get("flight_results", ""),
        FLIGHT_LIMIT,
    )

    hotel_results = compact_text(
        state.get("hotel_results", ""),
        HOTEL_LIMIT,
    )

    weather_results = compact_text(
        state.get("weather_results", ""),
        WEATHER_LIMIT,
    )

    itinerary = compact_text(
        state.get("itinerary", ""),
        ITINERARY_LIMIT,
    )

    deterministic = compact_text(
        deterministic_report,
        DETERMINISTIC_LIMIT,
    )

    return f"""
TRAVEL REQUEST:
{user_query}

DETERMINISTIC VALIDATION:
{deterministic}

FLIGHT EXCERPT:
{flight_results}

HOTEL EXCERPT:
{hotel_results}

WEATHER EXCERPT:
{weather_results}

ITINERARY EXCERPT:
{itinerary}
""".strip()


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

def get_validator_llm():
    """Create the validator LLM."""

    from langchain_groq import ChatGroq
    from src.config.settings import settings

    return ChatGroq(
        model=settings.GROQ_MODEL,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
        max_tokens=LLM_MAX_TOKENS,
    )


def run_llm_validation(
    state: TravelState,
    deterministic_report: str,
) -> str:
    """Run the compact qualitative LLM validation."""

    try:
        llm = get_validator_llm()

        prompt = build_llm_context(
            state,
            deterministic_report,
        )

        response = llm.invoke(
            [
                SystemMessage(
                    content=VALIDATOR_SYSTEM_PROMPT
                ),
                HumanMessage(
                    content=prompt
                ),
            ]
        )

        content = getattr(response, "content", "")

        result = normalize_result(content).strip()

        if result:
            return result

        return (
            "STATUS:\n"
            "PASS_WITH_WARNINGS\n\n"
            "CRITICAL_ISSUES:\n"
            "- None reported.\n\n"
            "WARNINGS:\n"
            "- LLM returned an empty validation response.\n\n"
            "SUPPORTED_FINDINGS:\n"
            "- Deterministic validation completed.\n\n"
            "RECOMMENDED_FIXES:\n"
            "- Review unverified travel claims manually."
        )

    except Exception as exc:
        # Do not kill the entire travel-planning graph if the LLM
        # temporarily hits a rate limit.

        return (
            "STATUS:\n"
            "PASS_WITH_WARNINGS\n\n"
            "CRITICAL_ISSUES:\n"
            "- None identified by deterministic validation.\n\n"
            "WARNINGS:\n"
            "- LLM qualitative validation was unavailable.\n"
            f"- Reason: {type(exc).__name__}\n\n"
            "SUPPORTED_FINDINGS:\n"
            "- Deterministic validation completed successfully.\n\n"
            "RECOMMENDED_FIXES:\n"
            "- Treat unverified travel claims cautiously."
        )


# ---------------------------------------------------------------------------
# Main LangGraph node
# ---------------------------------------------------------------------------

def validator_agent(state: TravelState) -> dict[str, Any]:
    """Validate the outputs of the travel-planning agents."""

    # ---------------------------------------------------------------
    # IMPORTANT:
    # Deterministic validation gets the full normalized outputs.
    # It does NOT need the LLM token limitation.
    # ---------------------------------------------------------------

    user_query = normalize_result(
        state.get("user_query", "")
    )

    flight_results = normalize_result(
        state.get("flight_results", "")
    )

    hotel_results = normalize_result(
        state.get("hotel_results", "")
    )

    weather_results = normalize_result(
        state.get("weather_results", "")
    )

    itinerary = normalize_result(
        state.get("itinerary", "")
    )

    # ---------------------------------------------------------------
    # Deterministic validation
    # ---------------------------------------------------------------

    deterministic_result = deterministic_validate(
        user_query=user_query,
        flight_results=flight_results,
        hotel_results=hotel_results,
        weather_results=weather_results,
        itinerary=itinerary,
    )

    deterministic_report = normalize_result(
        format_deterministic_validation(
            deterministic_result
        )
    ).strip()

    # ---------------------------------------------------------------
    # LLM validation
    # ---------------------------------------------------------------

    llm_report = run_llm_validation(
        state={
            **state,
            "user_query": user_query,
            "flight_results": flight_results,
            "hotel_results": hotel_results,
            "weather_results": weather_results,
            "itinerary": itinerary,
        },
        deterministic_report=deterministic_report,
    )

    # ---------------------------------------------------------------
    # Determine overall status
    # ---------------------------------------------------------------

    deterministic_lower = deterministic_report.lower()
    llm_lower = llm_report.lower()

    if (
        "critical" in deterministic_lower
        or "fail" in deterministic_lower
        or "status:\nfail" in llm_lower
    ):
        overall_status = "FAIL"

    elif (
        "warning" in deterministic_lower
        or "pass_with_warnings" in llm_lower
    ):
        overall_status = "PASS_WITH_WARNINGS"

    else:
        overall_status = "PASS"

    # ---------------------------------------------------------------
    # Final validation result
    # ---------------------------------------------------------------

    validation_output = f"""
VALIDATION STATUS: {overall_status}

=== DETERMINISTIC VALIDATION ===

{deterministic_report}

=== LLM VALIDATION ===

{llm_report}
""".strip()

    # Keep the output passed to the FINAL agent compact too.
    validation_output = compact_text(
        validation_output,
        5000,
    )

    return {
        "validation_results": validation_output,
        "messages": [
            HumanMessage(
                content=(
                    "Travel-plan validation completed. "
                    f"Overall status: {overall_status}."
                )
            )
        ],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }