"""Python plugin built on tree-sitter."""

from __future__ import annotations

import ast

import tree_sitter_python
from tree_sitter import Language, Node, Parser

from mytool.core.models import CodeUnit, LineRange, UnitKind

_DEFS = {"function_definition", "class_definition"}


class PythonPlugin:
    name = "python"
    extensions: tuple[str, ...] = (".py",)

    def __init__(self) -> None:
        self._parser = Parser(Language(tree_sitter_python.language()))

    def extract_units(self, source: str) -> list[CodeUnit]:
        data = source.encode("utf-8")
        tree = self._parser.parse(data)
        units: list[CodeUnit] = []
        _walk(tree.root_node, data, "", False, units)
        return units

    def check_syntax(self, source: str, filename: str) -> str | None:
        try:
            ast.parse(source, filename=filename)
        except SyntaxError as exc:
            return f"satır {exc.lineno or '?'}: {exc.msg}"
        except ValueError as exc:
            return str(exc)
        return None


def _walk(node: Node, data: bytes, prefix: str, in_class: bool, out: list[CodeUnit]) -> None:
    for child in node.children:
        definition = _definition(child)
        if definition is None:
            _walk(child, data, prefix, in_class, out)
            continue
        name_node = definition.child_by_field_name("name")
        if name_node is None or name_node.text is None:
            continue
        qualified = prefix + name_node.text.decode("utf-8")
        is_class = definition.type == "class_definition"
        kind = UnitKind.CLASS if is_class else UnitKind.METHOD if in_class else UnitKind.FUNCTION
        out.append(_make_unit(qualified, kind, child, data))
        _walk(definition, data, qualified + ".", is_class, out)


def _definition(node: Node) -> Node | None:
    if node.type in _DEFS:
        return node
    if node.type == "decorated_definition":
        return node.child_by_field_name("definition")
    return None


def _make_unit(name: str, kind: UnitKind, node: Node, data: bytes) -> CodeUnit:
    lines = LineRange(start=node.start_point[0] + 1, end=node.end_point[0] + 1)
    source = data[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
    return CodeUnit(name=name, kind=kind, lines=lines, source=source)
