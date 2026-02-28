class ProbabilityLineageTracer:
    def __init__(self, pick_id):
        self.pick_id = pick_id
        self.steps = []
        self.inputs = {}
        self.final = {}

    def log(self, stage, params, output):
        self.steps.append({
            "stage": stage,
            "params": params,
            "output": output
        })

    def set_inputs(self, inputs):
        self.inputs = inputs

    def set_final(self, final):
        self.final = final

    def export(self):
        return {
            "pick_id": self.pick_id,
            "inputs": self.inputs,
            "steps": self.steps,
            "final": self.final
        }

    def save(self, path):
        import json
        with open(path, 'w') as f:
            json.dump(self.export(), f, indent=2)
