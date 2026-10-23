"""Weekly schedule lookup, shared by the agent and its background scheduler.

A per-radiator schedule is {"days": {"0": [["06:00", 20], ...], ... "6": [...]}}
where the day key is the python weekday() (0 = Monday) and each entry is
[HH:MM, °C]. The active set-point is the most recent entry at or before now,
wrapping over to the previous day / end of week when earlier in the day.
"""
import time


def desired_temp(rad_sched, now=None):
    """Temp of the most recent (day, time) rule at or before `now`, or None."""
    now = now or time.localtime()
    rules = []  # (minutes_into_week, temp)
    for d_str, entries in (rad_sched.get("days") or {}).items():
        d = int(d_str)
        for hhmm, temp in entries:
            h, m = hhmm.split(":")
            rules.append((d * 1440 + int(h) * 60 + int(m), float(temp)))
    if not rules:
        return None
    rules.sort()
    cur = now.tm_wday * 1440 + now.tm_hour * 60 + now.tm_min
    before = [t for (mins, t) in rules if mins <= cur]
    return before[-1] if before else rules[-1][1]
