from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class MarketSession:
    name: str
    is_open: bool
    premarket: bool


def get_market_session(now: datetime | None = None) -> MarketSession:
    now = now.astimezone(IST) if now else datetime.now(IST)
    if now.weekday() >= 5:
        return MarketSession(name="closed", is_open=False, premarket=False)

    current_time = now.time()
    premarket_start = time(9, 0)
    market_open = time(9, 15)
    market_close = time(15, 30)

    if premarket_start <= current_time < market_open:
        return MarketSession(name="premarket", is_open=False, premarket=True)
    if market_open <= current_time <= market_close:
        return MarketSession(name="live", is_open=True, premarket=False)
    return MarketSession(name="closed", is_open=False, premarket=False)
