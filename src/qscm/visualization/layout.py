import dash_cytoscape as cyto
from dash import dcc, html

from qscm.visualization.cytoscape import ROLE_COLORS


def create_layout(
    items,
    default_name,
    default_graph_name,
    batch_files,
    is_batch,
    initial_elements,
    initial_status,
    initial_layout_command,
):
    return html.Div(
        [
            dcc.Store(id="cached-items", data=items),
            dcc.Interval(id="refresh-items", interval=2_000, n_intervals=0),
            dcc.Interval(
                id="layout-init",
                interval=250,
                max_intervals=1,
                n_intervals=0,
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
                            html.Button(
                                "Pause layout",
                                id="layout-toggle",
                                n_clicks=0,
                            ),
                            html.Button("Fit graph", id="fit-graph", n_clicks=0),
                            dcc.Store(
                                id="layout-command",
                                data=initial_layout_command,
                            ),
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
                            "background-color": ROLE_COLORS["hidden"],
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
                        "selector": ".isolated",
                        "style": {
                            "background-color": ROLE_COLORS["isolated"],
                        },
                    },
                    {
                        "selector": ".feature",
                        "style": {
                            "background-color": ROLE_COLORS["feature"],
                        },
                    },
                    {
                        "selector": ".hidden",
                        "style": {
                            "background-color": ROLE_COLORS["hidden"],
                        },
                    },
                    {
                        "selector": ".target",
                        "style": {
                            "background-color": ROLE_COLORS["target"],
                        },
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
        style={
            "width": "100vw",
            "height": "100vh",
            "overflow": "hidden",
        },
    )
