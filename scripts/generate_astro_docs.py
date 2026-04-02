#!/usr/bin/env python3
"""Generate Astro documentation pages for the designer-plugin package.

Parses Python docstrings with ast (no import required) and writes .md files
that match the format used by the d3_doc_dev Astro documentation site.

Run from the python-plugin repo root:
    python scripts/generate_astro_docs.py
    python scripts/generate_astro_docs.py --docs-repo /path/to/d3_doc_dev
"""

import argparse
import ast
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Union

# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_DOCS_REPO = Path("C:/dev/d3docs/d3_doc_dev")
OUTPUT_SUBDIR = Path("src/pages/plugins/designer-plugin")
LAYOUT = "../../../layouts/HeroLayout.astro"
URL_BASE = "plugins/designer-plugin"
AUTHOR = "Disguise"
DATE = datetime.now().strftime("%d-%b-%Y")
SRC = Path("src/designer_plugin")

FuncNode = Union[ast.FunctionDef, ast.AsyncFunctionDef]

# ── AST helpers ───────────────────────────────────────────────────────────────


def load_tree(rel_path: Path) -> ast.Module:
    return ast.parse((SRC / rel_path).read_text(encoding="utf-8"))


def find_class(tree: ast.Module, name: str) -> ast.ClassDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def find_function(tree: ast.Module, name: str) -> FuncNode | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def get_docstring(node: ast.AST) -> str:
    if (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return dedent(node.body[0].value.value).strip()
    return ""


def unparse_type(node: ast.expr | None) -> str:
    if node is None:
        return ""
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def func_signature(func: FuncNode, skip_self: bool = True) -> str:
    """Return formatted signature like (arg: *type* = default, ...)"""
    a = func.args
    params: list[str] = []
    offset = len(a.args) - len(a.defaults)
    for i, arg in enumerate(a.args):
        if skip_self and arg.arg in ("self", "cls"):
            continue
        s = arg.arg
        if arg.annotation:
            s += f": *{unparse_type(arg.annotation)}*"
        di = i - offset
        if 0 <= di < len(a.defaults):
            s += f" = {ast.unparse(a.defaults[di])}"
        params.append(s)
    if a.vararg:
        s = f"*{a.vararg.arg}"
        if a.vararg.annotation:
            s += f": *{unparse_type(a.vararg.annotation)}*"
        params.append(s)
    if a.kwarg:
        s = f"**{a.kwarg.arg}"
        if a.kwarg.annotation:
            s += f": *{unparse_type(a.kwarg.annotation)}*"
        params.append(s)
    return f"({', '.join(params)})"


# ── Google docstring parser ────────────────────────────────────────────────────

_SECT_RE = re.compile(
    r"^(Args|Returns|Raises|Attributes|Class Attributes|Examples?|Note|Usage|Yields):\s*$",
    re.I,
)


@dataclass
class DocSection:
    description: str = ""
    args: list[dict] = field(default_factory=list)      # {"name", "type", "desc"}
    returns: str = ""
    raises: list[dict] = field(default_factory=list)    # {"type", "desc"}
    attributes: list[dict] = field(default_factory=list)  # {"name", "type", "desc"}
    examples: str = ""

    @property
    def first_line(self) -> str:
        return self.description.split("\n")[0].strip()


def parse_docstring(raw: str) -> DocSection:
    d = DocSection()
    if not raw:
        return d
    lines = raw.split("\n")
    i, desc = 0, []
    while i < len(lines):
        if _SECT_RE.match(lines[i].strip()):
            break
        desc.append(lines[i])
        i += 1
    d.description = "\n".join(line.lstrip() for line in desc).rstrip()

    section, cur = None, None
    while i < len(lines):
        line, stripped = lines[i], lines[i].strip()
        m = _SECT_RE.match(stripped)
        if m:
            key = m.group(1).lower()
            if "attribute" in key:
                section = "attr"
            elif key.startswith("arg"):
                section = "args"
            elif key.startswith("raise"):
                section = "raises"
            elif key in ("returns", "yields"):
                section = "returns"
            elif key.startswith("example"):
                section = "examples"
            else:
                section = None
            cur = None
            i += 1
            continue
        if not stripped:
            i += 1
            continue
        if section in ("args", "attr"):
            m2 = re.match(r"^\s{4,}(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.*)", line)
            if m2:
                cur = {"name": m2.group(1), "type": m2.group(2) or "", "desc": m2.group(3).strip()}
                (d.args if section == "args" else d.attributes).append(cur)
            elif cur and re.match(r"^\s{8,}", line):
                cur["desc"] += " " + stripped
        elif section == "returns":
            d.returns = (d.returns + " " + stripped).strip()
        elif section == "raises":
            m2 = re.match(r"^\s{4,}(\w+)\s*:\s*(.*)", line)
            if m2:
                cur = {"type": m2.group(1), "desc": m2.group(2).strip()}
                d.raises.append(cur)
            elif cur and re.match(r"^\s{8,}", line):
                cur["desc"] += " " + stripped
        elif section == "examples":
            d.examples += line + "\n"
        i += 1
    d.examples = dedent(d.examples).rstrip()
    return d


# ── Markdown renderers ─────────────────────────────────────────────────────────


def render_doc_sections(doc: DocSection) -> list[str]:
    """Render Args / Returns / Raises / Examples sections."""
    out: list[str] = []
    if doc.args:
        out += ["", "**Parameters:**", ""]
        for a in doc.args:
            s = f"- `{a['name']}`"
            if a["type"]:
                s += f" (*{a['type']}*)"
            if a["desc"]:
                s += f" — {a['desc']}"
            out.append(s)
    if doc.returns:
        out += ["", f"**Returns:** {doc.returns}"]
    if doc.raises:
        out += ["", "**Raises:**", ""]
        for r in doc.raises:
            s = f"- `{r['type']}`"
            if r["desc"]:
                s += f" — {r['desc']}"
            out.append(s)
    if doc.examples:
        out += ["", "**Example:**", "", doc.examples]
    return out


def render_method(func: FuncNode, is_method: bool = True) -> list[str]:
    is_async = isinstance(func, ast.AsyncFunctionDef)
    sig = func_signature(func, skip_self=is_method)
    ret = f" → *{unparse_type(func.returns)}*" if func.returns else ""
    prefix = "*async* " if is_async else ""
    out = [f"#### {prefix}**{func.name}**{sig}{ret}", ""]
    doc = parse_docstring(get_docstring(func))
    if doc.description:
        out += [doc.description, ""]
    out += render_doc_sections(doc)
    return out


def _is_decorator(func: FuncNode, name: str) -> bool:
    return any(
        (isinstance(d, ast.Name) and d.id == name)
        for d in func.decorator_list
    )


def render_class_body(node: ast.ClassDef, h: int = 2) -> list[str]:
    """Render class internals (no class-name heading). h = heading level for sections."""
    hn = "#" * h + " "
    doc = parse_docstring(get_docstring(node))
    out: list[str] = []
    if doc.description:
        out += [doc.description, ""]
    if doc.attributes:
        out += [f"{hn}Attributes", ""]
        for a in doc.attributes:
            s = f"#### **{a['name']}**"
            if a["type"]:
                s += f" : *{a['type']}*"
            out.append(s)
            if a["desc"]:
                out += ["", a["desc"], ""]

    constructor, statics, props, publics, ctxmgr = [], [], [], [], []
    for child in node.body:
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if child.name == "__init__":
            constructor.append(child)
        elif child.name in ("__enter__", "__exit__", "__aenter__", "__aexit__"):
            ctxmgr.append(child)
        elif child.name.startswith("_"):
            continue
        elif _is_decorator(child, "staticmethod") or _is_decorator(child, "classmethod"):
            statics.append(child)
        elif _is_decorator(child, "property"):
            props.append(child)
        else:
            publics.append(child)

    if constructor:
        out += [f"{hn}Constructor", ""]
        for m in constructor:
            out += render_method(m)
            out.append("")
    if statics:
        out += [f"{hn}Static Methods", ""]
        for m in statics:
            out += render_method(m, is_method=False)
            out.append("")
    if props:
        out += [f"{hn}Properties", ""]
        for m in props:
            out += render_method(m)
            out.append("")
    if publics:
        out += [f"{hn}Methods", ""]
        for m in publics:
            out += render_method(m)
            out.append("")
    if ctxmgr:
        out += [f"{hn}Context Manager", ""]
        out.append("Supports use as a context manager (`with` / `async with`):")
        out.append("")
        for m in ctxmgr:
            out += render_method(m)
            out.append("")
    return out


# ── Frontmatter ───────────────────────────────────────────────────────────────


def frontmatter(title: str, description: str, url_slug: str) -> list[str]:
    safe_desc = description.replace('"', "'").split("\n")[0].strip()
    return [
        "---",
        f'title: "{title}"',
        f'description: "{safe_desc}"',
        f"layout: {LAYOUT}",
        f'author: "{AUTHOR}"',
        f'date: "{DATE}"',
        f'url: "{URL_BASE}/{url_slug}"',
        "---",
        "",
    ]


# ── Page builders ─────────────────────────────────────────────────────────────


def page_single_class(class_name: str, src_file: str, url_slug: str) -> str:
    tree = load_tree(Path(src_file))
    node = find_class(tree, class_name)
    assert node, f"Class {class_name!r} not found in {src_file}"
    doc = parse_docstring(get_docstring(node))
    lines = frontmatter(class_name, doc.first_line, url_slug)
    lines += [f"# {class_name}", ""]
    lines += render_class_body(node, h=2)
    return "\n".join(lines) + "\n"


def page_multi_class(
    title: str,
    description: str,
    url_slug: str,
    classes: list[tuple[str, str]],
) -> str:
    lines = frontmatter(title, description, url_slug)
    lines += [f"# {title}", "", description, ""]
    for class_name, src_file in classes:
        tree = load_tree(Path(src_file))
        node = find_class(tree, class_name)
        assert node, f"Class {class_name!r} not found in {src_file}"
        doc = parse_docstring(get_docstring(node))
        lines += [f"## {class_name}", ""]
        lines += render_class_body(node, h=3)
        lines += ["---", ""]
    return "\n".join(lines) + "\n"


def page_functions(
    title: str,
    description: str,
    url_slug: str,
    functions: list[tuple[str, str]],
) -> str:
    lines = frontmatter(title, description, url_slug)
    lines += [f"# {title}", "", description, ""]
    for func_name, src_file in functions:
        tree = load_tree(Path(src_file))
        node = find_function(tree, func_name)
        assert node, f"Function {func_name!r} not found in {src_file}"
        lines += render_method(node, is_method=False)
        lines += ["---", ""]
    return "\n".join(lines) + "\n"


def page_index() -> str:
    lines = frontmatter(
        "Python SDK",
        "Python SDK for creating and communicating with Disguise Designer plugins.",
        "index",
    )
    lines += [
        "# Python SDK",
        "",
        "The `designer-plugin` Python package provides tools for building and communicating",
        "with Disguise Designer plugins.",
        "",
        "```bash",
        "pip install designer-plugin",
        "```",
        "",
        "## Reference",
        "",
        f"| Page | Description |",
        f"|------|-------------|",
        f"| [DesignerPlugin](/{URL_BASE}/designer-plugin) | DNS-SD plugin discovery and registration |",
        f"| [Models](/{URL_BASE}/models) | Request/response payload models |",
        f"| [D3Session](/{URL_BASE}/d3session) | Sync and async session management |",
        f"| [D3PluginClient](/{URL_BASE}/d3pluginclient) | Class-based remote plugin execution |",
        f"| [d3sdk](/{URL_BASE}/d3sdk) | `@d3function` and `@d3pythonscript` decorators |",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Page manifest ─────────────────────────────────────────────────────────────

PAGES: list[tuple[str, callable]] = [
    ("index.md", lambda: page_index()),
    (
        "designer-plugin.md",
        lambda: page_single_class("DesignerPlugin", "designer_plugin.py", "designer-plugin"),
    ),
    (
        "models.md",
        lambda: page_multi_class(
            "Models",
            "Pydantic models and types used in the Designer Plugin API.",
            "models",
            [
                ("PluginPayload", "models.py"),
                ("PluginResponse", "models.py"),
                ("PluginError", "models.py"),
                ("PluginRegisterResponse", "models.py"),
                ("PluginStatus", "models.py"),
                ("PluginStatusDetail", "models.py"),
                ("RegisterPayload", "models.py"),
                ("PluginException", "models.py"),
            ],
        ),
    ),
    (
        "d3session.md",
        lambda: page_multi_class(
            "D3Session",
            "Sync and async session classes for communicating with Designer.",
            "d3session",
            [
                ("D3Session", "d3sdk/session.py"),
                ("D3AsyncSession", "d3sdk/session.py"),
            ],
        ),
    ),
    (
        "d3pluginclient.md",
        lambda: page_single_class("D3PluginClient", "d3sdk/client.py", "d3pluginclient"),
    ),
    (
        "d3sdk.md",
        lambda: page_functions(
            "d3sdk Decorators & Functions",
            "Decorators and utilities for registering and executing Designer functions.",
            "d3sdk",
            [
                ("d3function", "d3sdk/function.py"),
                ("d3pythonscript", "d3sdk/function.py"),
                ("get_register_payload", "d3sdk/function.py"),
                ("get_all_d3functions", "d3sdk/function.py"),
                ("get_all_modules", "d3sdk/function.py"),
            ],
        ),
    ),
]


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--docs-repo",
        default=str(DEFAULT_DOCS_REPO),
        help="Path to the d3_doc_dev Astro docs repository (default: %(default)s)",
    )
    args = parser.parse_args()

    out_dir = Path(args.docs_repo) / OUTPUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)

    for filename, builder in PAGES:
        content = builder()
        path = out_dir / filename
        path.write_text(content, encoding="utf-8")
        print(f"  wrote {path.relative_to(Path(args.docs_repo))}")

    print(f"\nGenerated {len(PAGES)} pages in {out_dir}")


if __name__ == "__main__":
    main()
