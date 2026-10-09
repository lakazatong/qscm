from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from qscm.fingerprint import graph_fingerprint

from .fingerprint import require_digraph

_ROLE_COLORS = {
    "feature": "#4C78A8",
    "hidden": "#9AA0A6",
    "target": "#E45756",
}
_DEFAULT_NODE_COLOR = "#4C78A8"


def _graph_positions(
    graph: nx.Graph,
    seed: int = 42,
) -> dict[Any, tuple[float, float]]:
    """Prefer a general-purpose Graphviz layout, with a NetworkX fallback."""
    if graph.number_of_nodes() == 0:
        return {}

    try:
        positions = nx.nx_pydot.graphviz_layout(graph, prog="sfdp")
        return {
            node: (float(position[0]), float(position[1]))
            for node, position in positions.items()
        }
    except (ImportError, OSError, nx.NetworkXException, ValueError):
        positions = nx.spring_layout(graph, seed=seed)
        return {
            node: (float(position[0]), float(position[1]))
            for node, position in positions.items()
        }


def _node_color(graph: nx.Graph, node: object) -> str:
    directed_graph = graph.to_directed()

    if directed_graph.in_degree(node) == 0:
        return "#4C78A8"  # feature
    if directed_graph.out_degree(node) == 0:
        return "#E45756"  # target
    return "#9AA0A6"  # hidden


def _add_graph_traces(
    fig: go.Figure,
    graph: nx.Graph,
    *,
    row: int | None = None,
    col: int | None = None,
    seed: int = 42,
) -> None:
    positions = _graph_positions(graph, seed=seed)

    if not positions:
        return

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []

    for source, target in graph.edges():
        x0, y0 = positions[source]
        x1, y1 = positions[target]

        edge_x.extend((x0, x1, None))
        edge_y.extend((y0, y1, None))

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line={"color": "#9AA0A6", "width": 1.2},
        hoverinfo="skip",
        showlegend=False,
    )

    node_trace = go.Scatter(
        x=[positions[node][0] for node in graph.nodes()],
        y=[positions[node][1] for node in graph.nodes()],
        mode="markers+text",
        text=[str(node) for node in graph.nodes()],
        textposition="top center",
        marker={
            "size": 12,
            "color": [_node_color(graph, node) for node in graph.nodes()],
            "line": {"width": 1, "color": "white"},
        },
        customdata=[
            [
                str(node),
                str(graph.nodes[node].get("role", "unspecified")),
                graph.degree(node),
            ]
            for node in graph.nodes()
        ],
        hovertemplate=(
            "Node: %{customdata[0]}<br>"
            "Role: %{customdata[1]}<br>"
            "Degree: %{customdata[2]}"
            "<extra></extra>"
        ),
        showlegend=False,
    )

    if row is None or col is None:
        fig.add_trace(edge_trace)
        fig.add_trace(node_trace)
    else:
        fig.add_trace(edge_trace, row=row, col=col)
        fig.add_trace(node_trace, row=row, col=col)

    # Directed edges get arrowheads. The line traces above handle the edges;
    # annotations provide arrowheads in the graph's own coordinate system.
    if graph.is_directed():
        annotations = []
        for source, target in graph.edges():
            x0, y0 = positions[source]
            x1, y1 = positions[target]

            # Keep the arrowhead slightly away from the center of the target.
            fraction = 0.82
            annotations.append(
                {
                    "x": x0 + fraction * (x1 - x0),
                    "y": y0 + fraction * (y1 - y0),
                    "ax": x0 + 0.65 * (x1 - x0),
                    "ay": y0 + 0.65 * (y1 - y0),
                    "xref": "x",
                    "yref": "y",
                    "axref": "x",
                    "ayref": "y",
                    "showarrow": True,
                    "arrowhead": 2,
                    "arrowsize": 1,
                    "arrowwidth": 1.2,
                    "arrowcolor": "#9AA0A6",
                    "text": "",
                }
            )

        # In the combined view the graph occupies the first subplot.
        if row is not None and col is not None:
            for annotation in annotations:
                annotation["xref"] = "x"
                annotation["yref"] = "y"
                annotation["axref"] = "x"
                annotation["ayref"] = "y"

        fig.update_layout(annotations=annotations)


def plot_graph(
    graph: nx.Graph,
    title: str = "Graph",
    *,
    seed: int = 42,
    show: bool = True,
) -> go.Figure:
    """Plot a directed or undirected graph."""
    fig = go.Figure()
    _add_graph_traces(fig, graph, seed=seed)

    fig.update_layout(
        title=title,
        template="plotly_white",
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        xaxis={"visible": False, "showgrid": False, "zeroline": False},
        yaxis={
            "visible": False,
            "showgrid": False,
            "zeroline": False,
            "scaleanchor": "x",
            "scaleratio": 1,
        },
    )

    if show:
        fig.show()

    return fig


def _histogram_labels(histogram: Mapping[Any, float]) -> list[str]:
    def sort_key(value: Any) -> tuple[int, float | str]:
        if isinstance(value, (int, float)):
            if math.isinf(value):
                return (1, str(value))
            return (0, float(value))
        return (0, str(value))

    def label(value: Any) -> str:
        if isinstance(value, (int, float)) and math.isinf(value):
            return "∞" if value > 0 else "−∞"
        return str(value)

    return [label(value) for value in sorted(histogram, key=sort_key)]


def _add_histogram(
    fig: go.Figure,
    histogram: Mapping[Any, float],
    name: str,
    *,
    row: int,
    col: int,
) -> None:
    labels = _histogram_labels(histogram)
    probabilities = [
        float(histogram[value])
        for value in sorted(
            histogram,
            key=lambda value: (
                1 if isinstance(value, (int, float)) and math.isinf(value) else 0,
                str(value)
                if isinstance(value, (int, float)) and math.isinf(value)
                else float(value)
                if isinstance(value, (int, float))
                else str(value),
            ),
        )
    ]

    if not labels:
        fig.add_annotation(
            text="No observations",
            x=0.5,
            y=0.5,
            xref=f"x{(row - 1) * 3 + col + 1 if row > 1 or col > 1 else ''} domain",
            yref=f"y{(row - 1) * 3 + col + 1 if row > 1 or col > 1 else ''} domain",
            showarrow=False,
            font={"size": 11, "color": "#777"},
        )
        return

    fig.add_trace(
        go.Bar(
            x=labels,
            y=probabilities,
            name=name,
            marker_color="#4C78A8",
            showlegend=False,
            hovertemplate="%{x}<br>Probability: %{y:.3f}<extra></extra>",
        ),
        row=row,
        col=col,
    )


def plot_fingerprint(
    fingerprint: Mapping[str, Mapping[Any, float]],
    title: str = "Graph fingerprint",
    *,
    show: bool = True,
) -> go.Figure:
    """Plot every fingerprint histogram in a grid."""
    names = list(fingerprint)
    if not names:
        fig = go.Figure()
        fig.update_layout(title=title, template="plotly_white")
        if show:
            fig.show()
        return fig

    columns = 3
    rows = math.ceil(len(names) / columns)

    fig = make_subplots(
        rows=rows,
        cols=columns,
        subplot_titles=names,
        vertical_spacing=min(0.12, 0.8 / max(rows, 1)),
    )

    for index, name in enumerate(names):
        _add_histogram(
            fig,
            fingerprint[name],
            name,
            row=index // columns + 1,
            col=index % columns + 1,
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        showlegend=False,
        height=max(500, rows * 230),
    )

    if show:
        fig.show()

    return fig


def plot_graph_fingerprint(
    graph: nx.Graph,
    fingerprint: Mapping[str, Mapping[Any, float]] | None = None,
    title: str = "Graph and fingerprint",
    *,
    seed: int = 42,
    show: bool = True,
) -> go.Figure:
    """Show the graph on the left and its fingerprint on the right.

    The dropdown switches between all histograms and one enlarged histogram.
    """
    if fingerprint is None and require_digraph(graph):
        fingerprint = graph_fingerprint(graph)
    assert fingerprint is not None
    names = list(fingerprint)
    if not names:
        raise ValueError("The graph fingerprint contains no histograms.")

    fig = make_subplots(
        rows=4,
        cols=4,
        specs=[
            [{"rowspan": 4}, {}, {}, {}],
            [None, {}, {}, {}],
            [None, {}, {}, {}],
            [None, {}, {}, {}],
        ],
        horizontal_spacing=0.055,
        vertical_spacing=0.10,
    )

    _add_graph_traces(fig, graph, row=1, col=1, seed=seed)

    for index, name in enumerate(names):
        row = index // 3 + 1
        col = index % 3 + 2
        _add_histogram(
            fig,
            fingerprint[name],
            name,
            row=row,
            col=col,
        )

    # The first two traces are the graph's edges and nodes.
    graph_trace_count = 2
    histogram_count = len(names)

    # Record the original subplot domains so the "All" button can restore them.
    all_domains: dict[str, Any] = {}

    for index in range(histogram_count):
        axis_number = index + 2
        x_key = f"xaxis{axis_number}"
        y_key = f"yaxis{axis_number}"

        x_axis = getattr(fig.layout, x_key)
        y_axis = getattr(fig.layout, y_key)

        all_domains[f"{x_key}.domain"] = list(x_axis.domain or [])
        all_domains[f"{y_key}.domain"] = list(y_axis.domain or [])
        all_domains[f"{x_key}.visible"] = True
        all_domains[f"{y_key}.visible"] = True

    buttons = [
        {
            "label": "All fingerprints",
            "method": "update",
            "args": [
                {"visible": [True] * (graph_trace_count + histogram_count)},
                all_domains,
            ],
        }
    ]

    for selected_index, name in enumerate(names):
        axis_number = selected_index + 2
        layout_update: dict[str, Any] = {}

        for index in range(histogram_count):
            number = index + 2
            selected = index == selected_index
            layout_update[f"xaxis{number}.visible"] = selected
            layout_update[f"yaxis{number}.visible"] = selected

            if selected:
                layout_update[f"xaxis{number}.domain"] = [0.49, 0.99]
                layout_update[f"yaxis{number}.domain"] = [0.08, 0.94]

        visible = [True] * graph_trace_count + [
            index == selected_index for index in range(histogram_count)
        ]

        buttons.append(
            {
                "label": name,
                "method": "update",
                "args": [{"visible": visible}, layout_update],
            }
        )

    fig.update_layout(
        title=title,
        template="plotly_white",
        showlegend=False,
        height=900,
        margin={"l": 15, "r": 20, "t": 100, "b": 25},
        updatemenus=[
            {
                "type": "dropdown",
                "direction": "down",
                "x": 0.99,
                "xanchor": "right",
                "y": 1.10,
                "yanchor": "top",
                "buttons": buttons,
                "showactive": True,
            }
        ],
    )

    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)

    # Keep the graph's axes hidden while preserving its aspect ratio.
    fig.update_xaxes(visible=False, row=1, col=1)
    fig.update_yaxes(
        visible=False,
        scaleanchor="x",
        scaleratio=1,
        row=1,
        col=1,
    )

    # Add metric labels to each histogram's vertical axis.
    for index, name in enumerate(names):
        fig.update_yaxes(
            title_text=name,
            title_font={"size": 10},
            tickfont={"size": 9},
            row=index // 3 + 1,
            col=index % 3 + 2,
        )
        fig.update_xaxes(tickfont={"size": 9}, row=index // 3 + 1, col=index % 3 + 2)

    # Display the graph title independently of the metric selector.
    fig.add_annotation(
        text=f"<b>{graph.number_of_nodes()}</b> nodes · "
        f"<b>{graph.number_of_edges()}</b> edges",
        x=0.21,
        y=1.01,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"size": 12},
    )

    if show:
        fig.show()

    return fig
