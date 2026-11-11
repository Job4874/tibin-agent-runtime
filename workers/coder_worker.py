"""
CoderWorker — code generation, analysis, linting, and snippet writing.

Supported action types:
  write_code     Write a code snippet to a file (creates or overwrites).
  analyze_code   Return basic metrics about a file (lines, functions, classes, imports).
  lint_code      Run a linter (flake8 / eslint) if available; fall back to syntax check.
  explain_code   Return the first docstring / block-comment from a file.
  search_code    Search for a pattern inside source files.
"""

import os
import ast
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List


_SUPPORTED_TYPES = {"write_code", "analyze_code", "lint_code", "explain_code", "search_code"}


class CoderWorker:
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type", "")
        params = action.get("params", {})

        dispatch = {
            "write_code": self._write_code,
            "analyze_code": self._analyze_code,
            "lint_code": self._lint_code,
            "explain_code": self._explain_code,
            "search_code": self._search_code,
        }

        handler = dispatch.get(action_type)
        if handler is None:
            return {
                "status": "failed",
                "error": f"CoderWorker does not support action type '{action_type}'. "
                         f"Supported: {sorted(_SUPPORTED_TYPES)}",
            }

        try:
            return handler(params)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _write_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_str = params.get("path", "")
        content = params.get("content", "")
        language = params.get("language", "")
        overwrite = params.get("overwrite", True)

        if not path_str:
            return {"status": "failed", "error": "Missing required param: path"}
        if not content:
            return {"status": "failed", "error": "Missing required param: content"}

        target = self._safe_path(path_str)
        if target is None:
            return {"status": "failed", "error": f"Path escapes base_dir: {path_str}"}

        if target.exists() and not overwrite:
            return {
                "status": "failed",
                "error": f"File already exists and overwrite=false: {path_str}",
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        # Dedent so plans can embed indented code blocks
        cleaned = textwrap.dedent(content)
        target.write_text(cleaned, encoding="utf-8")

        lines = cleaned.count("\n") + 1
        return {
            "status": "success",
            "data": {
                "path": str(target.relative_to(self.base_dir)),
                "language": language or self._guess_language(path_str),
                "lines_written": lines,
                "bytes_written": len(cleaned.encode("utf-8")),
            },
        }

    def _analyze_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_str = params.get("path", "")
        if not path_str:
            return {"status": "failed", "error": "Missing required param: path"}

        target = self._safe_path(path_str)
        if target is None:
            return {"status": "failed", "error": f"Path escapes base_dir: {path_str}"}
        if not target.exists():
            return {"status": "failed", "error": f"File not found: {path_str}"}

        source = target.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        metrics: Dict[str, Any] = {
            "path": path_str,
            "lines_total": len(lines),
            "lines_code": sum(1 for l in lines if l.strip() and not l.strip().startswith("#")),
            "lines_comments": sum(1 for l in lines if l.strip().startswith("#")),
            "lines_blank": sum(1 for l in lines if not l.strip()),
            "language": self._guess_language(path_str),
        }

        if path_str.endswith(".py"):
            try:
                tree = ast.parse(source)
                metrics["functions"] = sum(
                    1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                )
                metrics["classes"] = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
                metrics["imports"] = sum(
                    1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                )
                metrics["syntax_ok"] = True
            except SyntaxError as exc:
                metrics["syntax_ok"] = False
                metrics["syntax_error"] = str(exc)

        return {"status": "success", "data": metrics}

    def _lint_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_str = params.get("path", "")
        if not path_str:
            return {"status": "failed", "error": "Missing required param: path"}

        target = self._safe_path(path_str)
        if target is None:
            return {"status": "failed", "error": f"Path escapes base_dir: {path_str}"}
        if not target.exists():
            return {"status": "failed", "error": f"File not found: {path_str}"}

        language = self._guess_language(path_str)
        issues: List[str] = []
        linter_used = "none"

        if language == "python":
            # Try flake8 first, fall back to ast syntax check
            try:
                result = subprocess.run(
                    ["flake8", "--max-line-length=120", str(target)],
                    capture_output=True, text=True, timeout=30,
                )
                issues = [l for l in result.stdout.splitlines() if l.strip()]
                linter_used = "flake8"
            except FileNotFoundError:
                # flake8 not installed — syntax only
                source = target.read_text(encoding="utf-8", errors="replace")
                try:
                    ast.parse(source)
                    linter_used = "ast_syntax"
                except SyntaxError as exc:
                    issues = [f"SyntaxError: {exc}"]
                    linter_used = "ast_syntax"
        elif language in ("javascript", "typescript"):
            try:
                result = subprocess.run(
                    ["npx", "--yes", "eslint", "--no-eslintrc", "--rule", "no-undef:warn",
                     str(target)],
                    capture_output=True, text=True, timeout=60,
                )
                issues = [l for l in result.stdout.splitlines() if l.strip()]
                linter_used = "eslint"
            except Exception:
                linter_used = "none"
        else:
            linter_used = "none"

        return {
            "status": "success",
            "data": {
                "path": path_str,
                "linter": linter_used,
                "issues": issues,
                "issue_count": len(issues),
                "clean": len(issues) == 0,
            },
        }

    def _explain_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_str = params.get("path", "")
        if not path_str:
            return {"status": "failed", "error": "Missing required param: path"}

        target = self._safe_path(path_str)
        if target is None:
            return {"status": "failed", "error": f"Path escapes base_dir: {path_str}"}
        if not target.exists():
            return {"status": "failed", "error": f"File not found: {path_str}"}

        source = target.read_text(encoding="utf-8", errors="replace")
        explanation = self._extract_docstring(source, path_str)

        return {
            "status": "success",
            "data": {
                "path": path_str,
                "docstring": explanation,
                "language": self._guess_language(path_str),
            },
        }

    def _search_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pattern = params.get("pattern", "")
        directory = params.get("directory", ".")
        extensions = params.get("extensions", [".py", ".js", ".ts", ".json", ".md"])
        max_results = int(params.get("max_results", 20))

        if not pattern:
            return {"status": "failed", "error": "Missing required param: pattern"}

        search_root = self._safe_path(directory)
        if search_root is None:
            search_root = self.base_dir

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return {"status": "failed", "error": f"Invalid regex pattern: {exc}"}

        matches: List[Dict[str, Any]] = []
        ext_set = {e.lower() for e in extensions}

        for fpath in search_root.rglob("*"):
            if not fpath.is_file():
                continue
            if ext_set and fpath.suffix.lower() not in ext_set:
                continue
            # Skip hidden dirs and common noise
            if any(part.startswith(".") or part in ("__pycache__", "node_modules")
                   for part in fpath.parts):
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for lineno, line in enumerate(lines, 1):
                if regex.search(line):
                    rel = str(fpath.relative_to(self.base_dir)) if fpath.is_relative_to(self.base_dir) else str(fpath)
                    matches.append({"file": rel, "line": lineno, "text": line.rstrip()})
                    if len(matches) >= max_results:
                        break
            if len(matches) >= max_results:
                break

        return {
            "status": "success",
            "data": {
                "pattern": pattern,
                "matches": matches,
                "match_count": len(matches),
                "truncated": len(matches) >= max_results,
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_path(self, rel: str) -> "Path | None":
        try:
            candidate = (self.base_dir / rel).resolve()
            candidate.relative_to(self.base_dir)
            return candidate
        except ValueError:
            return None

    @staticmethod
    def _guess_language(path: str) -> str:
        ext = Path(path).suffix.lower()
        return {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".sh": "bash",
            ".bash": "bash",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".html": "html",
            ".css": "css",
            ".md": "markdown",
        }.get(ext, "generic")

    @staticmethod
    def _extract_docstring(source: str, path: str) -> str:
        if path.endswith(".py"):
            try:
                tree = ast.parse(source)
                first = ast.get_docstring(tree)
                if first:
                    return first
            except SyntaxError:
                pass
        lines = source.splitlines()
        block: List[str] = []
        in_block = False
        for line in lines[:40]:
            stripped = line.strip()
            if not stripped:
                if in_block:
                    break
                continue
            if stripped.startswith(("#", "//", "/*", "*", "\"\"\"", "'''")):
                block.append(stripped.lstrip("#/*' \"").rstrip("*/ \"'"))
                in_block = True
            else:
                if in_block:
                    break
        return " ".join(block).strip() or "No docstring found."
