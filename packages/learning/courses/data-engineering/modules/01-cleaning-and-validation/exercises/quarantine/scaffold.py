"""
Quarantine, not deletion.

Dropping a bad row makes the load succeed and the number wrong. Keeping it with
the reason attached costs almost nothing and is the difference between a bug
somebody finds on Tuesday and one they find next quarter.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def quarantine_record(result: dict, raw: dict, source: str, received_at: str) -> dict:
    """
    Build the record that goes in the quarantine.

    Args:
        result: one output of the previous exercise's `validate_row`, for a row
            that failed.
        raw: the row exactly as it arrived, before any coercion.
        source: what it came from, for example "orders_2026-03-06.csv".
        received_at: when the extract landed, ISO 8601.

    Returns:
        A dict shaped:

            {
                "row_number": 6,
                "source": "orders_2026-03-06.csv",
                "received_at": "2026-03-06T02:00:00Z",
                "errors": [...],
                "raw": {...},
            }

        `raw` is the untouched row. Not the partly-coerced version and not the
        row with the bad field blanked, because the raw row is what makes a
        quarantine repairable: when somebody fixes the source, these can be run
        back through the same validator and loaded. A cleaned-up copy means
        going back to a file that may have been rotated away.

        Store a copy, not the original dict. A quarantine that shares objects
        with the pipeline is one careless mutation away from being wrong about
        what actually arrived.
    """
    raise NotImplementedError


def summarise_quarantine(records: list[dict]) -> dict:
    """
    What is in the quarantine, grouped so a person can read it.

    Args:
        records: quarantine records.

    Returns:
        A dict shaped:

            {
                "total": 3,
                "by_field": {"quantity": 2, "status": 1},
                "by_problem": {"invalid": 2, "missing": 1},
                "sources": ["orders_2026-03-06.csv"],
            }

        `by_field` and `by_problem` count ERRORS, not rows, because the question
        here is "what is going wrong", not "how many rows did it cost". That is
        the opposite of `field_problems` in the previous exercise, and the
        difference is deliberate: one summary is for deciding whether to load,
        this one is for deciding what to fix.

        `sources` is sorted and deduplicated.
    """
    raise NotImplementedError


def rate_moved(
    yesterday: dict,
    today: dict,
    threshold: float = 2.0,
) -> dict:
    """
    Has the failure rate changed enough to be worth waking somebody up?

    A quarantine only works if somebody looks, and the number worth looking at is
    not the count, which is noise on a good day. It is a rate that moved.

    Args:
        yesterday: {"broken": 2, "total": 10000}
        today: the same shape.
        threshold: how many times worse today has to be before it is news.

    Returns:
        A dict shaped:

            {
                "yesterday_rate": 0.0002,
                "today_rate": 0.02,
                "ratio": 100.0,
                "moved": True,
            }

        `moved` is True when today's rate is at least `threshold` times
        yesterday's and today has at least one failure. Rates are
        `broken / total`, and a day with no total has a zero rate.

        Two edge cases decide whether this is useful or annoying. When
        yesterday's rate was zero and today's is not, `ratio` is infinity and
        `moved` is True: going from no failures to some failures is exactly the
        change worth reporting. When both are zero, `ratio` is 0.0 and `moved`
        is False, because nothing happened.

        A day with no rows at all has a rate of 0.0 rather than raising. An
        empty extract is a different alarm, and it belongs to `is_usable`.
    """
    raise NotImplementedError
