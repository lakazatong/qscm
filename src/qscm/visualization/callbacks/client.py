"""Callbacks that run in the browser; the code is in assets/qscm.js."""

from dash import ClientsideFunction, Input, Output, State


def _fn(name: str) -> ClientsideFunction:
    return ClientsideFunction(namespace="qscm", function_name=name)


def register(app) -> None:
    app.clientside_callback(
        _fn("toggle_metadata"),
        Output("metadata-panel", "className"),
        Output("toggle-metadata", "children"),
        Input("toggle-metadata", "n_clicks"),
    )

    app.clientside_callback(
        _fn("panel"),
        Output("visualization-workspace", "className"),
        Output("toggle-fingerprints", "children"),
        Output("expand-fingerprints", "children"),
        Output("panel-state", "data"),
        Output("fingerprints-open", "data"),
        Input("toggle-fingerprints", "n_clicks"),
        Input("close-fingerprints", "n_clicks"),
        Input("expand-fingerprints", "n_clicks"),
        State("panel-state", "data"),
        prevent_initial_call=True,
    )

    # Replaces the canvas contents and runs the layout engine. Output is a
    # dummy store: the real effects happen on the Cytoscape instance.
    app.clientside_callback(
        _fn("layout"),
        Output("layout-sink", "data"),
        Input("graph-data", "data"),
        Input("layout-toggle", "n_clicks"),
        Input("fit-graph", "n_clicks"),
    )
