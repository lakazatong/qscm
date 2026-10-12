const MIN_WIDTH = 280;
const DEFAULT_WIDTH = 380;

let width = DEFAULT_WIDTH;
let open = false;
let expanded = false;
let wasRunning = false;
let dragging = false;

function init(workspace, graph, sidebar, handle) {
    function resizeGraph() {
        requestAnimationFrame(() => {
            if (window.cy) window.cy.resize();
        });
    }

    function setLayoutRunning(running) {
        const controller = window.qscmLayoutController;
        if (!controller) return;

        if (running) {
            if (controller.layout) {
                controller.layout.run();
                controller.running = true;
            } else if (window.cy) {
                window.dash_clientside.set_props("layout-command", {
                    data: {
                        action: "restart",
                        graph_key: controller.graphKey,
                        node_count: window.cy.nodes().length,
                        reload_token: Date.now(),
                    },
                });
            }
            window.dash_clientside.set_props("layout-toggle", {
                children: "Pause layout",
            });
        } else {
            if (controller.layout) controller.layout.stop();
            controller.running = false;
            window.dash_clientside.set_props("layout-toggle", {
                children: "Play layout",
            });
        }
    }

    function render() {
        sidebar.style.display = open ? "flex" : "none";
        handle.style.display = open && !expanded ? "block" : "none";

        graph.style.display = expanded ? "none" : "block";
        graph.style.flex = "1 1 auto";
        graph.style.minWidth = "0";

        if (open && !expanded) {
            sidebar.style.flex = `0 0 ${width}px`;
            sidebar.style.width = `${width}px`;
        } else if (expanded) {
            sidebar.style.flex = "1 1 auto";
            sidebar.style.width = "100%";
        }

        workspace.classList.toggle("fingerprints-fullscreen", expanded);

        const toggle = document.getElementById("toggle-fingerprints");
        if (toggle) toggle.textContent = open ? "Hide fingerprints" : "Fingerprints";

        const expand = document.getElementById("expand-fingerprints");
        if (expand) expand.textContent = expanded ? "Restore graph" : "Expand";

        resizeGraph();
    }

    document.getElementById("toggle-fingerprints")?.addEventListener("click", () => {
        open = !open;
        expanded = false;
        render();
    });

    document.getElementById("close-fingerprints")?.addEventListener("click", () => {
        open = false;
        expanded = false;
        render();
    });

    document.getElementById("expand-fingerprints")?.addEventListener("click", () => {
        expanded = !expanded;
        open = true;

        if (expanded) {
            const controller = window.qscmLayoutController;
            wasRunning = !!controller?.running;
            setLayoutRunning(false);
        } else if (wasRunning) {
            setLayoutRunning(true);
        }

        render();
    });

    handle.addEventListener("pointerdown", (event) => {
        if (!open || expanded) return;

        dragging = true;
        handle.setPointerCapture(event.pointerId);
        event.preventDefault();
    });

    handle.addEventListener("pointermove", (event) => {
        if (!dragging) return;

        width = Math.max(
            MIN_WIDTH,
            Math.min(window.innerWidth - MIN_WIDTH, window.innerWidth - event.clientX),
        );
        render();
    });

    handle.addEventListener("pointerup", () => {
        dragging = false;
    });

    handle.addEventListener("pointercancel", () => {
        dragging = false;
    });

    window.addEventListener("resize", () => {
        if (open && !expanded) {
            width = Math.min(width, Math.max(MIN_WIDTH, window.innerWidth - MIN_WIDTH));
            render();
        }
    });

    render();
}

function waitForDOM() {
    function tryInit() {
        const workspace = document.getElementById("visualization-workspace");
        const graph = document.getElementById("graph-canvas");
        const sidebar = document.getElementById("fingerprint-sidebar");
        const handle = document.getElementById("fingerprint-resize-handle");

        if (!workspace || !graph || !sidebar || !handle) return false;
        if (workspace.dataset.fingerprintSidebarInitialized === "true") return true;

        workspace.dataset.fingerprintSidebarInitialized = "true";
        init(workspace, graph, sidebar, handle);
        return true;
    }

    if (tryInit()) return;

    const observer = new MutationObserver(() => {
        if (tryInit()) observer.disconnect();
    });

    observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
    });
}

waitForDOM();
