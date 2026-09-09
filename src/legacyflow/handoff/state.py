from enum import StrEnum

from legacyflow.models.contracts import Contract


class RunState(StrEnum):
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    HUMAN_CONTROLLED = "HUMAN_CONTROLLED"
    RESUMING = "RESUMING"
    ABORTED = "ABORTED"


class Intervention(Contract):
    id: str
    run_id: str
    session_id: str
    capability: str
    step_id: str
    reason: str
    expected_heading: str
    screenshot: str
    owner: str
    state: RunState
    requested_action: str = "Review the exception in the same browser, then Resume or Abort."


TRANSITIONS = {
    RunState.RUNNING: {RunState.WAITING_FOR_HUMAN},
    RunState.WAITING_FOR_HUMAN: {RunState.HUMAN_CONTROLLED, RunState.ABORTED},
    RunState.HUMAN_CONTROLLED: {RunState.RESUMING, RunState.ABORTED},
    RunState.RESUMING: {RunState.RUNNING, RunState.ABORTED},
    RunState.ABORTED: set(),
}
