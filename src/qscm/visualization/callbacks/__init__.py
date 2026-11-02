from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import dash

from . import client, fingerprints, graph, navigation


def register_callbacks(app: dash.Dash, cache_dir: Path) -> None:
    navigation.register(app, cache_dir)
    graph.register(app, cache_dir)
    fingerprints.register(app, cache_dir)
    client.register(app)
