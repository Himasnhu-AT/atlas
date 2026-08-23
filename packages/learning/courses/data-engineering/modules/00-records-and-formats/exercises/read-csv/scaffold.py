"""
Reading a messy file.

Parse a delimited file by hand, once, so you know what `csv` is doing for you.
Every rule here exists because a real file broke a real pipeline that ignored it.

Run `python3 test.py` when you want to see how you are doing.
"""

from __future__ import annotations


def split_fields(line: str, delimiter: str = ",") -> list[str]:
    """
    Split one line into fields, respecting quotes.

    Walk the line one character at a time rather than calling split(). Hold a
    flag for whether you are currently inside a quoted field; the delimiter only
    ends a field while that flag is off.

    Four rules cover it:
      - A field may be wrapped in double quotes, which are not part of the value.
      - Inside quotes, the delimiter is ordinary text.
      - Inside quotes, two double quotes in a row mean one literal double quote.
      - A quote only opens a quoted field at the START of one. A quote partway
        through an unquoted field is ordinary text, so a field that begins with
        a letter keeps every quote it contains, and one that begins with a quote
        does not. This is what the csv module does, and getting it backwards
        silently rewrites data that happens to contain a quote character.

    Args:
        line: one line, with no trailing newline.
        delimiter: the separator, always a single character.

    Returns:
        The fields, in order, with surrounding quotes removed and doubled quotes
        collapsed. An empty line gives [""], not [], because a line with no
        content still has one empty field.

    Examples:
        >>> split_fields('a,b,c')
        ['a', 'b', 'c']
        >>> split_fields('1003,"1,499.00",pending')
        ['1003', '1,499.00', 'pending']
        >>> split_fields('"say ""hi"" now",x')
        ['say "hi" now', 'x']
        >>> split_fields('say ""hi"",now')
        ['say ""hi""', 'now']
    """
    raise NotImplementedError


def parse_rows(text: str, delimiter: str = ",") -> list[dict]:
    """
    Parse a whole delimited document into dicts.

    The first line is the header and names the fields. Every line after it is a
    record.

    A row with fewer fields than the header gets None for the ones it is
    missing. Do not drop it. A row that is present in the source has to be
    present in what you parsed, even when it is incomplete: a bad row can be
    found later and a missing one cannot.

    A row with more fields than the header keeps only as many as the header
    names. The extras have nowhere to go, and `check_shape` below is what
    reports them.

    Args:
        text: the whole file, header included. May end with a newline.
        delimiter: the separator.

    Returns:
        One dict per record, keyed by header name, values as strings or None.
        Empty text, or text with only a header, gives [].
    """
    raise NotImplementedError


def check_shape(text: str, delimiter: str = ",") -> list[dict]:
    """
    Report every line whose field count does not match the header.

    This is the function that would have caught the naive parser eating a
    quoted comma. It reports rather than raises, because one malformed line in
    ten thousand should not stop a load; it should be visible.

    Args:
        text: the whole file, header included.

    Returns:
        One dict per bad line, in file order, shaped:

            {"line": 4, "expected": 6, "found": 7}

        `line` is 1-based and counts the header as line 1, so the first record
        is line 2. That is what an editor shows you, and an off-by-one here
        sends somebody to the wrong row.

        A file where every line matches gives [].
    """
    raise NotImplementedError


def column_values(rows: list[dict], column: str) -> list[str]:
    """
    Every non-empty value in one column, in order.

    Args:
        rows: the output of parse_rows.
        column: the field name to pull.

    Returns:
        The values, skipping any row where the field is missing, None, or an
        empty string after stripping. Whitespace is stripped from the values
        that are kept.

        Skipping blanks here is safe because this answers "what values appear",
        not "how many rows are there". Those are different questions and
        conflating them is how a count ends up wrong.
    """
    raise NotImplementedError
