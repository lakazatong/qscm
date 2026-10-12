"""Loading the selected graph and handing it to the browser."""

import pickle
from pathlib import Path

from dash import Input, Output, State

from qscm.cache import load_graph
from qscm.visualization.cytoscape import empty_payload, graph_payload, graph_status


def register(app, cache_dir: Path) -> None:
    @app.callback(
        Output("graph-data", "data"),
        Output("graph-status", "children"),
        Input("item-selector", "value"),
        Input("graph-selector", "value"),
        Input("reload-graph", "n_clicks"),
        State("cached-items", "data"),
    )
    def update_graph(name, graph_name, reload_clicks, items):
        token = reload_clicks or 0

        if name is None:
            return empty_payload(token), "No cached graphs found."

        item = next((i for i in items or [] if i["value"] == name), None)
        if item is None:
            return empty_payload(token), "Unknown graph or batch."

        selected_graph = graph_name if item["type"] == "batch" else None

        try:
            graph = load_graph(cache_dir, name, selected_graph)
        except (OSError, ValueError, TypeError, pickle.UnpicklingError) as exc:
            return empty_payload(token), str(exc)

        return (
            graph_payload(graph, f"{name}:{selected_graph}", token),
            graph_status(graph),
        )
