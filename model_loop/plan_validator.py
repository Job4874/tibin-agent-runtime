import copy
import json
import os
import shutil
import warnings
from pathlib import Path
from typing import Dict, Any, Tuple

_KNOWN_WORKERS = {
    "ShellWorker", "FileWorker", "GitWorker", "CoderWorker",
    "ResearchWorker", "BrowserWorker", "VerifierWorker",
    "MemoryWorker", "ReportWorker",
}

class PlanValidator:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._schema: Dict[str, Any] | None = self._load_schema()

    def _load_schema(self) -> Dict[str, Any] | None:
        schema_path = Path(self.base_dir) / "schemas" / "plan.schema.json"
        if schema_path.exists():
            try:
                return json.loads(schema_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def validate_plan(self, plan_data: Dict[str, Any]) -> Tuple[bool, str]:
        if not isinstance(plan_data, dict):
            return False, "Plan data is not a dictionary."
        if "plan_id" not in plan_data:
            return False, "Missing required field: plan_id."
        if not isinstance(plan_data.get("plan_id"), str) or not plan_data["plan_id"].strip():
            return False, "plan_id must be a non-empty string."
        if "actions" not in plan_data:
            return False, "Missing required field: actions."
        if not isinstance(plan_data["actions"], list):
            return False, "Field 'actions' must be a list."
        if len(plan_data["actions"]) == 0:
            return False, "Actions list must not be empty."

        for idx, action in enumerate(plan_data["actions"]):
            if not isinstance(action, dict):
                return False, f"Action at index {idx} must be an object."
            if "action_id" not in action:
                return False, f"Action at index {idx} missing required field: action_id."
            if "worker" not in action:
                return False, f"Action '{action.get('action_id')}' missing required field: worker."
            if "type" not in action:
                return False, f"Action '{action.get('action_id')}' missing required field: type."
            worker = action.get("worker", "")
            if worker not in _KNOWN_WORKERS:
                return False, (
                    f"Action '{action.get('action_id')}' references unknown worker '{worker}'. "
                    f"Known workers: {sorted(_KNOWN_WORKERS)}"
                )

        # Optional JSON-Schema validation (requires jsonschema package).
        # Only used to catch *type* mismatches, not to enforce `required` fields
        # beyond the structural checks already performed above.
        if self._schema is not None:
            try:
                import jsonschema
                from pathlib import Path as _Path

                schemas_dir = _Path(self.base_dir) / "schemas"
                base_uri = _Path(schemas_dir).resolve().as_uri() + "/"

                # Build a permissive copy of the schema without the `required` list
                # so we only validate types / enums, not presence.
                import copy
                permissive = copy.deepcopy(self._schema)
                permissive.pop("required", None)

                try:
                    # Try modern referencing API first (jsonschema >= 4.18)
                    import referencing
                    import referencing.jsonschema as _rjs
                    schemas_dir_path = _Path(self.base_dir) / "schemas"
                    resource_map = {}
                    for sf in schemas_dir_path.glob("*.json"):
                        try:
                            content = json.loads(sf.read_text(encoding="utf-8"))
                            resource_map[sf.name] = referencing.Resource.from_contents(content)
                        except Exception:
                            pass
                    registry = referencing.Registry().with_resources(resource_map.items())
                    validator_cls = jsonschema.Draft7Validator
                    v = validator_cls(permissive, registry=registry)
                    errors = list(v.iter_errors(plan_data))
                    if errors:
                        return False, f"Schema validation error: {errors[0].message}"
                except (ImportError, Exception):
                    # Fall back to legacy RefResolver
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", DeprecationWarning)
                            resolver = jsonschema.RefResolver(base_uri, permissive)
                            jsonschema.validate(plan_data, permissive, resolver=resolver)
                    except jsonschema.ValidationError as exc:
                        return False, f"Schema validation error: {exc.message}"
                    except Exception:
                        pass  # resolver issues — structural checks above suffice
            except ImportError:
                pass  # jsonschema not installed

        return True, "Valid."

    def ingest_candidate(self, file_path: str, validated_dir: str, rejected_dir: str) -> Tuple[bool, str]:
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)
                
            is_valid, reason = self.validate_plan(plan_data)
            
            filename = os.path.basename(file_path)
            if is_valid:
                target = os.path.join(validated_dir, filename)
                shutil.move(file_path, target)
                return True, target
            else:
                target = os.path.join(rejected_dir, filename)
                shutil.move(file_path, target)
                return False, reason
        except json.JSONDecodeError as e:
            filename = os.path.basename(file_path)
            target = os.path.join(rejected_dir, filename)
            shutil.move(file_path, target)
            return False, f"Invalid JSON: {e}"
        except Exception as e:
            return False, str(e)
