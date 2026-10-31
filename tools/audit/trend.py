"""The trend line for a timed metric: the new median against the baseline's spread across its runs."""


def trend(new, base, lo, hi):
    """'within noise' when the new median lies inside the baseline's minimum-to-maximum range; otherwise the direction and both medians,
    'down from X to Y' (X > Y) or 'up from X to Y' (X < Y), X the baseline median and Y the new one."""
    if lo is None or hi is None or base is None or new is None: return ''
    if lo <= new <= hi: return 'within noise'
    return f"{'down' if new < lo else 'up'} from {base} to {new}"


def tbt_failure(median, base_max, mode='absolute'):
    """The TBT gate. absolute (local runs against the GPU baseline): fail above 50 ms. relative (the review workflow's runner, where no
    page can meet 50 ms): fail when the median exceeds the CI baseline's maximum for the same cell by more than 25 percent. Returns the
    failure message, or None."""
    if median is None: return None
    if mode == 'absolute': return f"{median} ms is above 50 ms" if median > 50 else None
    if mode != 'relative': raise ValueError(f'unknown gate mode {mode}')
    if base_max is None: return f"{median} ms has no baseline spread to compare with"
    limit = base_max * 1.25
    return f"{median} ms is more than 25% over the baseline's maximum {base_max}" if median > limit else None


def bytes_failure(cold, base, allowance=0.10):
    """The byte gate: fail when cold bytes rise more than the allowance (10 percent unless a review passes another) over the baseline."""
    if not base or cold is None: return None
    limit = round(base * (1 + allowance), 6)   # rounded, so 15 percent of 100,000 is 115,000 and not a float a hair below it
    return f"{cold} is more than {allowance:.0%} over the baseline {base}" if cold > limit else None


def requests_failure(cold, base, extra=0):
    """The request gate: fail when cold requests rise more than 10 percent over the baseline, plus any extra requests a review the owner has
    approved allows (at most 2)."""
    if not base or cold is None: return None
    limit = round(base * 1.10, 6) + extra
    return f"{cold} is more than 10% over the baseline {base}" + (f" plus {extra} allowed" if extra else '') if cold > limit else None
