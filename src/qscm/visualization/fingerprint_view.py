"""Histogram cards for the fingerprint sidebar."""

from __future__ import annotations

from math import inf
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import dash

from qscm.data import Fingerprint, Histogram


def histogram_card(name: str, histogram: Histogram) -> dash.html.Div:
    import dash

    maximum = max(histogram.values(), default=0)

    bars = [
        dash.html.Div(
            [
                dash.html.Div(
                    className="bar",
                    title=f"{'∞' if value == inf else value}: {probability:.4f}",
                    style={
                        "height": f"{probability / maximum * 100 if maximum else 0:.2f}%",
                    },
                ),
                dash.html.Div(
                    "∞" if value == inf else str(value),
                    className="bar-label",
                ),
            ],
            className="bar-column",
        )
        for value, probability in sorted(histogram.items())
    ]

    return dash.html.Div(
        [
            dash.html.Strong(name),
            dash.html.Div(bars, className="bars"),
        ],
        className="fingerprint-card",
    )


def fingerprint_cards(fingerprint: Fingerprint) -> list[dash.html.Div]:
    return [histogram_card(name, histogram) for name, histogram in fingerprint.items()]
