"""Engine protocol for the review pipeline."""

from __future__ import annotations

from typing import Protocol


class ReviewEngine(Protocol):
    """A review engine turns an assembled context into a markdown report."""

    name: str

    def generate(self, system: str, user: str, ctx) -> str:  # noqa: ANN001
        """Return the raw markdown response for the given context."""
        ...
