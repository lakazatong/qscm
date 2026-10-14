/*
 * Browser-side behaviour for the QSCM graph browser.
 *
 * Dash serves everything in assets/ automatically. The functions registered
 * on window.dash_clientside.qscm at the bottom are wired to Dash callbacks in
 * callbacks/client.py.
 *
 * Design rule: the canvas is filled and laid out in ONE synchronous step
 * (showGraph -> replaceGraph). Nothing waits for "the elements to arrive",
 * so there is nothing to time out. The only wait left is at page start-up,
 * when the Cytoscape instance may not exist yet.
 */
(function () {
    "use strict";

    const GRAPH_ID = "graph-canvas";
    const WORKSPACE_ID = "visualization-workspace";
    const HANDLE_ID = "fingerprint-resize-handle";
    const SIDEBAR_MIN_WIDTH = 280;

    // ---------------------------------------------------------------- Cytoscape

    function getCy() {
        if (window.cy) return window.cy;
        const element = document.getElementById(GRAPH_ID);
        return (element && element._cyreg && element._cyreg.cy) || null;
    }

    // Calls `callback(cy)` as soon as the instance exists (start-up only).
    function whenCyReady(callback, attemptsLeft = 200) {
        const cy = getCy();
        if (cy) {
            callback(cy);
        } else if (attemptsLeft > 0) {
            setTimeout(() => whenCyReady(callback, attemptsLeft - 1), 50);
        } else {
            console.error("qscm: the Cytoscape instance never became available");
        }
    }

    // ------------------------------------------------------------------- Layout

    const EDGE_LENGTH = 50;

    const layoutState = {
        layout: null, // the cola layout of the current graph
        enabled: true,
        running: false,
        canvasHidden: false,
    };

    function setToggleLabel(running) {
        window.dash_clientside.set_props("layout-toggle", {
            children: running ? "Pause layout" : "Play layout",
        });
    }

    function stopLayout() {
        if (layoutState.layout) layoutState.layout.stop();
        layoutState.running = false;
    }

    function startLayout() {
        if (
            !layoutState.enabled ||
            layoutState.canvasHidden ||
            !layoutState.layout ||
            layoutState.running
        ) {
            return;
        }

        layoutState.layout.run();
        layoutState.running = true;
    }

    function setEnabled(enabled) {
        layoutState.enabled = enabled;

        if (enabled) {
            startLayout();
        } else {
            stopLayout();
        }

        setToggleLabel(enabled);
    }

    function colaOptions() {
        return {
            name: "cola",
            infinite: true,
            animate: true,
            refresh: 16,
            fit: false,
            avoidOverlap: true,
            handleDisconnected: false,
            ungrabifyWhileSimulating: false,

            nodeSpacing: (node) => {
                switch (node.data("role")) {
                    case "feature":
                    case "target":
                        return 3;
                    default:
                        return 10;
                }
            },

            edgeLength: EDGE_LENGTH,
        };
    }

    function findComponents(cy) {
        const remaining = new Set(cy.nodes().map((n) => n.id()));
        const components = [];

        while (remaining.size > 0) {
            const first = remaining.values().next().value;
            const stack = [cy.getElementById(first)];
            const nodes = [];

            remaining.delete(first);

            while (stack.length > 0) {
                const node = stack.pop();
                nodes.push(node);

                node.connectedEdges().forEach((edge) => {
                    const other = edge.source().id() === node.id() ? edge.target() : edge.source();

                    if (remaining.delete(other.id())) {
                        stack.push(other);
                    }
                });
            }

            components.push({
                nodes: cy.collection(nodes),
                isolated: nodes.length === 1 && nodes[0].connectedEdges().length === 0,
            });
        }

        return components;
    }

    // initial position helpers

    // function getWeightedCentroid(nodes, getWeight = (node) => node.indegree() + node.outdegree()) {
    //     let totalWeight = 0;
    //     let x = 0;
    //     let y = 0;

    //     for (const node of nodes) {
    //         const weight = getWeight(node);
    //         const position = node.position();

    //         totalWeight += weight;
    //         x += position.x * weight;
    //         y += position.y * weight;
    //     }

    //     if (totalWeight === 0) {
    //         return {
    //             x: nodes.reduce((sum, node) => sum + node.position("x"), 0) / nodes.length,
    //             y: nodes.reduce((sum, node) => sum + node.position("y"), 0) / nodes.length,
    //         };
    //     }

    //     return {
    //         x: x / totalWeight,
    //         y: y / totalWeight,
    //     };
    // }

    const LAYER_ASPECT_RATIO = 16 / 9;
    const FINAL_JITTER = 8;

    function getComponentMargin(nodeCount) {
        return Math.sqrt(nodeCount) * 128;
    }

    function getBounds(nodes) {
        const positions = nodes.map((node) => node.position());

        const xs = positions.map((p) => p.x);
        const ys = positions.map((p) => p.y);

        return {
            left: Math.min(...xs),
            top: Math.min(...ys),
            width: Math.max(...xs) - Math.min(...xs),
            height: Math.max(...ys) - Math.min(...ys),
        };
    }

    function getComponents(cy) {
        const components = findComponents(cy);
        const connected = components
            .filter((component) => !component.isolated)
            .sort((a, b) => b.nodes.length - a.nodes.length);

        const isolatedNodes = components
            .filter((component) => component.isolated)
            .flatMap((component) => component.nodes.toArray());

        if (isolatedNodes.length > 0) {
            connected.push({
                nodes: cy.collection(isolatedNodes),
                isolated: true,
            });
        }

        return connected;
    }

    function randomizeList(items) {
        const result = [...items];

        for (let i = result.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [result[i], result[j]] = [result[j], result[i]];
        }

        return result;
    }

    function translateNodes(nodes, dx, dy) {
        for (const node of nodes) {
            node.position({
                x: node.position("x") + dx,
                y: node.position("y") + dy,
            });
        }
    }

    function groupIntoRows(items, aspectRatio) {
        if (items.length === 0) return [];

        let columns = 1;
        let bestError = Infinity;

        for (let candidate = 1; candidate <= items.length; candidate++) {
            const rows = Math.ceil(items.length / candidate);
            const error = Math.abs(candidate / rows - aspectRatio);

            if (error < bestError) {
                columns = candidate;
                bestError = error;
            }
        }

        const rows = [];

        for (let i = 0; i < items.length; i += columns) {
            rows.push(items.slice(i, i + columns));
        }

        return rows;
    }

    function arrangeComponentLayers(component, nodeGap) {
        const nodes = component.nodes.toArray();

        const layers = [
            randomizeList(nodes.filter((node) => node.indegree() === 0)),
            randomizeList(nodes.filter((node) => node.indegree() > 0 && node.outdegree() > 0)),
            randomizeList(nodes.filter((node) => node.indegree() > 0 && node.outdegree() === 0)),
        ].filter((layer) => layer.length > 0);

        let y = 0;

        for (const layer of layers) {
            const rows = groupIntoRows(layer, LAYER_ASPECT_RATIO);

            rows.forEach((row, rowIndex) => {
                row.forEach((node, columnIndex) => {
                    node.position({
                        x: columnIndex * nodeGap,
                        y: y + rowIndex * nodeGap,
                    });
                });
            });

            y += rows.length * nodeGap;
        }
    }

    function displaceNodes(nodes, xDelta, yDelta) {
        for (const node of nodes) {
            node.position({
                x: node.position("x") + (Math.random() - 0.5) * xDelta,
                y: node.position("y") + (Math.random() - 0.5) * yDelta,
            });
        }
    }

    function groupComponentsIntoRows(components) {
        if (components.length === 0) return [];

        const sorted = [...components].sort((a, b) => b.nodes.length - a.nodes.length);

        const targetRowSize = Math.ceil(Math.sqrt(sorted.length));
        const rows = [];
        let offset = 0;

        while (offset < sorted.length) {
            let end = Math.min(offset + targetRowSize, sorted.length);

            // Keep components of equal size together.
            while (
                end < sorted.length &&
                sorted[end - 1].nodes.length === sorted[end].nodes.length
            ) {
                end++;
            }

            rows.push(sorted.slice(offset, end));
            offset = end;
        }

        return rows;
    }

    function initializePositions(components) {
        const connected = components.filter((component) => !component.isolated);
        const isolatedNodes = components
            .filter((component) => component.isolated)
            .flatMap((component) => component.nodes.toArray());

        for (const component of connected) {
            arrangeComponentLayers(component, EDGE_LENGTH);
        }

        const rows = groupComponentsIntoRows(connected);
        let yOffset = 0;

        for (const row of rows) {
            let xOffset = 0;
            let rowHeight = 0;
            let maxMargin = 0;

            for (const component of row) {
                const nodes = component.nodes.toArray();
                const bounds = getBounds(nodes);
                const margin = getComponentMargin(nodes.length);

                translateNodes(nodes, xOffset - bounds.left, yOffset - bounds.top);

                xOffset += bounds.width + margin;
                rowHeight = Math.max(rowHeight, bounds.height);
                maxMargin = Math.max(maxMargin, margin);
            }

            yOffset += rowHeight + maxMargin;
        }

        const connectedNodes = connected.flatMap((component) => component.nodes.toArray());

        if (isolatedNodes.length > 0 && connectedNodes.length > 0) {
            const bounds = getBounds(connectedNodes);
            const margin = getComponentMargin(isolatedNodes.length);

            translateNodes(
                isolatedNodes,
                bounds.left + bounds.width + margin,
                bounds.top + bounds.height + margin,
            );
        } else if (isolatedNodes.length > 0) {
            arrangeComponentLayers(
                { nodes: components.find((component) => component.isolated).nodes },
                EDGE_LENGTH,
            );
            translateNodes(
                isolatedNodes,
                getComponentMargin(isolatedNodes.length),
                getComponentMargin(isolatedNodes.length),
            );
        }

        displaceNodes(connectedNodes, FINAL_JITTER, FINAL_JITTER);
    }

    // The graph pane is hidden while the fingerprint sidebar is expanded.
    // Pause the simulation while it is hidden and resume it afterwards, and
    // keep Cytoscape's size in sync with its container (this also covers the
    // sidebar drag handle and window resizes).
    function observeCanvasSize(cy) {
        const element = document.getElementById(GRAPH_ID);
        if (!element || element.dataset.qscmObserved === "true") return;
        element.dataset.qscmObserved = "true";

        new ResizeObserver(() => {
            const hidden = element.clientWidth === 0 && element.clientHeight === 0;
            layoutState.canvasHidden = hidden;

            if (hidden) {
                stopLayout();
                return;
            }

            cy.resize();
            startLayout();
        }).observe(element);
    }

    function replaceGraph(cy, payload) {
        stopLayout();
        layoutState.layout = null;

        cy.batch(() => {
            cy.elements().remove();
            cy.add(payload.elements);
        });

        if (cy.nodes().length !== payload.node_count || cy.edges().length !== payload.edge_count) {
            console.error("qscm: canvas does not match the graph", {
                key: payload.key,
                expectedNodes: payload.node_count,
                actualNodes: cy.nodes().length,
                expectedEdges: payload.edge_count,
                actualEdges: cy.edges().length,
            });
        }

        observeCanvasSize(cy);

        if (cy.nodes().length === 0) {
            setToggleLabel(layoutState.enabled);
            return;
        }

        const components = getComponents(cy);
        initializePositions(components);
        layoutState.layout = cy.layout(colaOptions());
        startLayout();
        setToggleLabel(layoutState.enabled);
    }

    let latestRequest = 0;

    function showGraph(payload) {
        if (!payload || !Array.isArray(payload.elements)) return;

        // If several graphs are requested before the instance exists
        // (start-up), only the latest one is shown.
        const request = ++latestRequest;
        whenCyReady((cy) => {
            if (request === latestRequest) replaceGraph(cy, payload);
        });
    }

    function fitGraph() {
        const cy = getCy();
        if (cy) {
            const connectedNodes = cy.nodes().filter((node) => node.degree() > 0);
            const connectedElements = connectedNodes.union(connectedNodes.connectedEdges());
            cy.fit(connectedElements, 30);
        }
    }

    // ------------------------------------------------- Fingerprint sidebar drag
    //
    // Open/closed/expanded are CSS classes on the workspace (see `panel`
    // below); the only thing left for JS is the drag handle. Listening on the
    // document means we never have to wait for the handle to exist.

    let dragging = false;

    document.addEventListener("pointerdown", (event) => {
        const handle = event.target.closest && event.target.closest("#" + HANDLE_ID);
        if (!handle) return;

        dragging = true;
        handle.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    document.addEventListener("pointermove", (event) => {
        if (!dragging) return;

        const workspace = document.getElementById(WORKSPACE_ID);
        if (!workspace) return;

        const bounds = workspace.getBoundingClientRect();
        const width = Math.max(
            SIDEBAR_MIN_WIDTH,
            Math.min(bounds.width - SIDEBAR_MIN_WIDTH, bounds.right - event.clientX),
        );
        workspace.style.setProperty("--sidebar-width", width + "px");
    });

    const stopDragging = () => {
        dragging = false;
    };
    document.addEventListener("pointerup", stopDragging);
    document.addEventListener("pointercancel", stopDragging);

    // ----------------------------------------- Functions called from Dash (py)

    window.dash_clientside = window.dash_clientside || {};

    window.dash_clientside.qscm = {
        // Inputs: graph-data, layout-toggle, fit-graph
        layout: function (graphData, _toggleClicks, _fitClicks) {
            const triggered = window.dash_clientside.callback_context.triggered_id;

            if (triggered === "layout-toggle") {
                setEnabled(!layoutState.enabled);
            } else if (triggered === "fit-graph") {
                fitGraph();
            } else {
                showGraph(graphData); // "graph-data", or the initial call
            }

            return window.dash_clientside.no_update;
        },

        // Inputs: toggle-metadata.n_clicks
        toggle_metadata: function (clicks) {
            const visible = (clicks || 0) % 2 === 0;
            return [
                visible ? "metadata-panel" : "metadata-panel is-hidden",
                visible ? "Hide metadata" : "Show metadata",
            ];
        },

        // Inputs: toggle/close/expand clicks; State: panel-state
        panel: function (_toggle, _close, _expand, state) {
            const triggered = window.dash_clientside.callback_context.triggered_id;
            const wasOpen = !!(state && state.open);
            let open = wasOpen;
            let expanded = !!(state && state.expanded);

            if (triggered === "toggle-fingerprints") {
                open = !open;
                expanded = false;
            } else if (triggered === "close-fingerprints") {
                open = false;
                expanded = false;
            } else if (triggered === "expand-fingerprints") {
                expanded = !expanded;
                open = true;
            }

            const className = ["workspace", open && "fp-open", expanded && "fp-expanded"]
                .filter(Boolean)
                .join(" ");

            return [
                className,
                open ? "Hide fingerprints" : "Fingerprints",
                expanded ? "Restore graph" : "Expand",
                { open: open, expanded: expanded },
                // Only tell the server when open/closed actually changed, so
                // expanding/restoring does not recompute the fingerprints.
                open === wasOpen ? window.dash_clientside.no_update : open,
            ];
        },
    };
})();
