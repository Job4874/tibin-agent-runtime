"""
ResearchWorker — file-system and in-repo research operations.

Supported action types:
  find_files       Find files matching a glob or name pattern.
  read_file        Read a file and return its contents.
  summarize_dir    Return a directory tree with file sizes.
  grep             Search file contents with a regex pattern.
  diff_files       Compute a unified diff between two files.
"""

import os
import re
import difflib
from pathlib import Path
from typing import Any, Dict, List


_SUPPORTED_TYPES = {"find_files", "read_file", "summarize_dir", "grep", "diff_files"}


class ResearchWorker:
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir).resolve()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type", "")
        params = action.get("params", {})

        dispatch = {
            "find_files": self._find_files,
            "read_file": self._read_file,
            "summarize_dir": self._summarize_dir,
            "grep": self._grep,
            "diff_files": self._diff_files,
        }

        handler = dispatch.get(action_type)
        if handler is None:
            return {
                "status": "failed",
                "error": f"ResearchWorker does not support action type '{action_type}'. "
                         f"Supported: {sorted(_SUPPORTED_TYPES)}",
            }

        try:
            return handler(params)
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _find_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pattern = params.get("pattern", "*")
        directory = params.get("directory", ".")
        max_results = int(params.get("max_results", 50))
        recursive = bool(params.get("recursive", True))

        search_root = self._safe_path(directory)
        if search_root is None or not search_root.is_dir():
            search_root = self.base_dir

        files: List[Dict[str, Any]] = []
        glob_fn = search_root.rglob if recursive else search_root.glob

        for p in sorted(glob_fn(pattern)):
            if any(part.startswith(".") or part in ("__pycache__", "node_modules")
                   for part in p.parts):
                continue
            if p.is_file():
                rel = str(p.relative_to(self.base_dir)) if p.is_relative_to(self.base_dir) else str(p)
                files.append({"path": rel, "size_bytes": p.stat().st_size})
            if len(files) >= max_results:
                break

        return {
            "status": "success",
            "data": {
                "pattern": pattern,
                "directory": directory,
                "files": files,
                "count": len(files),
                "truncated": len(files) >= max_results,
            },
        }

    def _read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_str = params.get("path", "")
        max_chars = int(params.get("max_chars", 20000))
        start_line = int(params.get("start_line", 1))
        end_line = params.get("end_line")

        if not path_str:
            return {"status": "failed", "error": "Missing required param: path"}

        target = self._safe_path(path_str)
        if target is None:
            return {"status": "failed", "error": f"Path escapes base_dir: {path_str}"}
        if not target.exists():
            return {"status": "failed", "error": f"File not found: {path_str}"}

        content = target.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines(keepends=True)
        total_lines = len(lines)

        sl = max(1, start_line) - 1
        el = int(end_line) if end_line is not None else total_lines
        selected = "".join(lines[sl:el])

        truncated = False
        if len(selected) > max_chars:
            selected = selected[:max_chars]
            truncated = True

        return {
            "status": "success",
            "data": {
                "path": path_str,
                "content": selected,
                "total_lines": total_lines,
                "lines_returned": f"{sl + 1}-{min(el, total_lines)}",
                "truncated": truncated,
            },
        }

    def _summarize_dir(self, params: Dict[str, Any]) -> Dict[str, Any]:
        directory = params.get("directory", ".")
        max_depth = int(params.get("max_depth", 3))
        include_hidden = bool(params.get("include_hidden", False))

        target = self._safe_path(directory)
        if target is None or not target.is_dir():
            target = self.base_dir

        tree: List[str] = []
        totals: Dict[str, int] = {"files": 0, "dirs": 0, "total_bytes": 0}

        def _walk(d: Path, depth: int, prefix: str = ""):
            if depth > max_depth:
                return
            try:
                entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except PermissionError:
                return
            for entry in entries:
                if not include_hidden and entry.name.startswith("."):
                    continue
                if entry.name in ("__pycache__", "node_modules", ".git"):
                    continue
                connector = "└── " if entry == entries[-1] else "├── "
                if entry.is_dir():
                    tree.append(f"{prefix}{connector}{entry.name}/")
                    totals["dirs"] += 1
                    child_prefix = prefix + ("    " if entry == entries[-1] else "│   ")
                    _walk(entry, depth + 1, child_prefix)
                else:
                    size = entry.stat().st_size
                    totals["files"] += 1
                    totals["total_bytes"] += size
                    size_str = self._human_size(size)
                    tree.append(f"{prefix}{connector}{entry.name} ({size_str})")

        _walk(target, 1)
        rel_dir = str(target.relative_to(self.base_dir)) if target.is_relative_to(self.base_dir) else str(target)

        return {
            "status": "success",
            "data": {
                "directory": rel_dir,
                "tree": "\n".join(tree),
                "file_count": totals["files"],
                "dir_count": totals["dirs"],
                "total_size": self._human_size(totals["total_bytes"]),
            },
        }

    def _grep(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pattern = params.get("pattern", "")
        directory = params.get("directory", ".")
        extensions = params.get("extensions", [])
        max_results = int(params.get("max_results", 50))
        case_insensitive = bool(params.get("case_insensitive", False))

        if not pattern:
            return {"status": "failed", "error": "Missing required param: pattern"}

        search_root = self._safe_path(directory)
        if search_root is None:
            search_root = self.base_dir

        flags = re.IGNORECASE if case_insensitive else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as exc:
            return {"status": "failed", "error": f"Invalid regex: {exc}"}

        ext_set = {e.lower() for e in extensions} if extensions else None
        matches: List[Dict[str, Any]] = []

        for fpath in sorted(search_root.rglob("*")):
            if not fpath.is_file():
                continue
            if ext_set and fpath.suffix.lower() not in ext_set:
                continue
            if any(part.startswith(".") or part in ("__pycache__", "node_modules")
                   for part in fpath.parts):
                continue
            try:
                for lineno, line in enumerate(fpath.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if regex.search(line):
                        rel = str(fpath.relative_to(self.base_dir)) if fpath.is_relative_to(self.base_dir) else str(fpath)
                        matches.append({"file": rel, "line": lineno, "text": line.rstrip()})
                        if len(matches) >= max_results:
                            break
            except Exception:
                continue
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

    def _diff_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path_a = params.get("path_a", "")
        path_b = params.get("path_b", "")

        if not path_a or not path_b:
            return {"status": "failed", "error": "Missing required params: path_a, path_b"}

        target_a = self._safe_path(path_a)
        target_b = self._safe_path(path_b)

        for label, target, orig in [("path_a", target_a, path_a), ("path_b", target_b, path_b)]:
            if target is None:
                return {"status": "failed", "error": f"{label} escapes base_dir: {orig}"}
            if not target.exists():
                return {"status": "failed", "error": f"{label} not found: {orig}"}

        lines_a = target_a.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        lines_b = target_b.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

        diff = list(difflib.unified_diff(lines_a, lines_b, fromfile=path_a, tofile=path_b))
        diff_text = "".join(diff)

        return {
            "status": "success",
            "data": {
                "path_a": path_a,
                "path_b": path_b,
                "diff": diff_text,
                "changed_lines": sum(1 for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))),
                "identical": len(diff) == 0,
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
    def _human_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"
