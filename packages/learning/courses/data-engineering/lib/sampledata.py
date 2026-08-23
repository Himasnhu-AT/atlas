"""
The data this course works on.

Generated rather than shipped as files, for the same reason the AI course ships
a scripted model client rather than calling a provider: an exercise has to give
the same answer on every machine, every time, with nothing downloaded. A fixture
file would also drift out of step with the lessons that describe it.

Everything here is deterministic. There is no `random` seed to get wrong and no
clock to depend on, so a test that passes on your laptop passes in the build.

The mess is on purpose. Real extracts arrive with blank fields, three spellings
of the same date, currency symbols glued to numbers, duplicate ids from a
retried export, and a header that does not quite match the documentation. Every
one of those appears here because every one of them is a decision you have to
make in the next five modules.
"""

from __future__ import annotations

import csv
import io

# One order per line, as an upstream system actually hands them over.
#
# Read this once before starting module 0. Everything wrong with it is wrong on
# purpose, and knowing what is coming is not cheating: in a real job somebody
# tells you, and the useful skill is deciding what to do about it.
#
#  - `order_id` repeats once, because the export was retried after a timeout.
#  - `placed_at` is spelled three ways.
#  - `total` sometimes carries a currency symbol and sometimes a thousands comma.
#  - `quantity` is occasionally blank, and once the string "unknown".
#  - `customer` has stray whitespace and inconsistent case.
#  - one row has fewer fields than the header promises.
ORDERS_CSV = """order_id,customer,placed_at,quantity,total,status
1001,ada@example.com,2026-03-01,2,49.90,shipped
1002, Grace@Example.com ,01/03/2026,1,19.95,shipped
1003,lin@example.com,2026-03-02T09:14:00,3,"1,499.00",pending
1004,ada@example.com,2026-03-02,,29.99,shipped
1005,kofi@example.com,03/03/2026,2,$59.00,cancelled
1003,lin@example.com,2026-03-02T09:14:00,3,"1,499.00",pending
1006,mei@example.com,2026-03-04,unknown,15.00,shipped
1007,ada@example.com,2026-03-05,1,9.99
1008,,2026-03-05,4,80.00,shipped
1009,kofi@example.com,2026-03-06,1,12.50,refunded
"""

# A second extract, as it would arrive the next day: some rows are new, some are
# unchanged, and one has been corrected upstream. This is what an incremental
# load has to cope with, and what makes "run it twice" a real question.
ORDERS_CSV_DAY_TWO = """order_id,customer,placed_at,quantity,total,status
1009,kofi@example.com,2026-03-06,1,12.50,shipped
1010,ada@example.com,2026-03-06,2,24.00,shipped
1011,mei@example.com,2026-03-07,1,99.00,pending
1012,grace@example.com,2026-03-07,3,45.00,shipped
"""

# A tiny reference table, clean, the way a dimension usually is.
CUSTOMERS_CSV = """email,country,signed_up
ada@example.com,GB,2025-11-02
grace@example.com,GB,2025-12-14
lin@example.com,SG,2026-01-08
kofi@example.com,GH,2026-02-21
mei@example.com,SG,2026-02-28
"""


def orders_csv(day: int = 1) -> str:
    """
    The raw extract, exactly as it would land on disk.

    Args:
        day: 1 for the first extract, 2 for the next day's.

    Returns:
        The file contents as one string, newlines and all. Nothing is cleaned,
        nothing is sorted, and the header is included.
    """
    if day == 2:
        return ORDERS_CSV_DAY_TWO
    return ORDERS_CSV


def customers_csv() -> str:
    """The customer reference table. Clean, and smaller than the orders."""
    return CUSTOMERS_CSV


def read_rows(text: str) -> list[dict]:
    """
    Parse a CSV into dicts, doing nothing else.

    Provided because parsing CSV correctly is not what most of this course is
    about: quoting rules are genuinely fiddly and `csv` already knows them.
    Module 0 asks you to do it by hand once, so you know what the module is
    doing for you afterwards.

    A short row gets `None` for the fields it is missing, which is what
    `csv.DictReader` does and is worth seeing before you meet it in a test.
    """
    return list(csv.DictReader(io.StringIO(text)))


def write_rows(rows: list[dict], fieldnames: list[str]) -> str:
    """Render rows back to CSV, for exercises that produce a file."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return out.getvalue()
