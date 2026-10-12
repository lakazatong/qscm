import threading
import webbrowser
from pathlib import Path

import dash
import dash_cytoscape as cyto

from qscm.cache import discover_items
from qscm.config import APP_TITLE, ASSETS_DIR, DASH_HOST, DASH_PORT

from .callbacks import register_callbacks
from .layout import create_layout


def create_app(cache_dir: Path, initial_name: str | None = None) -> dash.Dash:
    """Create the interactive graph browser."""
    items = discover_items(cache_dir)

    if initial_name is not None and initial_name not in {i["value"] for i in items}:
        raise FileNotFoundError(f"No graph or batch named {initial_name!r}.")

    default_name = initial_name or (items[0]["value"] if items else None)

    app = dash.Dash(__name__, assets_folder=str(ASSETS_DIR))
    app.title = APP_TITLE
    cyto.load_extra_layouts()

    # The first graph is loaded by the same callbacks that handle every later
    # selection, so there is no separate "initial render" path to keep in sync.
    app.layout = create_layout(items, default_name)
    register_callbacks(app, cache_dir)
    return app


def run_visualizer(cache_dir: Path, name: str | None = None) -> None:
    """Start the graph browser and open it in the default browser."""
    app = create_app(cache_dir, initial_name=name)

    threading.Timer(
        1.0, lambda: webbrowser.open(f"http://{DASH_HOST}:{DASH_PORT}")
    ).start()

    app.run(host=DASH_HOST, port=DASH_PORT, debug=False)
