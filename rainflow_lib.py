from collections import deque, defaultdict
import math
import numpy as np

def _get_round_function(ndigits=None):
    if ndigits is None:
        def func(x):
            return x
    else:
        def func(x):
            return round(x, ndigits)
    return func

def find_extrema(series):
    """Find peaks and valleys in the series."""
    extrema = []
    for i in range(1, len(series) - 1):
        if (series[i] > series[i - 1] and series[i] > series[i + 1]) or \
           (series[i] < series[i - 1] and series[i] < series[i + 1]):
            extrema.append((i, series[i]))
    return extrema

def reversals(series):
    """Iterate reversal points in the series."""
    series = iter(series)
    x_last, x = next(series, None), next(series, None)
    if x_last is None or x is None:
        return
    d_last = (x - x_last)
    yield 0, x_last
    index = None
    for index, x_next in enumerate(series, start=1):
        if x_next == x:
            continue
        d_next = x_next - x
        if d_last * d_next < 0:
            yield index, x
        x_last, x = x, x_next
        d_last = d_next
    if index is not None:
        yield index + 1, x_next

def extract_cycles(series):
    """Iterate cycles in the series."""
    points = deque()

    def format_output(point1, point2, count):
        i1, x1 = point1
        i2, x2 = point2
        rng = abs(x1 - x2)
        mean = 0.5 * (x1 + x2)
        return rng, mean, count, i1, i2

    for point in reversals(series):
        points.append(point)

        while len(points) >= 3:
            x1, x2, x3 = points[-3][1], points[-2][1], points[-1][1]
            X = abs(x3 - x2)
            Y = abs(x2 - x1)

            if X < Y:
                break
            elif len(points) == 3:
                yield format_output(points[0], points[1], 0.5)
                points.popleft()
            else:
                yield format_output(points[-3], points[-2], 1.0)
                last = points.pop()
                points.pop()
                points.pop()
                points.append(last)
    else:
        while len(points) > 1:
            yield format_output(points[0], points[1], 0.5)
            points.popleft()

def count_cycles(series, ndigits=None, nbins=None, binsize=None):
    """Count cycles in the series."""
    if sum(value is not None for value in (ndigits, nbins, binsize)) > 1:
        raise ValueError("Arguments ndigits, nbins and binsize are mutually exclusive")

    counts = defaultdict(float)
    cycles = (
        (rng, count)
        for rng, mean, count, i_start, i_end in extract_cycles(series)
    )

    if nbins is not None:
        binsize = (max(series) - min(series)) / nbins

    if binsize is not None:
        nmax = 0
        for rng, count in cycles:
            quotient = rng / binsize
            n = int(math.ceil(quotient))

            if nbins and n > nbins:
                if (quotient % 1) > 1e-6:
                    raise Exception("Unexpected error")
                n = n - 1

            counts[n * binsize] += count
            nmax = max(n, nmax)

        for i in range(1, nmax):
            counts.setdefault(i * binsize, 0.0)

    elif ndigits is not None:
        round_ = _get_round_function(ndigits)
        for rng, count in cycles:
            counts[round_(rng)] += count

    else:
        for rng, count in cycles:
            counts[rng] += count

    return sorted(counts.items())

def rainflow(x, fs=None, t=None, ext=False):
    """Rainflow counting algorithm similar to MATLAB's implementation."""
    if ext:
        # If extrema are provided, use them directly
        idx = np.arange(len(x))
        extrema = list(zip(idx, x))
    else:
        # Find extrema (peaks and valleys)
        extrema = find_extrema(x)
        idx = [i for i, _ in extrema]
        x = [val for _, val in extrema]

    # Perform rainflow counting
    cycles = list(extract_cycles(x))

    # Create the output matrix
    C = np.array([
        [count, rng, mean, idx[start], idx[end]]
        for rng, mean, count, start, end in cycles
    ])

    # Compute the rainflow matrix
    if len(cycles) > 0:
        ranges = np.array([rng for rng, _, _, _, _ in cycles])
        means = np.array([mean for _, mean, _, _, _ in cycles])
        counts = np.array([count for _, _, count, _, _ in cycles])

        # Add whole cycles
        whole_cycles = counts == 1.0
        ranges = np.concatenate([ranges, ranges[whole_cycles]])
        means = np.concatenate([means, means[whole_cycles]])

        # Compute 2D histogram (rainflow matrix)
        rm, xedges, yedges = np.histogram2d(ranges, means, bins=10)

        # Normalize the rainflow matrix
        rm = rm / 2
    else:
        rm, xedges, yedges = np.array([]), np.array([]), np.array([])

    return C, rm, xedges, yedges, idx
