"""The device state machine as an explicit transition table.

    PROGRAMMING → TESTING → LABELING → PACKAGING → COMPLETE
    any production stage → REJECTED
    COMPLETE and REJECTED are terminal.

Anything else is an illegal transition and raises :class:`IllegalTransitionError`.
"""

from __future__ import annotations

from collections.abc import Mapping

from parkomate.core.enums import Stage
from parkomate.core.errors import RecordStateError

TRANSITIONS: Mapping[Stage, frozenset[Stage]] = {
    Stage.PROGRAMMING: frozenset({Stage.TESTING, Stage.REJECTED}),
    Stage.TESTING: frozenset({Stage.LABELING, Stage.REJECTED}),
    Stage.LABELING: frozenset({Stage.PACKAGING, Stage.REJECTED}),
    Stage.PACKAGING: frozenset({Stage.COMPLETE, Stage.REJECTED}),
    Stage.COMPLETE: frozenset(),
    Stage.REJECTED: frozenset(),
}

ORDER: tuple[Stage, ...] = (
    Stage.PROGRAMMING,
    Stage.TESTING,
    Stage.LABELING,
    Stage.PACKAGING,
    Stage.COMPLETE,
)


class IllegalTransitionError(RecordStateError):
    """A stage change the state machine does not allow."""


def is_allowed(old: Stage, new: Stage) -> bool:
    return new in TRANSITIONS.get(old, frozenset())


def check_transition(old: Stage, new: Stage) -> None:
    if not is_allowed(old, new):
        raise IllegalTransitionError(
            f"illegal stage transition {old.value} -> {new.value}",
            context={"from": old.value, "to": new.value},
        )


def next_stage(stage: Stage) -> Stage:
    """The forward (non-reject) successor of ``stage``."""
    forward = [s for s in TRANSITIONS.get(stage, frozenset()) if s is not Stage.REJECTED]
    if not forward:
        raise IllegalTransitionError(f"{stage.value} has no next stage")
    return forward[0]


def is_terminal(stage: Stage) -> bool:
    return not TRANSITIONS.get(stage)
