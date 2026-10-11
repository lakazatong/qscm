import os
import pickle
import random
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
        Input("random-graph", "n_clicks"),
        State("item-selector", "value"),
        State("cached-items", "data"),
        prevent_initial_call=True,
    )
    def navigate_items(_, __, _random_clicks, current_name, current_items):
        if not current_items:
            return None

        if ctx.triggered_id == "random-graph":
            current = next(
                (item for item in current_items if item["value"] == current_name),
                None,
            )

            # If a batch is selected, let update_batch_selector pick its graph.
            if current is not None and current["type"] == "batch":
                return current_name

            names = [item["value"] for item in current_items if item["type"] == "graph"]

            if len(names) > 1 and current_name in names:
                names.remove(current_name)

            return random.choice(names) if names else current_name

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
        Input("random-graph", "n_clicks"),
        State("graph-selector", "value"),
        State("cached-items", "data"),
    )
    def update_batch_selector(
        name, _, __, _random_clicks, current_graph, current_items
    ):
        item = next(
            (item for item in current_items if item["value"] == name),
            None,
        )

        if item is None or item["type"] != "batch":
            return [], None, {"display": "none"}

        files = graph_files(cache_dir / name)
        options = [{"label": path.name, "value": path.stem} for path in files]
        names = [option["value"] for option in options]

        if ctx.triggered_id == "random-graph" and names:
            choices = names.copy()

            if len(choices) > 1 and current_graph in choices:
                choices.remove(current_graph)

            return (
                options,
                random.choice(choices),
                {
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "4px",
                },
            )

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
        Input("reload-graph", "n_clicks"),
        State("cached-items", "data"),
    )
    def update_graph(
        name: str | None,
        graph_name: str | None,
        reload_clicks: int,
        current_items: list[dict[str, str]],
    ):

        def make_layout_command(graph_key="empty", node_count=0):
            return {
                "action": "restart",
                "graph_key": graph_key,
                "node_count": node_count,
                "reload_token": reload_clicks or 0,
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
        # print(
        #     "Callback output:",
        #     "nodes =",
        #     sum("source" not in e["data"] for e in elements),
        #     "edges =",
        #     sum("source" in e["data"] for e in elements),
        #     "edge-43 =",
        #     next(
        #         (e for e in elements if e["data"].get("id") == "edge-43"),
        #         None,
        #     ),
        # )

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
        Output("item-selector", "value"),
        Input("cached-items", "data"),
        State("item-selector", "value"),
    )
    def update_item_options(current_items, current_name):
        names = {item["value"] for item in current_items}

        if current_name in names:
            value = current_name
        else:
            value = current_items[0]["value"] if current_items else None

        return current_items, value

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
        def __init__(self, cache_dir: Path):
            self.cache_dir = cache_dir.resolve()

        def on_any_event(self, event):
            path = Path(os.fsdecode(event.src_path)).resolve()

            try:
                path.relative_to(self.cache_dir)
            except ValueError:
                return

            # print(
            #     "[watchdog event]",
            #     event.event_type,
            #     repr(event.src_path),
            #     "directory:",
            #     event.is_directory,
            # )

            if not event.is_directory and path.suffix != ".graph":
                return

            schedule_refresh()

    @app.callback(
        Output("cached-items", "data"),
        Input("refresh-items", "n_intervals"),
        State("cached-items", "data"),
    )
    def refresh_items(_n_intervals: int, current_items):
        discovered = discover_items(cache_dir)

        if discovered == (current_items or []):
            return dash.no_update

        return discovered

    observer = Observer()
    observer.schedule(
        CacheEventHandler(cache_dir),
        str(cache_dir.parent),
        recursive=True,
    )
    observer.daemon = True
    observer.start()

    print("[watchdog] alive:", observer.is_alive())
    print("[watchdog] watching parent:", cache_dir.parent.resolve())
    print("[watchdog] cache:", cache_dir.resolve())
