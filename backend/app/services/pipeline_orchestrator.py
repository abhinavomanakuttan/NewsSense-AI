from typing import Any


class PipelineOrchestrator:
    def __init__(self):
        self.steps: list[dict] = []

    def add_step(self, name: str, handler: callable, **kwargs) -> "PipelineOrchestrator":
        self.steps.append({"name": name, "handler": handler, "kwargs": kwargs})
        return self

    async def execute(self, data: Any) -> dict:
        results = {}
        current_data = data

        for step in self.steps:
            try:
                result = await step["handler"](current_data, **step["kwargs"])
                results[step["name"]] = {"status": "success", "output": result}
                current_data = result
            except Exception as e:
                results[step["name"]] = {"status": "failed", "error": str(e)}
                break

        return results
