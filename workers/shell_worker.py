import subprocess
import os
import atexit
import shlex
import threading
from typing import Dict, Any

class ShellWorker:
    def __init__(self):
        self.processes = {}
        atexit.register(self._cleanup)

    def _cleanup(self):
        for pid, pinfo in self.processes.items():
            process = pinfo.get("process")
            if process and process.poll() is None:
                try:
                    process.terminate()
                except:
                    pass

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("type", "execute")
        params = action.get("params", {})
        
        if action_type in ("execute", "run"):
            return self._execute_command(params)
        elif action_type == "check_status":
            return self._check_status(params)
        elif action_type == "kill_process":
            return self._kill_process(params)
        else:
            return {"status": "failed", "error": f"Unknown action type: {action_type}"}

    def _execute_command(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = params.get("command", "")
        timeout = params.get("timeout", 30)
        background = params.get("background", False)
        cwd = params.get("cwd", os.getcwd())
        env_updates = params.get("env", {})

        if not command:
            return {"status": "failed", "error": "No command provided."}

        env = os.environ.copy()
        env.update(env_updates)

        try:
            cmd_args = shlex.split(command)
        except Exception:
            cmd_args = command.split(" ")

        # Check for windows builtins that need shell
        use_shell = False
        if os.name == 'nt' and cmd_args[0] in ['dir', 'echo', 'type']:
            use_shell = True

        try:
            if background:
                process = subprocess.Popen(
                    command if use_shell else cmd_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=env,
                    shell=use_shell,
                    text=True
                )
                pid = str(process.pid)
                
                stdout_buf = []
                stderr_buf = []
                
                def drain_stream(stream, buffer):
                    for line in iter(stream.readline, ''):
                        buffer.append(line)
                    stream.close()
                    
                t_out = threading.Thread(target=drain_stream, args=(process.stdout, stdout_buf), daemon=True)
                t_err = threading.Thread(target=drain_stream, args=(process.stderr, stderr_buf), daemon=True)
                t_out.start()
                t_err.start()

                self.processes[pid] = {
                    "process": process,
                    "command": command,
                    "stdout_buf": stdout_buf,
                    "stderr_buf": stderr_buf
                }
                return {
                    "status": "success",
                    "data": {
                        "pid": pid,
                        "message": "Process started in background"
                    }
                }
            else:
                result = subprocess.run(
                    command if use_shell else cmd_args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=cwd,
                    env=env,
                    shell=use_shell
                )
                return {
                    "status": "success" if result.returncode == 0 else "failed",
                    "data": {
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.returncode
                    }
                }
        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": f"Command timed out after {timeout} seconds."}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    def _check_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pid = str(params.get("pid"))
        if pid not in self.processes:
            return {"status": "failed", "error": f"Process {pid} not found in registry."}
            
        process = self.processes[pid]["process"]
        retcode = process.poll()
        is_running = (retcode is None)
        
        stdout_buf = self.processes[pid].get("stdout_buf", [])
        stderr_buf = self.processes[pid].get("stderr_buf", [])
        
        return {
            "status": "success",
            "data": {
                "pid": pid,
                "is_running": is_running,
                "exit_code": retcode,
                "stdout": "".join(stdout_buf),
                "stderr": "".join(stderr_buf)
            }
        }

    def _kill_process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pid = str(params.get("pid"))
        if pid not in self.processes:
            return {"status": "failed", "error": f"Process {pid} not found in registry."}
            
        process = self.processes[pid]["process"]
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
            
        del self.processes[pid]
        return {
            "status": "success",
            "data": {
                "pid": pid,
                "message": "Process killed"
            }
        }
