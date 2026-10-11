import os
import pickle
import re
import threading
import webbrowser
from pathlib import Path
from threading import Event, Timer
from typing import Any

import dash
import dash_cytoscape as cyto
import networkx as nx
from dash import Input, Output, State, ctx, dcc, html
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

_ROLE_COLORS = {
    "feature": "#4C78A8",
    "hidden": "#9AA0A6",
    "target": "#E45756",
}


def _valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.fullmatch(name)) and name not in {".", ".."}


def discover_items(cache_dir: Path) -> list[dict[str, str]]:
    """Discover cached graphs and graph batches."""
    if not cache_dir.exists():
        return []

    items = []

    for path in cache_dir.iterdir():
        if not _valid_name(path.stem if path.is_file() else path.name):
            continue

        if path.is_file() and path.suffix == ".graph":
            items.append({"label": path.stem, "value": path.stem, "type": "graph"})
        elif path.is_dir() and any(
            child.is_file() and child.suffix == ".graph" for child in path.iterdir()
        ):
            items.append(
                {"label": f"{path.name} (batch)", "value": path.name, "type": "batch"}
            )

    return sorted(items, key=lambda item: item["label"].lower())


def _graph_files(batch_path: Path) -> list[Path]:
    """Return batch graphs in numeric order where possible."""
    files = [
        path
        for path in batch_path.iterdir()
        if path.is_file() and path.suffix == ".graph"
    ]

    def sort_key(path: Path) -> tuple[int, int | str]:
        stem = path.stem
        return (0, int(stem)) if stem.isdigit() else (1, stem.lower())

    return sorted(files, key=sort_key)


def load_graph(cache_dir: Path, name: str, graph_name: str | None = None) -> nx.Graph:
    """Load a standalone graph or a graph within a batch."""
    if not _valid_name(name):
        raise ValueError("Invalid graph or batch name.")

    if graph_name is not None:
        if not _valid_name(graph_name):
            raise ValueError("Invalid graph name.")

        path = cache_dir / name / f"{graph_name}.graph"
    else:
        path = cache_dir / f"{name}.graph"

        if not path.is_file():
            batch_path = cache_dir / name

            if not batch_path.is_dir():
                raise FileNotFoundError(f"No graph or batch named {name!r}.")

            files = _graph_files(batch_path)
            if not files:
                raise FileNotFoundError(f"Batch {name!r} contains no graphs.")

            path = files[0]

    with path.open("rb") as file:
        graph = pickle.load(file)

    if not isinstance(graph, nx.Graph):
        raise TypeError(f"{path} does not contain a NetworkX graph.")

    return graph


def graph_elements(graph: nx.Graph) -> list[dict[str, Any]]:
    """Convert a NetworkX graph into Cytoscape elements."""
    elements = []

    for node, attributes in graph.nodes(data=True):
        if isinstance(graph, nx.DiGraph):
            if graph.in_degree(node) == 0:
                role = "feature"
            elif graph.out_degree(node) == 0:
                role = "target"
            else:
                role = "hidden"
        else:
            role = "feature" if graph.degree(node) <= 1 else "hidden"

        elements.append(
            {
                "data": {
                    "id": str(node),
                    "label": str(node),
                    "role": role,
                    "details": f"Node: {node}\nRole: {role}\nDegree: {graph.degree(node)}",
                },
                # "position": {
                #     "x": float(attributes["pos"][0]),
                #     "y": float(attributes["pos"][1]),
                # },
                "classes": role,
            }
        )

    for index, (source, target) in enumerate(graph.edges()):
        elements.append(
            {
                "data": {
                    "id": f"edge-{index}",
                    "source": str(source),
                    "target": str(target),
                }
            }
        )

    return elements


def graph_status(graph: nx.Graph) -> str:
    metadata = graph.graph
    parameters = metadata.get("parameters", {})
    nx_arguments = metadata.get("nx_arguments", {})

    return (
        f"{graph.number_of_nodes()} nodes · {graph.number_of_edges()} edges\n"
        f"Model: {metadata.get('model', 'Unknown')}\n"
        f"Parameters: {parameters}\n"
        f"NetworkX arguments: {nx_arguments}"
    )


def create_app(cache_dir: Path, initial_name: str | None = None) -> dash.Dash:
    """Create the interactive graph browser."""
    items = discover_items(cache_dir)
    item_names = {item["value"] for item in items}

    if initial_name is not None and initial_name not in item_names:
        raise FileNotFoundError(f"No graph or batch named {initial_name!r}.")

    default_name = initial_name or (items[0]["value"] if items else None)
    default_item = next((item for item in items if item["value"] == default_name), None)
    is_batch = default_item is not None and default_item["type"] == "batch"

    batch_files = (
        _graph_files(cache_dir / default_name)
        if default_name is not None and is_batch
        else []
    )
    default_graph_name = batch_files[0].stem if batch_files else None

    try:
        initial_graph = (
            load_graph(cache_dir, default_name, default_graph_name)
            if default_name is not None
            else nx.DiGraph()
        )
        initial_elements = graph_elements(initial_graph)
        initial_status = graph_status(initial_graph)
        initial_layout_command = {
            "action": "restart",
            "graph_key": f"{default_name}:{default_graph_name if is_batch else None}",
            "node_count": initial_graph.number_of_nodes(),
        }
    except (OSError, ValueError, TypeError, pickle.UnpicklingError) as exc:
        initial_elements = []
        initial_status = str(exc)
        initial_layout_command = {
            "action": "restart",
            "graph_key": "empty",
            "node_count": 0,
        }

    app = dash.Dash(__name__)
    app.title = "QSCM Graph Browser"

    cyto.load_extra_layouts()

    app.layout = html.Div(
        [
            dcc.Store(id="cached-items", data=items),
            dcc.Interval(id="refresh-items", interval=2_000, n_intervals=0),
            dcc.Interval(
                id="layout-init", interval=250, max_intervals=1, n_intervals=0
            ),
            html.Div(
                [
                    html.Div(
                        [
                            dcc.Dropdown(
                                id="item-selector",
                                options=items,
                                value=default_name,
                                placeholder="Search graphs and batches...",
                                searchable=True,
                                clearable=False,
                                style={"width": "320px"},
                            ),
                            html.Button(
                                "←",
                                id="prev-item",
                                n_clicks=0,
                                title="Previous graph or batch",
                            ),
                            html.Button(
                                "→",
                                id="next-item",
                                n_clicks=0,
                                title="Next graph or batch",
                            ),
                            html.Div(
                                [
                                    dcc.Dropdown(
                                        id="graph-selector",
                                        options=[
                                            {"label": path.name, "value": path.stem}
                                            for path in batch_files
                                        ],
                                        value=default_graph_name,
                                        placeholder="Select graph...",
                                        searchable=True,
                                        clearable=False,
                                        style={"width": "160px"},
                                    ),
                                    html.Button(
                                        "←",
                                        id="prev-graph",
                                        n_clicks=0,
                                        title="Previous graph",
                                    ),
                                    html.Button(
                                        "→",
                                        id="next-graph",
                                        n_clicks=0,
                                        title="Next graph",
                                    ),
                                ],
                                id="batch-navigation",
                                style={
                                    "display": "flex" if is_batch else "none",
                                    "alignItems": "center",
                                    "gap": "4px",
                                },
                            ),
                            html.Button("Pause layout", id="layout-toggle", n_clicks=0),
                            dcc.Store(id="layout-command", data=initial_layout_command),
                            dcc.Store(id="layout-command-result"),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "8px",
                            "flexWrap": "wrap",
                            "maxWidth": "calc(100vw - 24px)",
                        },
                    ),
                    html.Div(
                        id="graph-status",
                        children=initial_status,
                        style={
                            "fontSize": "12px",
                            "color": "#555",
                            "whiteSpace": "pre-line",
                        },
                    ),
                ],
                style={
                    "position": "absolute",
                    "zIndex": 10,
                    "top": "12px",
                    "left": "12px",
                    "display": "flex",
                    "flexDirection": "column",
                    "alignItems": "flex-start",
                    "gap": "8px",
                    "maxWidth": "calc(100vw - 24px)",
                },
            ),
            cyto.Cytoscape(
                id="graph-canvas",
                elements=initial_elements,
                layout={"name": "preset"},
                stylesheet=[
                    {
                        "selector": "node",
                        "style": {
                            "label": "data(label)",
                            "background-color": "#9AA0A6",
                            "color": "#202124",
                            "font-size": "10px",
                            "text-valign": "top",
                            "text-margin-y": -6,
                            "width": 24,
                            "height": 24,
                            "border-width": 1,
                            "border-color": "#FFFFFF",
                        },
                    },
                    {
                        "selector": ".feature",
                        "style": {"background-color": _ROLE_COLORS["feature"]},
                    },
                    {
                        "selector": ".hidden",
                        "style": {"background-color": _ROLE_COLORS["hidden"]},
                    },
                    {
                        "selector": ".target",
                        "style": {"background-color": _ROLE_COLORS["target"]},
                    },
                    {
                        "selector": "edge",
                        "style": {
                            "width": 1.5,
                            "line-color": "#9AA0A6",
                            "target-arrow-color": "#9AA0A6",
                            "target-arrow-shape": "triangle",
                            "curve-style": "bezier",
                        },
                    },
                ],
                minZoom=0.05,
                maxZoom=5,
                zoom=1,
                wheelSensitivity=0.1,
                pan={"x": 0, "y": 0},
                userZoomingEnabled=True,
                userPanningEnabled=True,
                boxSelectionEnabled=True,
                autoungrabify=False,
                style={"width": "100vw", "height": "100vh"},
            ),
        ],
        style={"width": "100vw", "height": "100vh", "overflow": "hidden"},
    )

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

        files = _graph_files(cache_dir / name)
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
        name: str | None, graph_name: str | None, current_items: list[dict[str, str]]
    ):

        def make_layout_command(graph_key="empty", node_count=0):
            return {
                "action": "restart",
                "graph_key": graph_key,
                "node_count": node_count,
            }

        if name is None:
            return (
                [],
                "No cached graphs found.",
                make_layout_command(),
            )

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
            return ([], str(exc), make_layout_command(f"{name}:{selected_graph}"))

        return (
            graph_elements(graph),
            graph_status(graph),
            make_layout_command(
                f"{name}:{selected_graph}",
                graph.number_of_nodes(),
            ),
        )

    app.clientside_callback(
        """
        function(command, nClicks, initCount) {
            const noUpdate = window.dash_clientside.no_update;
            const triggered = window.dash_clientside.callback_context.triggered_id;

            let controller = window.qscmLayoutController;

            if (!controller) {
                controller = {
                    layout: null,
                    timer: null,
                    manual: false,
                    running: false,
                    graphKey: null,
                };
                window.qscmLayoutController = controller;
            }

            function setButtonLabel(label) {
                window.dash_clientside.set_props("layout-toggle", {
                    children: label,
                });
            }

            function stopLayout() {
                if (controller.layout) {
                    controller.layout.stop();
                }
                controller.running = false;
            }

            function startLayout() {
                if (controller.layout) {
                    controller.layout.run();
                    controller.running = true;
                }
            }

            function cancelTimer() {
                if (controller.timer !== null) {
                    clearTimeout(controller.timer);
                    controller.timer = null;
                }
            }

            function cola_layout() {
                return {
                    "name": "cola",
                    "infinite": true,
                    "animate": true,
                    "fit": false,
                    "refresh": 10,
                    "ungrabifyWhileSimulating": false,
                    "avoidOverlap": true,
                    "handleDisconnected": true,
                    "nodeSpacing": 10,
                    "edgeLength": 50,
                };
            }

            if (triggered === "layout-command" || triggered === "layout-init") {
                if (!command || command.action !== "restart") {
                    return noUpdate;
                }

                cancelTimer();
                stopLayout();

                controller.manual = false;
                controller.graphKey = command.graph_key;
                controller.layout = cy.layout(cola_layout());

                setButtonLabel("Pause layout");

                // Wait for Dash/React to apply the newly selected graph.
                function waitForGraph(attempt = 0) {
                    if (controller.graphKey !== command.graph_key) {
                        return;
                    }

                    const cy = window.cy;

                    if (!cy || cy.nodes().length !== command.node_count) {
                        if (attempt < 100) {
                            controller.timer = setTimeout(() => {
                                controller.timer = null;
                                waitForGraph(attempt + 1);
                            }, 50);
                        }
                        return;
                    }

                    startLayout();
                    setTimeout(() => {
                        cy.fit(undefined, 30);
                    }, 1000);

                    controller.timer = setTimeout(() => {
                        if (!controller.manual) {
                            stopLayout();
                            setButtonLabel("Play layout");
                        }
                        controller.timer = null;
                    }, 6000);
                }

                waitForGraph();

                return noUpdate;
            }

            if (triggered === "layout-toggle") {
                cancelTimer();
                controller.manual = true;

                if (controller.running) {
                    stopLayout();
                    setButtonLabel("Play layout");
                } else {
                    startLayout();
                    setButtonLabel("Pause layout");
                }
            }

            return noUpdate;
        }
        """,
        Output("layout-command-result", "data"),
        Input("layout-command", "data"),
        Input("layout-toggle", "n_clicks"),
        Input("layout-init", "n_intervals"),
        prevent_initial_call=True,
    )

    @app.callback(
        Output("item-selector", "options"),
        Input("cached-items", "data"),
    )
    def update_item_options(current_items):
        return current_items

    # watch dog

    refresh_timer: Timer | None = None
    changes_detected = Event()

    class CacheEventHandler(FileSystemEventHandler):
        def on_any_event(self, event):
            path = Path(os.fsdecode(event.src_path))
            if path.suffix != ".graph" and not event.is_directory:
                return

            schedule_refresh()

    def signal_refresh():
        changes_detected.set()

    def schedule_refresh():
        nonlocal refresh_timer

        if refresh_timer is not None:
            refresh_timer.cancel()

        refresh_timer = Timer(0.2, signal_refresh)
        refresh_timer.daemon = True
        refresh_timer.start()

    @app.callback(
        Output("cached-items", "data"),
        Input("refresh-items", "n_intervals"),
    )
    def refresh_items(_n_intervals: int):
        if not changes_detected.is_set():
            return dash.no_update

        changes_detected.clear()
        return discover_items(cache_dir)

    observer = Observer()
    observer.schedule(CacheEventHandler(), str(cache_dir), recursive=True)
    observer.daemon = True
    observer.start()

    return app


def run_visualizer(cache_dir: Path, name: str | None = None) -> None:
    """Start the graph browser and open it in the default browser."""
    cache_dir = Path(cache_dir)
    app = create_app(cache_dir, initial_name=name)

    threading.Timer(
        1.0,
        lambda: webbrowser.open("http://127.0.0.1:8050"),
    ).start()

    app.run(host="127.0.0.1", port=8050, debug=False)
