"""Complexity analyzer calculating Cyclomatic Complexity, nesting depth, and metrics."""

import ast
from typing import Any, Dict, List, Optional


class ASTComplexityVisitor(ast.NodeVisitor):
    """AST visitor to calculate McCabe cyclomatic complexity and nesting depth."""

    def __init__(self) -> None:
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self._current_function: Optional[Dict[str, Any]] = None
        self._current_class: Optional[Dict[str, Any]] = None
        self._nesting_depth = 0
        self._max_nesting_in_func = 0

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev_class = self._current_class
        class_info = {
            "name": node.name,
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "methods_count": 0,
        }
        self.classes.append(class_info)
        self._current_class = class_info

        self.generic_visit(node)
        self._current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)

    def _process_function(self, node: Any) -> None:
        prev_func = self._current_function
        prev_max_nesting = self._max_nesting_in_func
        prev_depth = self._nesting_depth

        self._nesting_depth = 1
        self._max_nesting_in_func = 1

        # Count parameters
        args = node.args
        param_count = (
            len(args.args)
            + len(getattr(args, "posonlyargs", []))
            + len(args.kwonlyargs)
            + (1 if args.vararg else 0)
            + (1 if args.kwarg else 0)
        )
        # Exclude self or cls if method inside a class
        if self._current_class and args.args and args.args[0].arg in ("self", "cls"):
            param_count = max(0, param_count - 1)

        func_info: Dict[str, Any] = {
            "name": node.name,
            "qualified_name": f"{self._current_class['name']}.{node.name}" if self._current_class else node.name,
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "line_count": getattr(node, "end_lineno", node.lineno) - node.lineno + 1,
            "complexity": 1,  # Base McCabe complexity
            "param_count": param_count,
            "max_nesting": 1,
            "is_method": self._current_class is not None,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        }
        if self._current_class:
            self._current_class["methods_count"] += 1

        self.functions.append(func_info)
        self._current_function = func_info

        # Visit child nodes to compute complexity and nesting
        for child in node.body:
            self.visit(child)

        func_info["max_nesting"] = self._max_nesting_in_func

        self._current_function = prev_func
        self._max_nesting_in_func = prev_max_nesting
        self._nesting_depth = prev_depth

    # Branching nodes that increase McCabe Cyclomatic Complexity
    def visit_If(self, node: ast.If) -> None:
        if self._current_function:
            self._current_function["complexity"] += 1
            self._nesting_depth += 1
            self._max_nesting_in_func = max(self._max_nesting_in_func, self._nesting_depth)
        self.generic_visit(node)
        if self._current_function:
            self._nesting_depth -= 1

    def visit_For(self, node: ast.For) -> None:
        if self._current_function:
            self._current_function["complexity"] += 1
            self._nesting_depth += 1
            self._max_nesting_in_func = max(self._max_nesting_in_func, self._nesting_depth)
        self.generic_visit(node)
        if self._current_function:
            self._nesting_depth -= 1

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        if self._current_function:
            self._current_function["complexity"] += 1
            self._nesting_depth += 1
            self._max_nesting_in_func = max(self._max_nesting_in_func, self._nesting_depth)
        self.generic_visit(node)
        if self._current_function:
            self._nesting_depth -= 1

    def visit_While(self, node: ast.While) -> None:
        if self._current_function:
            self._current_function["complexity"] += 1
            self._nesting_depth += 1
            self._max_nesting_in_func = max(self._max_nesting_in_func, self._nesting_depth)
        self.generic_visit(node)
        if self._current_function:
            self._nesting_depth -= 1

    def visit_Try(self, node: ast.Try) -> None:
        if self._current_function:
            self._current_function["complexity"] += len(node.handlers)
            self._nesting_depth += 1
            self._max_nesting_in_func = max(self._max_nesting_in_func, self._nesting_depth)
        self.generic_visit(node)
        if self._current_function:
            self._nesting_depth -= 1

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if self._current_function:
            # and/or branches add complexity
            self._current_function["complexity"] += len(node.values) - 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        if self._current_function:
            self._current_function["complexity"] += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        if self._current_function:
            self._current_function["complexity"] += len(node.cases)
        self.generic_visit(node)


class ComplexityAnalyzer:
    """Computes code complexity, metrics and function/class inventories."""

    @staticmethod
    def analyze_python_source(source_code: str) -> Dict[str, Any]:
        """Analyze Python source and return complexity metrics for functions, classes, and file."""
        lines = source_code.splitlines()
        loc = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))

        try:
            tree = ast.parse(source_code)
            visitor = ASTComplexityVisitor()
            visitor.visit(tree)
            functions = visitor.functions
            classes = visitor.classes
        except SyntaxError:
            functions = []
            classes = []

        return {
            "loc": loc,
            "code_lines": loc - blank_lines - comment_lines,
            "comment_lines": comment_lines,
            "blank_lines": blank_lines,
            "functions": functions,
            "classes": classes,
        }
