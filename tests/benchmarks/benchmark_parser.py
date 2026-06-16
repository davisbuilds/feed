"""Focused parser microbenchmarks.

Run:
    uv run python tests/benchmarks/benchmark_parser.py
"""

from __future__ import annotations

import statistics
import time

from feed.ingest.parser import clean_text

ITERATIONS = 5_000
ROUNDS = 7

SAMPLE_TEXT = (
    """
Daily briefing

This paragraph has    irregular spacing and several newsletter artifacts.
Subscribe to our newsletter for more.



Share this post

Leave a comment

Read more at https://example.com/full-story

Core content remains useful. View in browser. Forward to a friend.
"""
    * 8
)


def time_clean_text() -> list[float]:
    """Return per-round timings for cleaning repeated article text."""
    samples: list[float] = []
    for _ in range(ROUNDS):
        start = time.perf_counter()
        for _ in range(ITERATIONS):
            clean_text(SAMPLE_TEXT)
        samples.append(time.perf_counter() - start)
    return samples


def main() -> None:
    samples = time_clean_text()
    mean_seconds = statistics.mean(samples)
    best_seconds = min(samples)
    stdev_seconds = statistics.stdev(samples)
    mean_ms_per_1000 = mean_seconds / ITERATIONS * 1_000 * 1_000
    best_ms_per_1000 = best_seconds / ITERATIONS * 1_000 * 1_000
    stdev_ms_per_1000 = stdev_seconds / ITERATIONS * 1_000 * 1_000

    print("# Parser benchmark")
    print(f"iterations={ITERATIONS}")
    print(f"rounds={ROUNDS}")
    print(
        "metric=clean_text_mean_ms_per_1000 "
        f"value={mean_ms_per_1000:.6f} unit=ms lower_is_better=true"
    )
    print(
        "metric=clean_text_best_ms_per_1000 "
        f"value={best_ms_per_1000:.6f} unit=ms lower_is_better=true"
    )
    print(
        "metric=clean_text_stdev_ms_per_1000 "
        f"value={stdev_ms_per_1000:.6f} unit=ms lower_is_better=true"
    )


if __name__ == "__main__":
    main()
