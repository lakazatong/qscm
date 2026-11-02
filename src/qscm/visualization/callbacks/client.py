"""Callbacks that run in the browser; the code is in assets/qscm.js."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import dash


def _fn(name: str) -> dash.ClientsideFunction:
    import dash

    return dash.ClientsideFunction(namespace="qscm", function_name=name)


def register(app) -> None:
    import dash

    app.clientside_callback(
        _fn("toggle_metadata"),
        dash.Output("metadata-panel", "className"),
        dash.Output("toggle-metadata", "children"),
        dash.Input("toggle-metadata", "n_clicks"),
    )

    app.clientside_callback(
        _fn("panel"),
        dash.Output("visualization-workspace", "className"),
        dash.Output("toggle-fingerprints", "children"),
        dash.Output("expand-fingerprints", "children"),
        dash.Output("panel-state", "data"),
        dash.Output("fingerprints-open", "data"),
        dash.Input("toggle-fingerprints", "n_clicks"),
        dash.Input("close-fingerprints", "n_clicks"),
        dash.Input("expand-fingerprints", "n_clicks"),
        dash.State("panel-state", "data"),
        prevent_initial_call=True,
    )

    # Replaces the canvas contents and runs the layout engine. Output is a
    # dummy store: the real effects happen on the Cytoscape instance.
    app.clientside_callback(
        _fn("layout"),
        dash.Output("layout-sink", "data"),
        dash.Input("graph-data", "data"),
        dash.Input("layout-toggle", "n_clicks"),
        dash.Input("fit-graph", "n_clicks"),
    )
