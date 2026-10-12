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
                            html.Button(
                                "Hide metadata",
                                id="toggle-metadata",
                                n_clicks=0,
                                title="Show or hide graph metadata",
                            ),
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
                            html.Button("Reload graph", id="reload-graph", n_clicks=0),
                            html.Button("Random graph", id="random-graph", n_clicks=0),
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
                            html.Button(
                                "Fingerprints", id="toggle-fingerprints", n_clicks=0
                            ),
                        ],
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "8px",
                            "flexWrap": "wrap",
                            "maxWidth": "calc(100vw - 24px)",
                        },
                    ),
                    # html.Div(
                    #     id="graph-status",
                    #     children=initial_status,
                    #     style={
                    #         "fontSize": "12px",
                    #         "color": "#555",
                    #         "whiteSpace": "pre-line",
                    #     },
                    # ),
                    # html.Div(
                    #     [
                    #         html.Button(
                    #             "Hide metadata",
                    #             id="toggle-metadata",
                    #             n_clicks=0,
                    #         ),
                    #         html.Div(
                    #             initial_status,
                    #             id="graph-status",
                    #             style={
                    #                 "fontSize": "12px",
                    #                 "color": "#374151",
                    #                 "whiteSpace": "pre-line",
                    #             },
                    #         ),
                    #     ],
                    #     id="metadata-panel",
                    #     style={
                    #         "background": "rgba(255, 255, 255, 0.95)",
                    #         "border": "1px solid #D1D5DB",
                    #         "borderRadius": "6px",
                    #         "padding": "8px 10px",
                    #         "boxShadow": "0 1px 4px rgba(0, 0, 0, 0.12)",
                    #         "maxWidth": "min(520px, calc(100vw - 24px))",
                    #     },
                    # ),
                    html.Div(
                        html.Div(
                            initial_status,
                            id="graph-status",
                            style={
                                "fontSize": "12px",
                                "color": "#374151",
                                "whiteSpace": "pre-line",
                            },
                        ),
                        id="metadata-panel",
                        style={
                            "background": "rgba(255, 255, 255, 0.95)",
                            "border": "1px solid #D1D5DB",
                            "borderRadius": "6px",
                            "padding": "8px 10px",
                            "boxShadow": "0 1px 4px rgba(0, 0, 0, 0.12)",
                            "maxWidth": "min(520px, calc(100vw - 24px))",
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
            html.Div(
                [
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
                            *[
                                {
                                    "selector": f".{role}",
                                    "style": {"background-color": color},
                                }
                                for role, color in ROLE_COLORS.items()
                            ],
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
                        style={
                            "flex": "1 1 auto",
                            "width": "100%",
                            "height": "100%",
                            "minWidth": 0,
                            "minHeight": 0,
                        },
                    ),
                    html.Div(
                        id="fingerprint-resize-handle",
                        title="Drag to resize",
                        style={
                            "display": "none",
                            "flex": "0 0 6px",
                            "cursor": "col-resize",
                            "background": "#D1D5DB",
                            "zIndex": 5,
                        },
                    ),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Strong("Fingerprints"),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Expand",
                                                id="expand-fingerprints",
                                                n_clicks=0,
                                            ),
                                            html.Button(
                                                "Close",
                                                id="close-fingerprints",
                                                n_clicks=0,
                                            ),
                                        ],
                                        style={
                                            "display": "flex",
                                            "gap": "8px",
                                        },
                                    ),
                                ],
                                style={
                                    "display": "flex",
                                    "alignItems": "center",
                                    "justifyContent": "space-between",
                                    "padding": "12px",
                                    "borderBottom": "1px solid #D1D5DB",
                                    "flex": "0 0 auto",
                                },
                            ),
                            html.Div(
                                "Click Fingerprints to compute the graph fingerprints.",
                                id="fingerprint-content",
                                style={
                                    "display": "grid",
                                    "gridTemplateColumns": "repeat(auto-fit, minmax(260px, 1fr))",
                                    "alignContent": "start",
                                    "gap": "12px",
                                    "padding": "12px",
                                    "overflowY": "auto",
                                },
                            ),
                        ],
                        id="fingerprint-sidebar",
                        style={
                            "display": "none",
                            "flex": "0 0 380px",
                            "width": "380px",
                            "minWidth": 0,
                            "minHeight": 0,
                            "flexDirection": "column",
                            "overflow": "hidden",
                            "background": "#F9FAFB",
                            "borderLeft": "1px solid #D1D5DB",
                        },
                    ),
                ],
                id="visualization-workspace",
                style={
                    "position": "absolute",
                    "inset": 0,
                    "display": "flex",
                    "overflow": "hidden",
                },
            ),
        ],
        style={
            "width": "100vw",
            "height": "100vh",
            "overflow": "hidden",
        },
    )
