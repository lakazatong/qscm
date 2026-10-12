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

    const layoutState = {
        layout: null, // the cola layout of the current graph
        running: false,
        pausedWhileHidden: false,
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

    function setRunning(running) {
        if (running) {
            if (!layoutState.layout) return;
            layoutState.layout.run();
            layoutState.running = true;
        } else {
            stopLayout();
        }
        setToggleLabel(running);
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

            edgeLength: 50,
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

    // Start each component in a compact grid so the force simulation begins
    // from a tidy state. O(V + E), no preliminary simulations.
    function initializePositions(cy) {
        const components = findComponents(cy);
        const connected = components
            .filter((c) => !c.isolated)
            .sort((a, b) => b.nodes.length - a.nodes.length);
        const isolated = components.filter((c) => c.isolated);

        const gap = 40;
        const nodeGap = 34;
        const margin = 30;

        let x = margin;
        let y = margin;
        let rowHeight = 0;
        let right = margin;
        let bottom = margin;

        const totalNodes = connected.reduce((sum, c) => sum + c.nodes.length, 0);
        const targetWidth = Math.max(500, Math.sqrt(totalNodes) * nodeGap * 1.8);

        for (const component of connected) {
            const count = component.nodes.length;
            const columns = Math.ceil(Math.sqrt(count));
            const rows = Math.ceil(count / columns);
            const width = columns * nodeGap;
            const height = rows * nodeGap;

            if (x > margin && x + width > margin + targetWidth) {
                x = margin;
                y += rowHeight + gap;
                rowHeight = 0;
            }

            component.nodes.positions((node, index) => ({
                x: x + (index % columns) * nodeGap,
                y: y + Math.floor(index / columns) * nodeGap,
            }));

            right = Math.max(right, x + width);
            bottom = Math.max(bottom, y + height);

            x += width + gap;
            rowHeight = Math.max(rowHeight, height);
        }

        // Isolated nodes start in a grid below and to the right.
        const isolatedColumns = Math.max(1, Math.ceil(Math.sqrt(isolated.length)));
        const isolatedStartX = right + gap;
        const isolatedStartY = bottom + gap;

        isolated.forEach((component, index) => {
            component.nodes.position({
                x: isolatedStartX + (index % isolatedColumns) * nodeGap,
                y: isolatedStartY + Math.floor(index / isolatedColumns) * nodeGap,
            });
        });
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

            if (hidden) {
                if (layoutState.running) {
                    layoutState.pausedWhileHidden = true;
                    setRunning(false);
                }
                return;
            }

            cy.resize();

            if (layoutState.pausedWhileHidden) {
                layoutState.pausedWhileHidden = false;
                setRunning(true);
            }
        }).observe(element);
    }

    function replaceGraph(cy, payload) {
        stopLayout();
        layoutState.layout = null;
        layoutState.pausedWhileHidden = false;

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
            setToggleLabel(false);
            return;
        }

        initializePositions(cy);
        layoutState.layout = cy.layout(colaOptions());
        setRunning(true);
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
        if (cy) cy.fit(cy.elements(), 30);
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
                setRunning(!layoutState.running);
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
