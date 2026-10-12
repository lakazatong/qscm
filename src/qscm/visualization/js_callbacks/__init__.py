from pathlib import Path

CUR_FOLDER = Path(__file__).parent


def load_script(name: str) -> str:
    return (CUR_FOLDER / f"{name}.js").read_text(encoding="utf-8")


GRAPH_LAYOUT_CALLBACK = load_script("graph_layout")
