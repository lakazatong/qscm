"""Static page layout. All styling lives in assets/qscm.css."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import dash

from .cytoscape import STYLESHEET


def _button(label: str, id: str, title: str | None = None) -> dash.html.Button:
    import dash

    return dash.html.Button(label, id=id, n_clicks=0, title=title)


def _toolbar(items, default_name) -> dash.html.Div:
    import dash

    return dash.html.Div(
        [
            dash.html.Div(
                _button(
                    "Hide metadata",
                    "toggle-metadata",
                    "Show or hide graph metadata",
                ),
                className="toolbar-group",
            ),
            dash.html.Div(
                [
                    dash.dcc.Dropdown(
                        id="item-selector",
                        options=items,
                        value=default_name,
                        placeholder="Search graphs and batches...",
                        searchable=True,
                        clearable=False,
                        style={"width": "320px"},
                    ),
                    _button("←", "prev-item", "Previous graph or batch"),
                    _button("→", "next-item", "Next graph or batch"),
                ],
                className="toolbar-group",
            ),
            # Only shown while a batch is selected.
            dash.html.Div(
                [
                    dash.dcc.Dropdown(
                        id="graph-selector",
                        options=[],
                        placeholder="Select graph...",
                        searchable=True,
                        clearable=False,
                        style={"width": "160px"},
                    ),
                    _button("←", "prev-graph", "Previous graph"),
                    _button("→", "next-graph", "Next graph"),
                ],
                id="batch-navigation",
                className="toolbar-group is-hidden",
            ),
            dash.html.Div(
                [
                    _button("Reload graph", "reload-graph"),
                    _button("Random graph", "random-graph"),
                ],
                className="toolbar-group",
            ),
            dash.html.Div(
                [
                    _button("Pause layout", "layout-toggle"),
                    _button("Fit graph", "fit-graph"),
                ],
                className="toolbar-group",
            ),
            dash.html.Div(
                _button("Fingerprints", "toggle-fingerprints"),
                className="toolbar-group",
            ),
        ],
        className="toolbar",
    )


def _graph_pane() -> dash.html.Div:
    import dash
    import dash_cytoscape as cyto

    return dash.html.Div(
        [
            # The canvas is only a host: the browser fills it directly
            # (see assets/qscm.js), so `elements` stays empty on purpose.
            cyto.Cytoscape(
                id="graph-canvas",
                elements=[],
                layout={"name": "preset"},
                stylesheet=STYLESHEET,
                minZoom=0.05,
                maxZoom=5,
                zoom=1,
                wheelSensitivity=0.1,
                pan={"x": 0, "y": 0},
                userZoomingEnabled=True,
                userPanningEnabled=True,
                boxSelectionEnabled=True,
                autoungrabify=False,
                style={
                    "position": "absolute",
                    "inset": 0,
                    "width": "100%",
                    "height": "100%",
                },
            ),
            dash.html.Div(
                dash.html.Div(id="graph-status"),
                id="metadata-panel",
                className="metadata-panel",
            ),
        ],
        className="graph-pane",
    )


def _fingerprint_sidebar() -> dash.html.Div:
    import dash

    return dash.html.Div(
        [
            dash.html.Div(
                [
                    dash.html.Strong("Fingerprints"),
                    dash.html.Div(
                        [
                            _button("Expand", "expand-fingerprints"),
                            _button("Close", "close-fingerprints"),
                        ],
                        className="sidebar-actions",
                    ),
                ],
                className="sidebar-header",
            ),
            dash.html.Div(
                "Click Fingerprints to compute the graph fingerprints.",
                id="fingerprint-content",
                className="fingerprint-grid",
            ),
        ],
        id="fingerprint-sidebar",
        className="sidebar",
    )


def create_layout(items, default_name) -> dash.html.Div:
    import dash

    return dash.html.Div(
        [
            # Client-side state
            dash.dcc.Store(id="cached-items", data=items),
            dash.dcc.Store(id="graph-data"),
            dash.dcc.Store(id="panel-state", data={"open": False, "expanded": False}),
            dash.dcc.Store(id="fingerprints-open", data=False),
            dash.dcc.Store(id="layout-sink"),
            dash.dcc.Interval(id="refresh-items", interval=2_000),
            _toolbar(items, default_name),
            dash.html.Div(
                [
                    _graph_pane(),
                    dash.html.Div(
                        id="fingerprint-resize-handle",
                        className="resize-handle",
                        title="Drag to resize",
                    ),
                    _fingerprint_sidebar(),
                ],
                id="visualization-workspace",
                className="workspace",
            ),
        ],
        className="app",
    )
