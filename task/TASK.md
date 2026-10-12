# Task: duration parser

Implement two functions in `duration.py`. Read every rule carefully.

## `parse_duration(text: str) -> int`

Parse a human duration string and return the total as an **integer number of milliseconds**.

1. **Units** (lowercase only, case-sensitive):
   `w` = 7 days, `d` = day, `h` = hour, `m` = minute, `s` = second, `ms` = millisecond.
   Anything else (e.g. `M`, `H`, `y`, `min`) is invalid.
2. **Components** are `<number><unit>`, e.g. `1h30m`. Components may be separated by
   **at most one** space (`1h 30m` is valid, `1h  30m` is not). Leading/trailing
   whitespace of the whole string is ignored.
3. **Numbers** are non-negative. No leading zeros except a single `0`
   (`0s` and `0.5h` are fine, `01h` and `00.5h` are invalid).
4. **Decimals** are allowed **only in the last component** (`1.5h` and `1h1.5m`
   are valid, `1.5h30m` is invalid). A decimal needs digits on both sides of the dot
   (`.5h` and `1.h` are invalid). If the result is not a whole number of milliseconds,
   it is invalid (`0.0005s` is invalid).
5. **Order**: units must appear in strictly descending size, each at most once
   (`1h30m` valid, `30m1h` invalid, `1h1h` invalid).
6. **Sign**: an optional single leading `-` makes the whole duration negative
   (`-1h30m` = -5400000). `+` is invalid. `-0s` is `0`.
7. The bare string `0` (no unit) is valid and means `0`. Any other number without a
   unit is invalid. An empty or whitespace-only string is invalid.
8. Invalid input raises `ValueError`. Input that is not a `str` raises `TypeError`.

## `format_duration(ms: int) -> str`

Return the canonical string for a millisecond count.

1. Use the largest units first (`w`, `d`, `h`, `m`, `s`, `ms`), no spaces, omit zero
   components: `5400000` -> `"1h30m"`, `1500` -> `"1s500ms"`, `694861001` -> `"1w1d1h1m1s1ms"`.
2. `0` -> `"0s"`.
3. Negative values get a single leading `-`: `-90000` -> `"-1m30s"`.
4. Non-`int` input raises `TypeError`. **`bool` is not accepted** (raise `TypeError`).
5. Round trip: `parse_duration(format_duration(x)) == x` for every int `x`.
