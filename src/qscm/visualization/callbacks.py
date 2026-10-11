import os
import pickle
from pathlib import Path
from threading import Event, Timer

import dash
from dash import Input, Output, State, ctx

from qscm.visualization.cytoscape import (
    discover_items,
    graph_elements,
    graph_files,
    graph_status,
    load_graph,
)
from qscm.visualization.layout_js import LAYOUT_CALLBACK


def register_callbacks(app: dash.Dash, cache_dir: Path) -> None:
    @app.callback(
        Output("item-selector", "value"),
        Input("prev-item", "n_clicks"),
        Input("next-item", "n_clicks"),
        State("item-selector", "value"),
        State("cached-items", "data"),
        prevent_initial_call=True,
    )
    def navigate_items(_, __, current_name, current_items):
        if not current_items:
            return None

        names = [item["value"] for item in current_items]
        try:
            index = names.index(current_name)
        except ValueError:
            index = None

        if ctx.triggered_id == "next-item":
            return names[0] if index is None else names[(index + 1) % len(names)]

        return names[-1] if index is None else names[(index - 1) % len(names)]

    @app.callback(
        Output("graph-selector", "options"),
        Output("graph-selector", "value"),
        Output("batch-navigation", "style"),
        Input("item-selector", "value"),
        Input("prev-graph", "n_clicks"),
        Input("next-graph", "n_clicks"),
        State("graph-selector", "value"),
        State("cached-items", "data"),
    )
    def update_batch_selector(name, _, __, current_graph, current_items):
        item = next(
            (item for item in current_items if item["value"] == name),
            None,
        )

        if item is None or item["type"] != "batch":
            return [], None, {"display": "none"}

        files = graph_files(cache_dir / name)
        options = [{"label": path.name, "value": path.stem} for path in files]
        names = [option["value"] for option in options]

        style = {
            "display": "flex",
            "alignItems": "center",
            "gap": "4px",
        }

        if not names:
            return options, None, style

        try:
            index = names.index(current_graph)
        except ValueError:
            index = None

        if ctx.triggered_id == "next-graph":
            value = names[0] if index is None else names[(index + 1) % len(names)]
        elif ctx.triggered_id == "prev-graph":
            value = names[-1] if index is None else names[(index - 1) % len(names)]
        else:
            value = current_graph if current_graph in names else names[0]

        return options, value, style

    @app.callback(
        Output("graph-canvas", "elements"),
        Output("graph-status", "children"),
        Output("layout-command", "data"),
        Input("item-selector", "value"),
        Input("graph-selector", "value"),
        State("cached-items", "data"),
    )
    def update_graph(
        name: str | None,
        graph_name: str | None,
        current_items: list[dict[str, str]],
    ):
        def make_layout_command(graph_key="empty", node_count=0):
            return {
                "action": "restart",
                "graph_key": graph_key,
                "node_count": node_count,
            }

        if name is None:
            return [], "No cached graphs found.", make_layout_command()

        item = next(
            (item for item in current_items if item["value"] == name),
            None,
        )
        if item is None:
            return (
                [],
                "Unknown graph or batch.",
                make_layout_command(f"{name}:{graph_name}"),
            )

        selected_graph = graph_name if item["type"] == "batch" else None

        try:
            graph = load_graph(cache_dir, name, selected_graph)

        except (OSError, ValueError, TypeError, pickle.UnpicklingError) as exc:
            return (
                [],
                str(exc),
                make_layout_command(f"{name}:{selected_graph}"),
            )
        elements = graph_elements(graph)
        print(
            "Callback output:",
            "nodes =",
            sum("source" not in e["data"] for e in elements),
            "edges =",
            sum("source" in e["data"] for e in elements),
            "edge-43 =",
            next(
                (e for e in elements if e["data"].get("id") == "edge-43"),
                None,
            ),
        )

        return (
            elements,
            graph_status(graph),
            make_layout_command(
                f"{name}:{selected_graph}",
                graph.number_of_nodes(),
            ),
        )

    app.clientside_callback(
        LAYOUT_CALLBACK,
        Output("layout-command-result", "data"),
        Input("layout-command", "data"),
        Input("layout-toggle", "n_clicks"),
        Input("fit-graph", "n_clicks"),
        Input("layout-init", "n_intervals"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("item-selector", "options"),
        Input("cached-items", "data"),
    )
    def update_item_options(current_items):
        return current_items

    changes_detected = Event()
    refresh_timer: Timer | None = None

    def signal_refresh():
        changes_detected.set()

    def schedule_refresh():
        nonlocal refresh_timer

        if refresh_timer is not None:
            refresh_timer.cancel()

        refresh_timer = Timer(0.2, signal_refresh)
        refresh_timer.daemon = True
        refresh_timer.start()

    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    class CacheEventHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            path = Path(os.fsdecode(event.src_path))
            if path.suffix != ".graph" and not event.is_directory:
                return
            schedule_refresh()

    @app.callback(
        Output("cached-items", "data"),
        Input("refresh-items", "n_intervals"),
    )
    def refresh_items(_n_intervals: int):
        if not changes_detected.is_set():
            return dash.no_update

        changes_detected.clear()
        return discover_items(cache_dir)

    if cache_dir.exists():
        observer = Observer()
        observer.schedule(
            CacheEventHandler(),
            str(cache_dir),
            recursive=True,
        )
        observer.daemon = True
        observer.start()
