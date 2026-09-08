"""Deterministic validation for hard travel-plan constraints."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


DATE_PATTERNS = [
    r"\b(\d{4})-(\d{2})-(\d{2})\b",
    r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
]


def _parse_date(value: str) -> date | None:
    """Parse common date formats used by the agents."""

    value = value.strip()

    # YYYY-MM-DD
    match = re.search(DATE_PATTERNS[0], value)
    if match:
        try:
            return date(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
            )
        except ValueError:
            return None

    # DD/MM/YYYY or DD-MM-YYYY
    match = re.search(DATE_PATTERNS[1], value)
    if match:
        try:
            return date(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
            )
        except ValueError:
            return None

    return None


def extract_dates(text: str) -> list[date]:
    """Extract unique dates from text."""

    dates: list[date] = []

    for pattern in DATE_PATTERNS:
        for match in re.finditer(pattern, text):
            try:
                if pattern == DATE_PATTERNS[0]:
                    parsed = date(
                        int(match.group(1)),
                        int(match.group(2)),
                        int(match.group(3)),
                    )
                else:
                    parsed = date(
                        int(match.group(3)),
                        int(match.group(2)),
                        int(match.group(1)),
                    )

                if parsed not in dates:
                    dates.append(parsed)

            except ValueError:
                continue

    return dates


def extract_trip_dates(user_query: str) -> tuple[date | None, date | None]:
    """
    Extract a likely start and end date from the user's request.

    Supports patterns such as:
    - 2026-09-08 to 2026-09-12
    - 08/09/2026 - 12/09/2026
    - 8 Sep 2026 to 12 Sep 2026
    """

    dates = extract_dates(user_query)

    # Explicit numeric dates.
    if len(dates) >= 2:
        return dates[0], dates[1]

    # Month-name format.
    month_pattern = (
        r"\b(\d{1,2})\s+"
        r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"\s+(\d{4})"
    )

    matches = list(re.finditer(month_pattern, user_query, re.IGNORECASE))

    if len(matches) >= 2:
        month_map = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
            "jun": 6,
            "june": 6,
            "jul": 7,
            "july": 7,
            "aug": 8,
            "august": 8,
            "sep": 9,
            "september": 9,
            "oct": 10,
            "october": 10,
            "nov": 11,
            "november": 11,
            "dec": 12,
            "december": 12,
        }

        parsed_dates = []

        for match in matches:
            day = int(match.group(1))
            month = month_map[match.group(2).lower()]
            year = int(match.group(3))

            try:
                parsed_dates.append(date(year, month, day))
            except ValueError:
                continue

        if len(parsed_dates) >= 2:
            return parsed_dates[0], parsed_dates[1]

    return None, None


def calculate_calendar_days(start: date, end: date) -> int:
    """Calculate inclusive calendar-day count."""

    return (end - start).days + 1


def calculate_hotel_nights(start: date, end: date) -> int:
    """Calculate hotel nights."""

    return (end - start).days


def extract_hotel_nights(text: str) -> list[int]:
    """Extract explicit hotel-night counts."""

    patterns = [
        r"(\d+)\s*(?:hotel\s*)?nights?",
        r"(\d+)\s*nights?\s*(?:in|at|of)",
    ]

    values: list[int] = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = int(match.group(1))

            if value not in values:
                values.append(value)

    return values


def extract_day_count(text: str) -> list[int]:
    """Extract explicit calendar-day counts."""

    values: list[int] = []

    pattern = r"(\d+)\s*(?:calendar\s*)?days?"

    for match in re.finditer(pattern, text, re.IGNORECASE):
        value = int(match.group(1))

        if value not in values:
            values.append(value)

    return values


def extract_budget_numbers(text: str) -> list[Decimal]:
    """Extract simple currency numbers from budget text."""

    values: list[Decimal] = []

    pattern = r"(?:₹|€|\$|USD|EUR|INR)\s*([\d,]+(?:\.\d+)?)"

    for match in re.finditer(pattern, text, re.IGNORECASE):
        raw = match.group(1).replace(",", "")

        try:
            values.append(Decimal(raw))
        except InvalidOperation:
            continue

    return values

def contains_exact_flight_time(text: str) -> bool:
    """Detect exact-looking flight times in travel text."""

    if not text:
        return False

    time_pattern = re.compile(
        r"\b(?:[01]?\d|2[0-3]):[0-5]\d\s*(?:AM|PM)?\b"
        r"|\b(?:1[0-2]|0?[1-9])\s*(?::[0-5]\d)?\s*(?:AM|PM)\b",
        re.IGNORECASE,
    )

    flight_context = re.compile(
        r"\b("
        r"flight|departure|depart|arrival|arrive|return flight|"
        r"outbound|takeoff|landing"
        r")\b",
        re.IGNORECASE,
    )

    for line in text.splitlines():
        if flight_context.search(line) and time_pattern.search(line):
            return True

    return False


def flight_data_is_unverified(text: str) -> bool:
    """Detect explicit uncertainty in flight-agent output."""

    if not text:
        return True

    uncertainty_pattern = re.compile(
        r"\b("
        r"unverified|estimated|estimate|"
        r"not verified|cannot verify|unable to verify|"
        r"no live data|live data unavailable|"
        r"availability unavailable|"
        r"check before booking"
        r")\b",
        re.IGNORECASE,
    )

    return bool(uncertainty_pattern.search(text))

def deterministic_validate(
    user_query: str,
    flight_results: str,
    hotel_results: str,
    weather_results: str,
    itinerary: str,
) -> dict[str, Any]:
    """
    Run deterministic checks that should not depend on an LLM.

    Returns structured validation information.
    """

    issues: list[str] = []
    warnings: list[str] = []
    checks: list[str] = []

    # ---------------------------------------------------------------
    # 1. TRIP DATES
    # ---------------------------------------------------------------

    start_date, end_date = extract_trip_dates(user_query)

    if start_date and end_date:
        checks.append(
            f"Trip dates detected: {start_date.isoformat()} → "
            f"{end_date.isoformat()}."
        )

        if end_date < start_date:
            issues.append(
                "CRITICAL: Return/end date occurs before the trip start date."
            )

        else:
            calendar_days = calculate_calendar_days(start_date, end_date)
            hotel_nights = calculate_hotel_nights(start_date, end_date)

            checks.append(
                f"Calculated duration: {calendar_days} calendar days "
                f"and {hotel_nights} hotel nights."
            )

            # Check hotel output.
            hotel_nights_found = extract_hotel_nights(hotel_results)

            if hotel_nights_found:
                for nights in hotel_nights_found:
                    if nights != hotel_nights:
                        issues.append(
                            f"Hotel-night mismatch: expected {hotel_nights} "
                            f"nights from the requested dates, but hotel "
                            f"output contains {nights} nights."
                        )

            # Check itinerary day count.
            itinerary_days = extract_day_count(itinerary)

            for days in itinerary_days:
                if days != calendar_days:
                    warnings.append(
                        f"Itinerary duration says {days} days, but the "
                        f"requested date range contains {calendar_days} "
                        f"calendar days."
                    )

            # Check dates appearing in itinerary.
            itinerary_dates = extract_dates(itinerary)

            for itinerary_date in itinerary_dates:
                if itinerary_date < start_date or itinerary_date > end_date:
                    issues.append(
                        f"Itinerary contains {itinerary_date.isoformat()}, "
                        f"which falls outside the requested trip dates."
                    )

    else:
        warnings.append(
            "No explicit trip start/end dates could be extracted from "
            "the user request."
        )

    # ---------------------------------------------------------------
    # 2. FLIGHT DATE ORDER
    # ---------------------------------------------------------------

    flight_dates = extract_dates(flight_results)

    if len(flight_dates) >= 2:
        outbound = min(flight_dates)
        return_date = max(flight_dates)

        if return_date < outbound:
            issues.append(
                "CRITICAL: Flight dates are chronologically inconsistent."
            )
        else:
            checks.append(
                f"Flight dates are chronologically ordered: "
                f"{outbound.isoformat()} → {return_date.isoformat()}."
            )

        if start_date and end_date:
            if outbound < start_date or outbound > end_date:
                warnings.append(
                    "Outbound flight date appears outside the requested "
                    "trip-date range."
                )

            if return_date < start_date or return_date > end_date:
                warnings.append(
                    "Return flight date appears outside the requested "
                    "trip-date range."
                )

    else:
        warnings.append(
            "Could not deterministically verify outbound and return "
            "flight dates."
        )

    # ---------------------------------------------------------------
    # 2B. UNSUPPORTED EXACT FLIGHT TIMES
    # ---------------------------------------------------------------
    #
    # If flight information is explicitly unverified, exact-looking
    # flight times should not be allowed to silently pass into the
    # final itinerary.
    #
    # This is deterministic and does NOT use another LLM call.
    # ---------------------------------------------------------------

    if (
        flight_data_is_unverified(flight_results)
        and contains_exact_flight_time(itinerary)
    ):
        issues.append(
            "CRITICAL: The itinerary contains exact-looking flight "
            "times even though the available flight information is "
            "unverified or estimated. Remove those times from the "
            "final answer unless they are explicitly supported by "
            "verified flight data."
        )
    else:
        checks.append(
            "No unsupported exact flight times detected in the "
            "itinerary."
        )

    # ---------------------------------------------------------------
    # 3. HOTEL OUTPUT
    # ---------------------------------------------------------------

    hotel_nights = extract_hotel_nights(hotel_results)

    if len(set(hotel_nights)) > 1:
        warnings.append(
            "Hotel output contains multiple different night counts; "
            "manual/LLM validation is required."
        )

    # ---------------------------------------------------------------
    # 4. WEATHER DATE CHECK
    # ---------------------------------------------------------------

    weather_dates = extract_dates(weather_results)

    if start_date and end_date and weather_dates:
        outside_dates = [
            d
            for d in weather_dates
            if d < start_date or d > end_date
        ]

        if outside_dates:
            warnings.append(
                "Weather output contains dates outside the requested "
                "travel period."
            )

    # ---------------------------------------------------------------
    # 5. BASIC BUDGET SANITY
    # ---------------------------------------------------------------

    budget_numbers = extract_budget_numbers(itinerary)

    if budget_numbers:
        checks.append(
            f"Detected {len(budget_numbers)} currency values in the "
            "itinerary for budget review."
        )
    else:
        warnings.append(
            "No simple currency values were detected for deterministic "
            "budget checking."
        )

    # ---------------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------------

    status = "ISSUES FOUND" if issues else "VALID"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "checks": checks,
    }


def format_deterministic_validation(result: dict[str, Any]) -> str:
    """Convert structured deterministic validation into readable text."""

    lines = [
        "DETERMINISTIC VALIDATION",
        "=========================",
        f"STATUS: {result['status']}",
        "",
        "HARD ISSUES:",
    ]

    if result["issues"]:
        lines.extend(f"- {issue}" for issue in result["issues"])
    else:
        lines.append("- None detected.")

    lines.extend(
        [
            "",
            "WARNINGS:",
        ]
    )

    if result["warnings"]:
        lines.extend(f"- {warning}" for warning in result["warnings"])
    else:
        lines.append("- None.")

    lines.extend(
        [
            "",
            "CHECKS:",
        ]
    )

    if result["checks"]:
        lines.extend(f"- {check}" for check in result["checks"])
    else:
        lines.append("- No deterministic checks completed.")

    return "\n".join(lines)