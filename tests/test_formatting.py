from pdf_reader.core.formatting import duration, time_ago


def test_time_ago():
    now = 1_000_000.0
    assert time_ago(now - 10, now) == "just now"
    assert time_ago(now - 300, now) == "5 min ago"
    assert time_ago(now - 7200, now) == "2 h ago"
    assert time_ago(now - 86_400 * 1.5, now) == "yesterday"
    assert time_ago(now - 86_400 * 4, now) == "4 days ago"


def test_duration():
    assert duration(0.4) == "under 1 min"
    assert duration(12.4) == "12 min"
    assert duration(65) == "1 h 05 min"
    assert duration(180) == "3 h"
