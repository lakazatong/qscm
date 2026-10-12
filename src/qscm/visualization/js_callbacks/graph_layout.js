function graph_layout(command, nClicks, fitClicks, initCount) {
    const noUpdate = window.dash_clientside.no_update;
    const triggered = window.dash_clientside.callback_context.triggered_id;

    let controller = window.qscmLayoutController;

    if (!controller) {
        controller = {
            layout: null,
            timer: null,
            running: false,
            graphKey: null,
            generation: 0,
        };
        window.qscmLayoutController = controller;
    }

    function setButtonLabel(label) {
        window.dash_clientside.set_props("layout-toggle", {
            children: label,
        });
    }

    function cancelTimer() {
        if (controller.timer !== null) {
            clearTimeout(controller.timer);
            controller.timer = null;
        }
    }

    function stopLayout() {
        if (controller.layout) {
            controller.layout.stop();
        }
        controller.running = false;
    }

    function cancelCurrentRun() {
        controller.generation += 1;
        cancelTimer();
        stopLayout();
        controller.layout = null;
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

    // Initialize each component using a compact grid-like arrangement.
    // This is O(V + E), with no preliminary force simulations.
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
            const nodes = component.nodes;
            const count = nodes.length;

            // Approximate footprint based on node count.
            const columns = Math.ceil(Math.sqrt(count));
            const rows = Math.ceil(count / columns);
            const width = columns * nodeGap;
            const height = rows * nodeGap;

            if (x > margin && x + width > margin + targetWidth) {
                x = margin;
                y += rowHeight + gap;
                rowHeight = 0;
            }

            // Put nodes into the component's own initial footprint.
            nodes.positions((node, index) => ({
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

    function startLayout(cy, generation) {
        if (generation !== controller.generation) return;

        initializePositions(cy);

        controller.layout = cy.layout(colaOptions());
        controller.layout.run();
        controller.running = true;
        setButtonLabel("Pause layout");
    }

    if (triggered === "layout-command" || triggered === "layout-init") {
        if (!command || command.action !== "restart") {
            return noUpdate;
        }

        cancelCurrentRun();
        controller.graphKey = command.graph_key;

        const generation = controller.generation;
        const graphKey = command.graph_key;

        function waitForGraph(attempt = 0) {
            if (generation !== controller.generation || controller.graphKey !== graphKey) {
                return;
            }

            const cy = window.cy;

            if (!cy || cy.nodes().length !== command.node_count) {
                if (attempt < 100) {
                    controller.timer = setTimeout(() => {
                        controller.timer = null;
                        waitForGraph(attempt + 1);
                    }, 50);
                }
                return;
            }

            startLayout(cy, generation);
        }

        waitForGraph();
        return noUpdate;
    }

    if (triggered === "layout-toggle") {
        cancelTimer();

        if (controller.running) {
            stopLayout();
            setButtonLabel("Play layout");
        } else if (controller.layout) {
            controller.layout.run();
            controller.running = true;
            setButtonLabel("Pause layout");
        }

        return noUpdate;
    }

    if (triggered === "fit-graph") {
        const cy = window.cy;
        if (cy) cy.fit(cy.elements(), 30);
        return noUpdate;
    }

    return noUpdate;
}
