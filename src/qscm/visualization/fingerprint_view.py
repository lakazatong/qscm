"""Histogram cards for the fingerprint sidebar."""

from math import inf

from dash import html

from qscm.data import Fingerprint, Histogram


def histogram_card(name: str, histogram: Histogram) -> html.Div:
    maximum = max(histogram.values(), default=0)

    bars = [
        html.Div(
            className="bar",
            title=f"{'∞' if value == inf else value}: {probability:.4f}",
            style={"height": f"{probability / maximum * 100 if maximum else 0:.2f}%"},
        )
        for value, probability in sorted(histogram.items())
    ]

    return html.Div(
        [
            html.Strong(name),
            html.Div(bars, className="bars"),
            html.Div(
                f"{len(histogram)} bins · normalized distribution",
                className="card-caption",
            ),
        ],
        className="fingerprint-card",
    )


def fingerprint_cards(fingerprint: Fingerprint) -> list[html.Div]:
    return [histogram_card(name, histogram) for name, histogram in fingerprint.items()]
