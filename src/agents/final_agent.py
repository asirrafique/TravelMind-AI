"""Formats validated travel-agent results into the final user-facing answer."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from src.agents.prompts import FINAL_AGENT_PROMPT, FINAL_SYSTEM_PROMPT
from src.clients.llm import get_llm
from src.graph.state import TravelState
from src.utils.async_utils import bump_llm_calls


# ---------------------------------------------------------------------------
# Context limits
# ---------------------------------------------------------------------------

# The final agent should NOT receive unlimited raw MCP/tool output.
# Keeping the context compact also protects the Groq TPM limit.

QUERY_LIMIT = 1200
FLIGHT_LIMIT = 2200
HOTEL_LIMIT = 2200
WEATHER_LIMIT = 1800
ITINERARY_LIMIT = 3000
VALIDATION_LIMIT = 3500


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_result(value: Any) -> str:
    """Convert arbitrary agent output into safe text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    if isinstance(value, list):
        parts = []

        for item in value:
            text = normalize_result(item).strip()

            if text:
                parts.append(text)

        return "\n".join(parts)

    if isinstance(value, tuple):
        parts = []

        for item in value:
            text = normalize_result(item).strip()

            if text:
                parts.append(text)

        return "\n".join(parts)

    if isinstance(value, dict):
        parts = []

        for key, item in value.items():
            text = normalize_result(item).strip()

            if text:
                parts.append(f"{key}: {text}")

        return "\n".join(parts)

    return str(value)


def compact_text(value: Any, max_chars: int) -> str:
    """Normalize and truncate an agent result."""

    text = normalize_result(value).strip()

    if not text:
        return "(no data returned)"

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n[OUTPUT TRUNCATED]"


# ---------------------------------------------------------------------------
# Final-agent safety instructions
# ---------------------------------------------------------------------------

FINAL_SAFETY_PROMPT = """
IMPORTANT FINAL-ANSWER RULES:

You are the final synthesis agent for a travel-planning system.

The information below comes from multiple agents and tools.

You MUST respect validation results.

1. NEVER invent flight times, flight numbers, airlines, fares,
   hotel availability, hotel prices, booking confirmations,
   weather forecasts, or transportation prices.

2. If the flight agent says UNVERIFIED or no flight data was returned,
   keep the flight information explicitly UNVERIFIED.

3. NEVER turn an estimated value into a confirmed value.

4. NEVER claim that something is booked, available, confirmed,
   or verified unless the supplied data explicitly supports it.

5. If flight data is UNVERIFIED or estimated, NEVER include any exact
   or approximate flight departure/arrival time in the final itinerary,
   even if it appears as an assumption, example, planning assumption,
   or itinerary estimate.

   Do NOT write things such as:
   - "arrive at ~15:30"
   - "depart at ~16:30"
   - "assuming arrival at 3:30 PM"
   - "based on an estimated 4:30 PM flight"

   Instead use flexible wording such as:
   - "after your confirmed flight arrival"
   - "before your confirmed departure"
   - "allow sufficient time to reach CDG"

   Flight duration may be shown only if explicitly supported by the
   supplied flight information, and it must remain clearly labeled
   as estimated when unverified.

6. If a price is an estimate, label it as an estimate.

7. If weather data is only available for one day, do not create
   weather forecasts for the remaining days.

8. If the validator identifies a contradiction, warning, or critical
   issue, clearly surface it in the final answer.

9. Prefer "unverified", "estimated", or "check before booking"
   over guessing.

10. The user's request should be answered completely, but accuracy
    is more important than filling every field.

11. Do not mention internal agent names, prompts, token limits,
    LangGraph state, or implementation details.

12. Do not claim to have made bookings.

13. Keep the final answer concise enough to remain readable.

14. Use markdown tables only where they genuinely improve clarity.

15. For the budget, make the estimate internally consistent:
    - Clearly label whether each amount is per person, per room/stay,
      or for the full group.
    - Keep hotel cost consistent with the requested number of nights.
    - Base meals, transport, and attractions on the itinerary
      instead of arbitrary figures.
    - Prefer ranges when source data is uncertain; avoid false precision.
    - Recalculate the group total from the displayed line items
      so the arithmetic matches.
    - Label unsupported prices as estimates rather than presenting
      them as confirmed.
    - If a contingency is included, show it separately and calculate
      it from the subtotal.

16. End with practical final recommendations.


SOURCE PRIORITY:

Validation results
    >
Tool-backed results
    >
Agent-generated estimates
    >
General itinerary suggestions

When sources conflict, follow the validation result and explicitly
flag the conflict instead of silently choosing one.
""".strip()


# ---------------------------------------------------------------------------
# Build final context
# ---------------------------------------------------------------------------

def build_final_prompt(state: TravelState) -> str:
    """Build a compact, validation-aware final prompt."""

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

    validation_results = compact_text(
        state.get("validation_results", ""),
        VALIDATION_LIMIT,
    )

    return f"""
USER REQUEST
{user_query}

FLIGHT INFORMATION
{flight_results}

HOTEL INFORMATION
{hotel_results}

WEATHER INFORMATION
{weather_results}

ITINERARY
{itinerary}

VALIDATION RESULTS
{validation_results}

FINAL ANSWER REQUIREMENTS
- Produce the complete travel plan requested by the user.
- Preserve uncertainty labels.
- Do not invent missing information.
- Correct or remove unsupported itinerary details.
- Clearly distinguish verified information from estimates.
- Surface important validation warnings.
- Make the displayed budget arithmetically consistent and explain
  the basis of major estimates.
""".strip()


# ---------------------------------------------------------------------------
# Main graph node
# ---------------------------------------------------------------------------

def final_agent(state: TravelState) -> dict[str, Any]:
    """Generate the final validated travel-plan response."""

    prompt = build_final_prompt(state)

    system_prompt = (
        FINAL_SYSTEM_PROMPT
        + "\n\n"
        + FINAL_SAFETY_PROMPT
    )

    response = get_llm().invoke(
        [
            SystemMessage(
                content=system_prompt
            ),
            HumanMessage(
                content=prompt
            ),
        ]
    )

    return {
        "messages": [response],
        "llm_calls": bump_llm_calls(state),
    }