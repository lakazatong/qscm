from pathlib import Path

import dash

from . import client, fingerprints, graph, navigation


def register_callbacks(app: dash.Dash, cache_dir: Path) -> None:
    navigation.register(app, cache_dir)
    graph.register(app, cache_dir)
    fingerprints.register(app, cache_dir)
    client.register(app)
