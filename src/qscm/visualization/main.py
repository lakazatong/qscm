import pickle
import threading
import webbrowser
from pathlib import Path

import dash
import dash_cytoscape as cyto
import networkx as nx

from qscm.visualization.callbacks import register_callbacks
from qscm.visualization.cytoscape import (
    discover_items,
    graph_elements,
    graph_files,
    graph_status,
    load_graph,
)
from qscm.visualization.layout import create_layout


def create_app(cache_dir: Path, initial_name: str | None = None) -> dash.Dash:
    """Create the interactive graph browser."""
    cache_dir = Path(cache_dir)
    items = discover_items(cache_dir)
    item_names = {item["value"] for item in items}

    if initial_name is not None and initial_name not in item_names:
        raise FileNotFoundError(f"No graph or batch named {initial_name!r}.")

    default_name = initial_name or (items[0]["value"] if items else None)
    default_item = next(
        (item for item in items if item["value"] == default_name),
        None,
    )
    is_batch = default_item is not None and default_item["type"] == "batch"

    batch_files = (
        graph_files(cache_dir / default_name)
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
            "graph_key": (f"{default_name}:{default_graph_name if is_batch else None}"),
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

    app = dash.Dash(__name__, assets_folder=str(Path(__file__).parent / "assets"))

    app.title = "QSCM Graph Browser"
    cyto.load_extra_layouts()

    app.layout = create_layout(
        items=items,
        default_name=default_name,
        default_graph_name=default_graph_name,
        batch_files=batch_files,
        is_batch=is_batch,
        initial_elements=initial_elements,
        initial_status=initial_status,
        initial_layout_command=initial_layout_command,
    )

    register_callbacks(app, cache_dir)
    return app


def run_visualizer(cache_dir: Path, name: str | None = None) -> None:
    """Start the graph browser and open it in the default browser."""
    app = create_app(Path(cache_dir), initial_name=name)

    threading.Timer(
        1.0,
        lambda: webbrowser.open("http://127.0.0.1:8050"),
    ).start()

    app.run(host="127.0.0.1", port=8050, debug=False)
