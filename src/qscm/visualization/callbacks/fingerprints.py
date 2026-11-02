"""Fingerprint histograms for the selected graph."""

import pickle
from pathlib import Path

from qscm.cache import load_graph
from qscm.data import require_digraph
from qscm.fingerprint import graph_fingerprint
from qscm.visualization.fingerprint_view import fingerprint_cards


def register(app, cache_dir: Path) -> None:
    import dash

    @app.callback(
        dash.Output("fingerprint-content", "children"),
        dash.Input("fingerprints-open", "data"),
        dash.Input("item-selector", "value"),
        dash.Input("graph-selector", "value"),
        prevent_initial_call=True,
    )
    def update_fingerprints(is_open, name, graph_name):
        # Recomputed when the panel opens and whenever the selection changes
        # while it is open; never while it is closed.
        if not is_open:
            return dash.no_update

        if name is None:
            return "Select a graph first."

        try:
            graph = load_graph(cache_dir, name, graph_name)
            if require_digraph(graph):
                return fingerprint_cards(graph_fingerprint(graph))
        except (OSError, ValueError, TypeError, pickle.UnpicklingError) as exc:
            return f"Could not compute fingerprints: {exc}"
