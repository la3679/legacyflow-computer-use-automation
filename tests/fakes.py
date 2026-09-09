"""Scripted planner for offline tests only; never used for live discovery evidence."""

from legacyflow.models.contracts import Decision, Observation


class ScriptedPlanner:
    async def decide(
        self, goal: str, observation: Observation, inputs: dict[str, str], history: list[str]
    ) -> Decision:
        action, name, input_name, literal = "finish", None, None, None
        controls = {c.name: c for c in observation.controls}
        if observation.heading == "Member Search":
            if controls["Member ID"].value_state == "empty":
                action, name, input_name = "type", "Member ID", "member_id"
            else:
                action, name = "click", "Search"
        elif observation.heading == "Member Details":
            action, name = "click", "Open Sub-Account"
        elif observation.heading == "Open New Sub-Account":
            if controls["Account Type"].value_state == "empty":
                action, name, literal = "select", "Account Type", "Savings"
            elif controls["Initial Deposit"].value_state == "empty":
                action, name, input_name = "type", "Initial Deposit", "initial_deposit"
            else:
                action, name = "click", "Continue"
        return Decision.model_validate(
            {
                "action": action,
                "control_id": controls[name].id if name else None,
                "input_name": input_name,
                "literal": literal,
                "rationale_summary": "Offline test decision",
            }
        )
