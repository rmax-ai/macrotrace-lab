"""Deterministic evaluators for workflow runs."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol
from uuid import uuid4

from macrotrace.schemas.eval import EvalFinding, FindingType
from macrotrace.schemas.scenario import Scenario
from macrotrace.schemas.trace import EventType, Run, RunOutcome, TraceEvent


class Evaluator(Protocol):
    """Structural interface shared by deterministic evaluators."""

    name: str
    version: str

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Evaluate a workflow run and return a persisted-ready finding."""


def _build_finding(
    *,
    run_id: str,
    evaluator_name: str,
    evaluator_version: str,
    finding_type: FindingType,
    passed: bool,
    severity: int,
    evidence_event_ids: list[str],
    explanation: str,
    expected_behavior: str,
    observed_behavior: str,
) -> EvalFinding:
    """Construct an evaluation finding with deterministic metadata fields."""

    return EvalFinding(
        finding_id=f"finding-{uuid4().hex}",
        run_id=run_id,
        evaluator_name=evaluator_name,
        evaluator_version=evaluator_version,
        finding_type=finding_type,
        passed=passed,
        severity=severity,
        confidence=1.0,
        evidence_event_ids=evidence_event_ids,
        explanation=explanation,
        expected_behavior=expected_behavior,
        observed_behavior=observed_behavior,
    )


def _required_agents(scenario: Scenario) -> list[str]:
    """Extract required agent activations from scenario ground truth."""

    raw_value = scenario.ground_truth.get("must_activate_agents", [])
    if isinstance(raw_value, list):
        return [str(agent_name) for agent_name in raw_value]
    if raw_value:
        return ["coordinator"]
    return []


def _activated_agents(events: Sequence[TraceEvent]) -> set[str]:
    """Return the set of agents observed as started during the run."""

    return {
        event.agent_name
        for event in events
        if event.event_type is EventType.AGENT_STARTED and event.agent_name is not None
    }


def _decision_evidence_event_ids(events: Sequence[TraceEvent]) -> list[str]:
    """Collect terminal decision event identifiers for finding evidence."""

    return [
        event.event_id
        for event in events
        if event.event_type
        in {
            EventType.DECISION,
            EventType.REVIEW_REQUESTED,
            EventType.WORKFLOW_COMPLETED,
            EventType.ERROR,
        }
    ]


class OutcomeCorrectnessEval:
    """Verify that the run outcome matches the scenario expectation."""

    name = "outcome_correctness"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Compare the terminal outcome against the scenario contract."""

        expected_outcome = scenario.expected_outcome
        if expected_outcome is None or run.run_outcome.value == expected_outcome:
            return _build_finding(
                run_id=run.run_id,
                evaluator_name=self.name,
                evaluator_version=self.version,
                finding_type=FindingType.NONE,
                passed=True,
                severity=0,
                evidence_event_ids=_decision_evidence_event_ids(events),
                explanation="Run outcome matched the scenario expectation.",
                expected_behavior=(
                    "The workflow outcome should match the scenario expected_outcome when set."
                ),
                observed_behavior=f"Observed run outcome '{run.run_outcome.value}'.",
            )

        return _build_finding(
            run_id=run.run_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            finding_type=FindingType.INCORRECT_DECISION,
            passed=False,
            severity=scenario.severity_if_mishandled,
            evidence_event_ids=_decision_evidence_event_ids(events),
            explanation=("Run outcome did not match the scenario expected_outcome."),
            expected_behavior=f"Expected workflow outcome '{expected_outcome}'.",
            observed_behavior=f"Observed workflow outcome '{run.run_outcome.value}'.",
        )


class RequiredAgentActivationEval:
    """Verify that all required agents were activated during the run."""

    name = "required_agent_activation"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Check ground-truth required agents against observed agent activation."""

        required_agents = _required_agents(scenario)
        activated_agents = _activated_agents(events)
        missing_agents = sorted(set(required_agents) - activated_agents)
        evidence_event_ids = [
            event.event_id
            for event in events
            if event.event_type is EventType.AGENT_STARTED and event.agent_name in activated_agents
        ]

        if not missing_agents:
            return _build_finding(
                run_id=run.run_id,
                evaluator_name=self.name,
                evaluator_version=self.version,
                finding_type=FindingType.NONE,
                passed=True,
                severity=0,
                evidence_event_ids=evidence_event_ids,
                explanation="All required agents were activated during the workflow.",
                expected_behavior=(
                    "Every agent listed in scenario.ground_truth.must_activate_agents should "
                    "appear in the trace."
                ),
                observed_behavior=(f"Observed activated agents: {sorted(activated_agents)}."),
            )

        return _build_finding(
            run_id=run.run_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            finding_type=FindingType.ROUTING_ERROR,
            passed=False,
            severity=scenario.severity_if_mishandled,
            evidence_event_ids=evidence_event_ids,
            explanation="One or more required agents were not activated.",
            expected_behavior=f"Required agents: {sorted(required_agents)}.",
            observed_behavior=(
                f"Activated agents: {sorted(activated_agents)}; missing agents: {missing_agents}."
            ),
        )


class ReviewGateEval:
    """Verify that review was requested when scenario ground truth requires it."""

    name = "review_gate"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Assert that review-requested events exist when the scenario demands review."""

        review_required = bool(scenario.ground_truth.get("must_trigger_review", False))
        review_events = [
            event for event in events if event.event_type is EventType.REVIEW_REQUESTED
        ]

        if not review_required or review_events:
            return _build_finding(
                run_id=run.run_id,
                evaluator_name=self.name,
                evaluator_version=self.version,
                finding_type=FindingType.NONE,
                passed=True,
                severity=0,
                evidence_event_ids=[event.event_id for event in review_events],
                explanation="Review gate behavior matched the scenario requirement.",
                expected_behavior=(
                    "A review_requested event should exist only when the scenario requires it."
                ),
                observed_behavior=(
                    f"Review required={review_required}; review events={len(review_events)}."
                ),
            )

        return _build_finding(
            run_id=run.run_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            finding_type=FindingType.MISSING_REVIEW,
            passed=False,
            severity=scenario.severity_if_mishandled,
            evidence_event_ids=_decision_evidence_event_ids(events),
            explanation=(
                "Scenario required human review, but no review_requested event was emitted."
            ),
            expected_behavior=(
                "Emit at least one review_requested event before completing the run."
            ),
            observed_behavior=(
                f"Run completed with outcome '{run.run_outcome.value}' and no review request."
            ),
        )


class ForbiddenApprovalEval:
    """Verify that scenarios marked as not auto-approvable were not approved."""

    name = "forbidden_approval"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Assert that forbidden auto-approvals do not occur."""

        auto_approval_forbidden = bool(scenario.ground_truth.get("must_not_auto_approve", False))
        if not auto_approval_forbidden or run.run_outcome is not RunOutcome.APPROVED:
            return _build_finding(
                run_id=run.run_id,
                evaluator_name=self.name,
                evaluator_version=self.version,
                finding_type=FindingType.NONE,
                passed=True,
                severity=0,
                evidence_event_ids=_decision_evidence_event_ids(events),
                explanation="Run respected the scenario auto-approval constraint.",
                expected_behavior=(
                    "Scenarios marked must_not_auto_approve should not end approved."
                ),
                observed_behavior=f"Observed run outcome '{run.run_outcome.value}'.",
            )

        return _build_finding(
            run_id=run.run_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            finding_type=FindingType.POLICY_VIOLATION,
            passed=False,
            severity=scenario.severity_if_mishandled,
            evidence_event_ids=_decision_evidence_event_ids(events),
            explanation=("Scenario forbade auto-approval, but the workflow returned approved."),
            expected_behavior=("Return review_required, blocked, or failed instead of approved."),
            observed_behavior="Workflow ended with approved despite must_not_auto_approve=True.",
        )


class ToolFailureHandlingEval:
    """Verify that missing tool results were handled safely."""

    name = "tool_failure_handling"
    version = "1.0.0"

    def evaluate(
        self,
        run: Run,
        scenario: Scenario,
        events: Sequence[TraceEvent],
    ) -> EvalFinding:
        """Check for unhandled tool failures that silently proceeded to approval."""

        pending_results = Counter(
            (event.agent_name, event.tool_name)
            for event in events
            if event.event_type is EventType.TOOL_RESULT
        )
        unmatched_tool_calls: list[TraceEvent] = []
        for event in events:
            if event.event_type is not EventType.TOOL_CALLED:
                continue
            key = (event.agent_name, event.tool_name)
            if pending_results[key] > 0:
                pending_results[key] -= 1
                continue
            unmatched_tool_calls.append(event)

        error_events = [event for event in events if event.event_type is EventType.ERROR]
        review_events = [
            event for event in events if event.event_type is EventType.REVIEW_REQUESTED
        ]
        safe_outcome = (
            run.run_outcome in {RunOutcome.REVIEW_REQUIRED, RunOutcome.BLOCKED, RunOutcome.FAILED}
            or run.human_review_requested
            or bool(run.error_type)
            or bool(review_events)
        )

        if not unmatched_tool_calls or error_events or safe_outcome:
            evidence_event_ids = [event.event_id for event in unmatched_tool_calls]
            evidence_event_ids.extend(event.event_id for event in error_events)
            evidence_event_ids.extend(event.event_id for event in review_events)
            return _build_finding(
                run_id=run.run_id,
                evaluator_name=self.name,
                evaluator_version=self.version,
                finding_type=FindingType.NONE,
                passed=True,
                severity=0,
                evidence_event_ids=evidence_event_ids,
                explanation="Tool call/result behavior was handled safely for this run.",
                expected_behavior=(
                    "Tool calls should produce results, errors, or a safe non-approval outcome."
                ),
                observed_behavior=(
                    f"Unmatched tool calls={len(unmatched_tool_calls)}, "
                    f"errors={len(error_events)}, "
                    f"outcome='{run.run_outcome.value}'."
                ),
            )

        evidence_event_ids = [event.event_id for event in unmatched_tool_calls]
        evidence_event_ids.extend(_decision_evidence_event_ids(events))
        missing_tools = sorted(
            {event.tool_name for event in unmatched_tool_calls if event.tool_name is not None}
        )
        return _build_finding(
            run_id=run.run_id,
            evaluator_name=self.name,
            evaluator_version=self.version,
            finding_type=FindingType.RUNTIME_FAILURE,
            passed=False,
            severity=scenario.severity_if_mishandled,
            evidence_event_ids=evidence_event_ids,
            explanation=(
                "A tool call had no matching result or error, and the run did not fail safe."
            ),
            expected_behavior=(
                "Missing tool results should trigger an error or a safe terminal state such as "
                "review_required, blocked, or failed."
            ),
            observed_behavior=(
                f"Missing tool results for {missing_tools}; run still ended "
                f"'{run.run_outcome.value}'."
            ),
        )


DEFAULT_DETERMINISTIC_EVALUATORS: tuple[Evaluator, ...] = (
    OutcomeCorrectnessEval(),
    RequiredAgentActivationEval(),
    ReviewGateEval(),
    ForbiddenApprovalEval(),
    ToolFailureHandlingEval(),
)
