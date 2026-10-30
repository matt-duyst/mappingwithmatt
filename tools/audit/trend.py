"""The trend line for a timed metric: the new median against the baseline's spread across its runs."""


def trend(new, base, lo, hi):
    """'within noise' when the new median lies inside the baseline's minimum-to-maximum range; otherwise the direction and both medians,
    'down from X to Y' (X > Y) or 'up from X to Y' (X < Y), X the baseline median and Y the new one."""
    if lo is None or hi is None or base is None or new is None: return ''
    if lo <= new <= hi: return 'within noise'
    return f"{'down' if new < lo else 'up'} from {base} to {new}"
