class QuestionRefiner:
    def __init__(self):
        pass

    def refine_question(self, question: str, context: str) -> str:
        # Simplistic MVP
        return f"Given this context: {context}\nRefined question: {question}"

    def generate_prompt_variants(self, failure_reason: str) -> dict:
        return {
            "Direct": f"Given this exact failure, what is the next smallest fix? Failure: {failure_reason}",
            "Red-team": "What assumption is wrong in this plan?",
            "Senior engineer": f"Act as a principal engineer. Diagnose why this failed: {failure_reason}",
            "Minimal action": "What is the next single action the runtime should take?"
        }
