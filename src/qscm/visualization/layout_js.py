LAYOUT_CALLBACK = r"""
function(command, nClicks, fitClicks, initCount) {
    const noUpdate = window.dash_clientside.no_update;
    const triggered = window.dash_clientside.callback_context.triggered_id;

    let controller = window.qscmLayoutController;

    if (!controller) {
        controller = {
            layout: null,
            timer: null,
            manual: false,
            running: false,
            graphKey: null,
        };
        window.qscmLayoutController = controller;
    }

    function setButtonLabel(label) {
        window.dash_clientside.set_props("layout-toggle", {
            children: label,
        });
    }

    function stopLayout() {
        if (controller.layout) {
            controller.layout.stop();
        }
        controller.running = false;
    }

    function startLayout() {
        if (controller.layout) {
            controller.layout.run();
            controller.running = true;
        }
    }

    function cancelTimer() {
        if (controller.timer !== null) {
            clearTimeout(controller.timer);
            controller.timer = null;
        }
    }

    function cola_layout() {
        return {
            name: "cola",
            infinite: true,
            animate: true,
            fit: false,
            refresh: 10,
            ungrabifyWhileSimulating: false,
            avoidOverlap: true,
            handleDisconnected: true,

            nodeSpacing: node => {
                switch (node.data("role")) {
                    case "feature": return 3;
                    case "target": return 3;
                    default: return 10;
                }
            },

            edgeLength: 50,
        };
    }

    if (triggered === "layout-command" || triggered === "layout-init") {
        if (!command || command.action !== "restart") {
            return noUpdate;
        }

        cancelTimer();
        stopLayout();

        controller.manual = false;
        controller.graphKey = command.graph_key;

        const cy = window.cy;
        if (!cy) {
            return noUpdate;
        }

        controller.layout = cy.layout(cola_layout());
        setButtonLabel("Pause layout");

        function waitForGraph(attempt = 0) {
            if (controller.graphKey !== command.graph_key) {
                return;
            }

            const cy = window.cy;

            console.log(
                "Edge before layout:",
                cy.getElementById("edge-43").length,
                "total edges:",
                cy.edges().length
            );

            if (!cy || cy.nodes().length !== command.node_count) {
                if (attempt < 100) {
                    controller.timer = setTimeout(() => {
                        controller.timer = null;
                        waitForGraph(attempt + 1);
                    }, 50);
                }
                return;
            }

            controller.layout = cy.layout(cola_layout());
            startLayout();
            
            console.log(
                "Edge after layout:", cy.getElementById("edge-43").length,
                "total edges:", cy.edges().length
            );
        }

        waitForGraph();
        return noUpdate;
    }

    if (triggered === "layout-toggle") {
        cancelTimer();
        controller.manual = true;

        if (controller.running) {
            stopLayout();
            setButtonLabel("Play layout");
        } else {
            startLayout();
            setButtonLabel("Pause layout");
        }
    }

    if (triggered === "fit-graph") {
        const cy = window.cy;
        if (cy) {
            cy.fit(undefined, 30);
        }
        return noUpdate;
    }

    return noUpdate;
}
"""
