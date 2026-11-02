"""Which graph is selected: item dropdown, batch dropdown, prev/next/random."""

import random
from pathlib import Path

from qscm.cache import discover_items, graph_files

HIDDEN = "toolbar-group is-hidden"
SHOWN = "toolbar-group"


def _step(names: list[str], current: str | None, step: int) -> str | None:
    """Cyclic neighbour of `current`; starts from an end if it is not in `names`."""
    if not names:
        return None
    if current not in names:
        return names[0] if step > 0 else names[-1]
    return names[(names.index(current) + step) % len(names)]


def _random_other(names: list[str], current: str | None) -> str:
    choices = [name for name in names if name != current] or names
    return random.choice(choices)


def register(app, cache_dir: Path) -> None:
    import dash

    # Single owner of item-selector's options and value.
    @app.callback(
        dash.Output("item-selector", "options"),
        dash.Output("item-selector", "value"),
        dash.Input("cached-items", "data"),
        dash.Input("prev-item", "n_clicks"),
        dash.Input("next-item", "n_clicks"),
        dash.Input("random-graph", "n_clicks"),
        dash.State("item-selector", "value"),
    )
    def choose_item(items, _prev, _next, _random, current):
        items = items or []
        names = [item["value"] for item in items]
        trigger = dash.ctx.triggered_id

        if trigger == "prev-item":
            return dash.no_update, _step(names, current, -1)

        if trigger == "next-item":
            return dash.no_update, _step(names, current, +1)

        if trigger == "random-graph":
            selected = next((i for i in items if i["value"] == current), None)

            # With a batch selected, "random" picks inside the batch instead
            # (see choose_graph).
            if selected is not None and selected["type"] == "batch":
                return dash.no_update, dash.no_update

            graphs = [i["value"] for i in items if i["type"] == "graph"]
            return dash.no_update, _random_other(
                graphs, current
            ) if graphs else dash.no_update

        # Initial call, or the list of cached items changed.
        value = current if current in names else (names[0] if names else None)
        return items, value

    # Single owner of graph-selector and of the batch row's visibility.
    @app.callback(
        dash.Output("graph-selector", "options"),
        dash.Output("graph-selector", "value"),
        dash.Output("batch-navigation", "className"),
        dash.Input("item-selector", "value"),
        dash.Input("prev-graph", "n_clicks"),
        dash.Input("next-graph", "n_clicks"),
        dash.Input("random-graph", "n_clicks"),
        dash.State("graph-selector", "value"),
        dash.State("cached-items", "data"),
    )
    def choose_graph(name, _prev, _next, _random, current, items):
        item = next((i for i in items or [] if i["value"] == name), None)

        if item is None or item["type"] != "batch":
            return [], None, HIDDEN

        try:
            files = graph_files(cache_dir / name)
        except OSError:  # batch deleted while it was selected
            return [], None, HIDDEN

        options = [{"label": path.name, "value": path.stem} for path in files]
        names = [option["value"] for option in options]

        if not names:
            return options, None, SHOWN

        trigger = dash.ctx.triggered_id

        if trigger == "random-graph":
            value = _random_other(names, current)
        elif trigger == "next-graph":
            value = _step(names, current, +1)
        elif trigger == "prev-graph":
            value = _step(names, current, -1)
        else:
            value = current if current in names else names[0]

        return options, value, SHOWN

    # Poll the cache directory for new or deleted graphs and batches.
    @app.callback(
        dash.Output("cached-items", "data"),
        dash.Input("refresh-items", "n_intervals"),
        dash.State("cached-items", "data"),
    )
    def refresh_items(_n_intervals, current_items):
        discovered = discover_items(cache_dir)
        return dash.no_update if discovered == (current_items or []) else discovered
