"""Weekly scheduler lookup. Run: pytest  (or python tests/test_schedule.py)"""
import time

from pyenki.schedule import desired_temp


def at(wday, hhmm):
    h, m = map(int, hhmm.split(":"))
    return time.struct_time((2026, 1, 5 + wday, h, m, 0, wday, 5 + wday, -1))


RS = {"days": {
    "0": [["06:00", 20], ["08:00", 17], ["18:00", 21], ["22:00", 16]],  # Monday
    "2": [["07:00", 19]],                                               # Wednesday
}}


def test_latest_slot_of_the_day():
    assert desired_temp(RS, at(0, "06:30")) == 20
    assert desired_temp(RS, at(0, "08:00")) == 17
    assert desired_temp(RS, at(0, "21:59")) == 21
    assert desired_temp(RS, at(0, "23:00")) == 16


def test_wraps_to_previous_rule():
    # before Monday's first slot -> last rule of the week (Wed 19)
    assert desired_temp(RS, at(0, "05:00")) == 19
    # Tuesday has no rules -> carries Monday's last (16)
    assert desired_temp(RS, at(1, "12:00")) == 16
    # Wednesday before its slot -> Monday 22:00 (16); after -> 19
    assert desired_temp(RS, at(2, "06:00")) == 16
    assert desired_temp(RS, at(2, "07:30")) == 19


def test_empty_schedule():
    assert desired_temp({"days": {}}) is None


if __name__ == "__main__":
    test_latest_slot_of_the_day()
    test_wraps_to_previous_rule()
    test_empty_schedule()
    print("ok")
