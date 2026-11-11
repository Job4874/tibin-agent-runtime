class TaskDecomposer:
    def __init__(self):
        pass

    def decompose(self, goal: str) -> list:
        # MVP: simplistic split or just return goal as one task
        return [{"description": f"Handle {goal}", "type": "mixed"}]
