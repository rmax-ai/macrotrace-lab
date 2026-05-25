"""Reference workflow orchestration for research procurement review."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from macrotrace.runtime.agents import (
    AgentContext,
    BudgetAgent,
    CoordinatorAgent,
    PolicyAgent,
    ProcurementAgent,
    ReleaseReviewerAgent,
    SecurityAgent,
)
from macrotrace.runtime.fault_injection import apply_faults
from macrotrace.runtime.tools import SimulatedToolset, ToolSeedConfig
from macrotrace.schemas import EventType, RunOutcome, Scenario, TraceEvent


@dataclass(frozen=True)
class WorkflowResult:
    """Structured outcome returned by the reference workflow."""

    workflow_id: str
    trace_events: list[dict[str, object]]
    outcome: RunOutcome
    final_decision: str


class TraceBuilder:
    """Build normalized trace events with deterministic identifiers."""

    def __init__(self, *, run_id: str, trace_id: str, base_timestamp: datetime) -> None:
        self._run_id = run_id
        self._trace_id = trace_id
        self._base_timestamp = base_timestamp
        self._sequence_no = 0
        self._events: list[TraceEvent] = []

    def add(
        self,
        *,
        event_type: EventType,
        agent_name: str | None,
        tool_name: str | None,
        structured_payload: dict[str, object],
        input_summary: str | None = None,
        output_summary: str | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        policy_reference: str | None = None,
        severity: int = 1,
    ) -> None:
        """Append a normalized trace event."""

        self._sequence_no += 1
        event_id = f"{self._trace_id}-event-{self._sequence_no:03d}"
        event = TraceEvent(
            event_id=event_id,
            trace_id=self._trace_id,
            run_id=self._run_id,
            sequence_no=self._sequence_no,
            timestamp=self._base_timestamp,
            event_type=event_type,
            agent_name=agent_name,
            tool_name=tool_name,
            parent_event_id=None,
            from_agent=from_agent,
            to_agent=to_agent,
            input_summary=input_summary,
            output_summary=output_summary,
            structured_payload=structured_payload,
            policy_reference=policy_reference,
            severity=severity,
            redacted=False,
        )
        self._events.append(event)

    def as_dicts(self) -> list[dict[str, object]]:
        """Return the trace events serialized as dictionaries."""

        return [cast(dict[str, object], event.model_dump(mode="json")) for event in self._events]


def _workflow_identifier(seed: int, scenario: Scenario) -> str:
    """Return a deterministic workflow identifier."""

    digest = hashlib.sha256(f"{seed}|{scenario.scenario_id}".encode()).hexdigest()[:12]
    return f"workflow-{digest}"


def _run_specialist(
    *,
    agent_name: str,
    context: AgentContext,
) -> tuple[str, dict[str, object]]:
    """Execute a named specialist and return its structured result."""

    agent_map = {
        "budget": BudgetAgent(),
        "security": SecurityAgent(),
        "policy": PolicyAgent(),
    }
    result = agent_map[agent_name].run(context)
    return agent_name, result


def execute_reference_workflow(
    scenario: Scenario,
    *,
    seed: int,
    workflow_config: dict[str, object] | None = None,
    fault_names: list[str] | None = None,
) -> WorkflowResult:
    """Execute the deterministic reference workflow for one scenario."""

    base_config = dict(workflow_config or {})
    resolved_config = apply_faults(base_config, fault_names or [])
    toolset = SimulatedToolset(
        ToolSeedConfig(
            seed=seed,
            timeout_vendors=tuple(
                str(value) for value in resolved_config.get("timeout_vendors", ())
            ),
        )
    )
    request = {
        "department": scenario.environmental_signals.get("department", "research"),
        "item": scenario.environmental_signals.get("item", "software subscription"),
        "vendor": scenario.environmental_signals.get("vendor", "default vendor"),
        "vendor_known": scenario.environmental_signals.get("vendor_known", False),
        "quoted_monthly_cost": scenario.environmental_signals.get("quoted_monthly_cost", 0.0),
        "quoted_annual_cost": scenario.environmental_signals.get("quoted_annual_cost", 0.0),
        "data_description": scenario.environmental_signals.get("data_description", ""),
        "request_text": scenario.request_text,
    }

    workflow_id = _workflow_identifier(seed, scenario)
    run_id = f"run-{workflow_id}"
    trace_id = f"trace-{workflow_id}"
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    trace = TraceBuilder(run_id=run_id, trace_id=trace_id, base_timestamp=timestamp)
    trace.add(
        event_type=EventType.WORKFLOW_STARTED,
        agent_name=None,
        tool_name=None,
        structured_payload={"scenario_id": scenario.scenario_id, "workflow_id": workflow_id},
        input_summary=scenario.request_text,
        output_summary=None,
        severity=0,
    )

    coordinator_context = AgentContext(
        scenario_id=scenario.scenario_id,
        request=request,
        workflow_config=resolved_config,
        tools=toolset,
        results={},
    )
    trace.add(
        event_type=EventType.AGENT_STARTED,
        agent_name="coordinator",
        tool_name=None,
        structured_payload={"request": request},
        input_summary="Route incoming procurement request.",
        output_summary=None,
    )
    coordinator_result = CoordinatorAgent().run(coordinator_context)
    trace.add(
        event_type=EventType.AGENT_RESPONSE,
        agent_name="coordinator",
        tool_name=None,
        structured_payload=coordinator_result,
        input_summary=None,
        output_summary=str(coordinator_result["decision"]),
    )

    specialist_results: dict[str, dict[str, object]] = {}
    specialist_names = [
        name for name in coordinator_result["activated_agents"] if name != "procurement"
    ]
    if specialist_names:
        with ThreadPoolExecutor(max_workers=len(specialist_names)) as executor:
            futures = {
                name: executor.submit(
                    _run_specialist,
                    agent_name=name,
                    context=AgentContext(
                        scenario_id=scenario.scenario_id,
                        request=request,
                        workflow_config=resolved_config,
                        tools=toolset,
                        results={},
                    ),
                )
                for name in specialist_names
            }
            for agent_name in ("budget", "security", "policy"):
                future = futures.get(agent_name)
                if future is None:
                    continue
                _, result = future.result()
                specialist_results[agent_name] = result
                trace.add(
                    event_type=EventType.HANDOFF,
                    agent_name=None,
                    tool_name=None,
                    structured_payload={"from_agent": "coordinator", "to_agent": agent_name},
                    from_agent="coordinator",
                    to_agent=agent_name,
                    severity=0,
                )
                trace.add(
                    event_type=EventType.AGENT_STARTED,
                    agent_name=agent_name,
                    tool_name=None,
                    structured_payload={"request": request},
                    input_summary="Perform specialist review.",
                    output_summary=None,
                )
                for tool_use in cast(list[dict[str, object]], result["tools_used"]):
                    tool_name = str(tool_use["tool_name"])
                    trace.add(
                        event_type=EventType.TOOL_CALLED,
                        agent_name=agent_name,
                        tool_name=tool_name,
                        structured_payload={"tool_name": tool_name},
                        input_summary=f"{agent_name} called {tool_name}.",
                        output_summary=None,
                    )
                    trace.add(
                        event_type=EventType.TOOL_RESULT,
                        agent_name=agent_name,
                        tool_name=tool_name,
                        structured_payload=cast(dict[str, object], tool_use["result"]),
                        input_summary=None,
                        output_summary=f"{tool_name} returned.",
                    )
                trace.add(
                    event_type=EventType.AGENT_RESPONSE,
                    agent_name=agent_name,
                    tool_name=None,
                    structured_payload=result,
                    input_summary=None,
                    output_summary=str(result["decision"]),
                    policy_reference=cast(str | None, result.get("policy_reference")),
                )

    procurement_context = AgentContext(
        scenario_id=scenario.scenario_id,
        request=request,
        workflow_config=resolved_config,
        tools=toolset,
        results=specialist_results,
    )
    trace.add(
        event_type=EventType.HANDOFF,
        agent_name=None,
        tool_name=None,
        structured_payload={"from_agent": "coordinator", "to_agent": "procurement"},
        from_agent="coordinator",
        to_agent="procurement",
        severity=0,
    )
    procurement_result = ProcurementAgent().run(procurement_context)
    trace.add(
        event_type=EventType.AGENT_STARTED,
        agent_name="procurement",
        tool_name=None,
        structured_payload={"request": request, "inputs": specialist_results},
        input_summary="Prepare procurement recommendation.",
        output_summary=None,
    )
    for tool_use in cast(list[dict[str, object]], procurement_result["tools_used"]):
        tool_name = str(tool_use["tool_name"])
        trace.add(
            event_type=EventType.TOOL_CALLED,
            agent_name="procurement",
            tool_name=tool_name,
            structured_payload={"tool_name": tool_name},
            input_summary=f"procurement called {tool_name}.",
            output_summary=None,
        )
        trace.add(
            event_type=EventType.TOOL_RESULT,
            agent_name="procurement",
            tool_name=tool_name,
            structured_payload=cast(dict[str, object], tool_use["result"]),
            input_summary=None,
            output_summary=f"{tool_name} returned.",
        )
    trace.add(
        event_type=EventType.AGENT_RESPONSE,
        agent_name="procurement",
        tool_name=None,
        structured_payload=procurement_result,
        input_summary=None,
        output_summary=str(procurement_result["decision"]),
    )

    reviewer_context = AgentContext(
        scenario_id=scenario.scenario_id,
        request=request,
        workflow_config=resolved_config,
        tools=toolset,
        results={"procurement": procurement_result},
    )
    trace.add(
        event_type=EventType.HANDOFF,
        agent_name=None,
        tool_name=None,
        structured_payload={"from_agent": "procurement", "to_agent": "release_reviewer"},
        from_agent="procurement",
        to_agent="release_reviewer",
        severity=0,
    )
    reviewer_result = ReleaseReviewerAgent().run(reviewer_context)
    trace.add(
        event_type=EventType.AGENT_STARTED,
        agent_name="release_reviewer",
        tool_name=None,
        structured_payload={"procurement_decision": procurement_result["decision"]},
        input_summary="Finalize the request disposition.",
        output_summary=None,
    )
    for tool_use in cast(list[dict[str, object]], reviewer_result["tools_used"]):
        tool_name = str(tool_use["tool_name"])
        trace.add(
            event_type=EventType.TOOL_CALLED,
            agent_name="release_reviewer",
            tool_name=tool_name,
            structured_payload={"tool_name": tool_name},
            input_summary=f"release_reviewer called {tool_name}.",
            output_summary=None,
        )
        trace.add(
            event_type=EventType.TOOL_RESULT,
            agent_name="release_reviewer",
            tool_name=tool_name,
            structured_payload=cast(dict[str, object], tool_use["result"]),
            input_summary=None,
            output_summary=f"{tool_name} returned.",
        )
    trace.add(
        event_type=EventType.AGENT_RESPONSE,
        agent_name="release_reviewer",
        tool_name=None,
        structured_payload=reviewer_result,
        input_summary=None,
        output_summary=str(reviewer_result["decision"]),
    )

    final_decision = str(reviewer_result["decision"])
    outcome = RunOutcome(final_decision)
    final_event_type = (
        EventType.REVIEW_REQUESTED if outcome is RunOutcome.REVIEW_REQUIRED else EventType.DECISION
    )
    trace.add(
        event_type=final_event_type,
        agent_name="release_reviewer",
        tool_name=None,
        structured_payload={"final_decision": final_decision},
        input_summary=None,
        output_summary=final_decision,
    )
    trace.add(
        event_type=EventType.WORKFLOW_COMPLETED,
        agent_name=None,
        tool_name=None,
        structured_payload={"outcome": outcome.value, "final_decision": final_decision},
        input_summary=None,
        output_summary=final_decision,
        severity=0,
    )
    return WorkflowResult(
        workflow_id=workflow_id,
        trace_events=trace.as_dicts(),
        outcome=outcome,
        final_decision=final_decision,
    )
