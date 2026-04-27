"""
events.py — Market event calendar for trading blackout detection.

Maintains a list of high-impact events (RBI, FOMC, Budget, etc.)
that should prevent new trade entries.
"""
from datetime import date, datetime, timedelta


# Hardcoded known high-impact events for 2025-2026
# Source: RBI website, Federal Reserve website, India Budget
KNOWN_EVENTS = [
    # RBI MPC Policy Dates 2025
    {"date": "2025-04-09", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2025-06-06", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2025-08-08", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2025-10-01", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2025-12-05", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    # RBI MPC Policy Dates 2026
    {"date": "2026-02-06", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2026-04-08", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2026-06-05", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},
    {"date": "2026-08-07", "name": "RBI MPC Policy Decision", "impact": "high", "category": "rbi"},

    # FOMC (US Fed) 2025
    {"date": "2025-03-19", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-05-07", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-06-18", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-07-30", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-09-17", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-10-29", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2025-12-17", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    # FOMC 2026
    {"date": "2026-01-28", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2026-03-18", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2026-05-06", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},
    {"date": "2026-06-17", "name": "FOMC Rate Decision", "impact": "high", "category": "fed"},

    # India Budget
    {"date": "2025-07-23", "name": "India Union Budget 2025-26", "impact": "high", "category": "budget"},
    {"date": "2026-02-01", "name": "India Union Budget 2026-27", "impact": "high", "category": "budget"},

    # India Election results (if applicable)
    {"date": "2025-11-23", "name": "Bihar Election Results", "impact": "medium", "category": "election"},
]

# NSE Trading Holidays 2025 (approximate)
NSE_HOLIDAYS_2025 = [
    "2025-02-26",  # Mahashivratri
    "2025-03-14",  # Holi
    "2025-03-31",  # Eid-ul-Fitr
    "2025-04-10",  # Shri Ram Navami
    "2025-04-14",  # Dr. Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-06-07",  # Eid-ul-Adha
    "2025-08-15",  # Independence Day
    "2025-08-16",  # Janmashtami
    "2025-10-02",  # Mahatma Gandhi Jayanti
    "2025-10-21",  # Dussehra
    "2025-11-05",  # Diwali (Laxmi Pujan)
    "2025-11-06",  # Diwali Balipratipada
    "2025-11-26",  # Guru Nanak Jayanti
    "2025-12-25",  # Christmas
]

NSE_HOLIDAYS_2026 = [
    "2026-01-26",  # Republic Day
    "2026-02-17",  # Mahashivratri
    "2026-03-03",  # Holi
    "2026-03-20",  # Eid-ul-Fitr
    "2026-03-30",  # Shri Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Eid-ul-Adha
    "2026-08-15",  # Independence Day
    "2026-08-05",  # Janmashtami
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-09",  # Dussehra
    "2026-10-24",  # Diwali (Laxmi Pujan)
    "2026-10-25",  # Diwali Balipratipada
    "2026-11-16",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
]

ALL_NSE_HOLIDAYS = set(NSE_HOLIDAYS_2025 + NSE_HOLIDAYS_2026)


def is_nse_holiday(check_date: date = None) -> bool:
    """Check if a date is an NSE trading holiday."""
    if check_date is None:
        check_date = date.today()
    return check_date.isoformat() in ALL_NSE_HOLIDAYS


def is_market_hours(now: datetime = None) -> bool:
    """Check if current time is within NSE trading hours (9:15 AM - 3:30 PM IST)."""
    if now is None:
        # Use IST
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)

    # Weekday check (Mon-Fri = 0-4)
    if now.weekday() > 4:
        return False

    if is_nse_holiday(now.date()):
        return False

    # Market hours: 9:15 AM to 3:30 PM
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    return market_open <= now <= market_close


def get_upcoming_events(days_ahead: int = 7) -> list[dict]:
    """Get events within the next N days."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    upcoming = []
    for event in KNOWN_EVENTS:
        event_date = date.fromisoformat(event["date"])
        if today <= event_date <= cutoff:
            upcoming.append({
                **event,
                "days_away": (event_date - today).days,
            })

    return sorted(upcoming, key=lambda e: e["date"])


def is_blackout_period(hours_ahead: int = 24) -> tuple[bool, str]:
    """
    Check if there's a high-impact event within the blackout window.
    Returns (is_blackout, reason_string).
    """
    today = date.today()
    cutoff = today + timedelta(hours=hours_ahead)

    for event in KNOWN_EVENTS:
        event_date = date.fromisoformat(event["date"])
        if event["impact"] == "high" and today <= event_date <= cutoff:
            days_away = (event_date - today).days
            return True, f"{event['name']} in {days_away} day(s) ({event['date']})"

    return False, ""


async def sync_events_to_db() -> int:
    """Sync hardcoded events to market_events table. Returns count inserted."""
    from db.database import _get_db

    count = 0
    async with _get_db() as db:
        for event in KNOWN_EVENTS:
            try:
                await db.execute(
                    """INSERT OR IGNORE INTO market_events
                       (event_date, event_name, impact, category, avoid_trading)
                       VALUES (?, ?, ?, ?, ?)""",
                    (event["date"], event["name"], event["impact"],
                     event["category"], 1 if event["impact"] == "high" else 0),
                )
                count += 1
            except Exception:
                pass
        await db.commit()

    return count
