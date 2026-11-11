import subprocess
from typing import Dict, Any
import os

class GitWorker:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _run_git(self, args: list) -> Dict[str, Any]:
        try:
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            result = subprocess.run(
                ["git"] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                shell=False,
                env=env
            )
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "data": {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode
                }
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type")
        params = action.get("params", {})

        if action_type != "init" and not os.path.exists(os.path.join(self.repo_path, ".git")):
            return {"status": "failed", "error": "Not a git repository. Run 'init' first."}

        if action_type == "init":
            os.makedirs(self.repo_path, exist_ok=True)
            return self._run_git(["init"])

        elif action_type == "status":
            return self._run_git(["status"])
        
        elif action_type == "diff":
            path = params.get("path", "")
            if path:
                return self._run_git(["diff", "--", path])
            return self._run_git(["diff"])
            
        elif action_type == "stage":
            path = params.get("path", ".")
            return self._run_git(["add", path])
            
        elif action_type == "commit":
            message = params.get("message", "")
            if not message:
                return {"status": "failed", "error": "Commit message required."}
            return self._run_git(["commit", "-m", message])
            
        elif action_type == "push":
            remote = params.get("remote", "origin")
            branch = params.get("branch", "main")
            return self._run_git(["push", remote, branch])

        elif action_type == "pull":
            remote = params.get("remote", "origin")
            branch = params.get("branch", "main")
            return self._run_git(["pull", remote, branch])

        elif action_type == "checkout":
            branch = params.get("branch", "")
            create = params.get("create", False)
            if not branch:
                return {"status": "failed", "error": "Branch name required for checkout."}
            if create:
                return self._run_git(["checkout", "-b", branch])
            return self._run_git(["checkout", branch])

        elif action_type == "branch":
            return self._run_git(["branch", "-a"])

        elif action_type == "log":
            n = str(params.get("n", 5))
            return self._run_git(["log", "-n", n, "--oneline"])
            
        else:
            return {"status": "failed", "error": f"Unknown git action: {action_type}"}
