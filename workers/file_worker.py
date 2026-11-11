import os
from typing import Dict, Any

class FileWorker:
    def __init__(self, base_dir: str, redaction_tool=None):
        self.base_dir = os.path.abspath(os.path.normpath(base_dir))
        self.redaction_tool = redaction_tool

    def _resolve_path(self, path: str) -> str:
        # Normalise Windows-style backslashes and resolve against base_dir
        normalised = path.replace("\\", "/").rstrip("/")
        if not normalised:
            normalised = "."
        abs_path = os.path.abspath(os.path.normpath(os.path.join(self.base_dir, normalised)))
        return abs_path

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type")
        params = action.get("params", {})
        path = params.get("path", "")
        content = params.get("content", "")

        if not path and action_type != "search":
            return {"status": "failed", "error": "No path provided."}

        try:
            if path:
                path = self._resolve_path(path)

            if action_type == "read":
                if not os.path.exists(path):
                    return {"status": "failed", "error": f"File not found: {path}"}
                with open(path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                
                if self.redaction_tool:
                    file_content = self.redaction_tool.redact(file_content)
                    
                return {"status": "success", "data": {"content": file_content}}

            elif action_type == "write":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"status": "success", "data": {"message": f"File written: {path}"}}

            elif action_type == "append":
                with open(path, "a", encoding="utf-8") as f:
                    f.write(content)
                return {"status": "success", "data": {"message": f"File appended: {path}"}}

            elif action_type == "replace_content":
                target = params.get("target", "")
                replacement = params.get("replacement", "")
                if not os.path.exists(path):
                    return {"status": "failed", "error": f"File not found: {path}"}
                with open(path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                if target not in file_content:
                    return {"status": "failed", "error": "Target string not found in file"}
                file_content = file_content.replace(target, replacement)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(file_content)
                return {"status": "success", "data": {"message": f"Content replaced in {path}"}}

            elif action_type == "list":
                if not os.path.exists(path):
                    return {"status": "failed", "error": f"Path not found: {path}"}
                files = os.listdir(path)
                return {"status": "success", "data": {"files": files}}

            elif action_type == "search":
                search_dir = self._resolve_path(params.get("dir", "."))
                query = params.get("query", "")
                if not query:
                    return {"status": "failed", "error": "Query required for search"}
                
                import glob
                results = []
                for filepath in glob.iglob(os.path.join(search_dir, "**/*"), recursive=True):
                    if os.path.isfile(filepath):
                        try:
                            with open(filepath, "rb") as f:
                                if b'\0' in f.read(1024):
                                    continue
                        except Exception:
                            continue
                            
                        try:
                            with open(filepath, "r", encoding="utf-8") as f:
                                for i, line in enumerate(f):
                                    if query in line:
                                        rel_path = os.path.relpath(filepath, self.base_dir)
                                        results.append(f"{rel_path}:{i+1}: {line.strip()}")
                        except UnicodeDecodeError:
                            pass # Skip binary files
                return {"status": "success", "data": {"matches": results}}

            elif action_type == "create_dir":
                os.makedirs(path, exist_ok=True)
                return {"status": "success", "data": {"message": f"Directory created: {path}"}}
            
            elif action_type == "delete":
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return {"status": "success", "data": {"message": f"Deleted: {path}"}}

            else:
                return {"status": "failed", "error": f"Unknown file action: {action_type}"}

        except Exception as e:
            return {"status": "failed", "error": str(e)}
