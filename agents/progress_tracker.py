class ProgressTracker:
    def __init__(self):
        self.progress = []

    def record_success(self, action_id: str):
        self.progress.append({"action_id": action_id, "status": "success"})

    def record_failure(self, action_id: str, error: str):
        self.progress.append({"action_id": action_id, "status": "failed", "error": error})

    def get_summary(self) -> str:
        success_count = sum(1 for p in self.progress if p["status"] == "success")
        fail_count = sum(1 for p in self.progress if p["status"] == "failed")
        return f"Progress: {success_count} succeeded, {fail_count} failed."
