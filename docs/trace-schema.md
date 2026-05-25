# Trace Schema

All runtime adapters produce normalized `TraceEvent` records. This schema is the contract between agent frameworks and the evaluation pipeline.

## Schema Version

Current: `1.0.0`

## Event Types

| `event_type` | Description | Fields |
|---|---|---|
| `workflow_started` | Workflow execution began | agent_name, input_summary |
| `agent_started` | An agent was activated | agent_name, input_summary |
| `agent_response` | An agent produced output | agent_name, output_summary |
| `tool_called` | Agent invoked a function | tool_name, agent_name, input_summary |
| `tool_result` | Tool returned a result | tool_name, agent_name, output_summary |
| `handoff` | Agent transferred to another agent | from_agent, to_agent |
| `guardrail_triggered` | A guardrail policy was evaluated | agent_name, policy_reference, severity |
| `review_requested` | Human review was requested | agent_name |
| `decision` | A final decision was made | agent_name, output_summary |
| `error` | A runtime error occurred | agent_name, tool_name, severity, output_summary |
| `workflow_completed` | Workflow execution finished | agent_name, output_summary |

## Field Reference

```json
{
  "event_id": "evt_001",
  "trace_id": "trace_abc123",
  "run_id": "run_0042",
  "sequence_no": 1,
  "timestamp": "2025-06-01T14:30:00.000Z",
  "event_type": "agent_started",
  "agent_name": "BudgetAgent",
  "tool_name": null,
  "parent_event_id": null,
  "from_agent": null,
  "to_agent": null,
  "input_summary": "check budget for request: purchase API credits",
  "output_summary": null,
  "structured_payload": {},
  "policy_reference": null,
  "severity": null,
  "redacted": false
}
```

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` | Unique event identifier |
| `trace_id` | `str` | Trace this event belongs to |
| `run_id` | `str` | Run this event belongs to |
| `sequence_no` | `int` | Monotonically increasing per trace |
| `timestamp` | `datetime` | ISO 8601 timestamp |
| `event_type` | `EventType` | Typed event category |
| `agent_name` | `str \| None` | Agent that produced this event |
| `tool_name` | `str \| None` | Tool involved (for tool events) |
| `parent_event_id` | `str \| None` | Parent span/event for hierarchy |
| `from_agent` | `str \| None` | Source agent (handoffs) |
| `to_agent` | `str \| None` | Target agent (handoffs) |
| `input_summary` | `str \| None` | Brief input description |
| `output_summary` | `str \| None` | Brief output description |
| `structured_payload` | `dict \| None` | Additional structured data |
| `policy_reference` | `str \| None` | Policy document if guardrail triggered |
| `severity` | `int \| None` | Severity 0-5 for errors/guardrails |
| `redacted` | `bool` | Whether payload was redacted |

## Adapter Implementation

### JSONL Import

```json
{
  "trace_id": "trace_001",
  "run_id": "run_001",
  "events": [
    {
      "event_type": "agent_started",
      "agent_name": "CoordinatorAgent",
      "sequence_no": 1,
      ...
    }
  ]
}
```

### OpenAI Agents SDK

Uses the SDK's custom trace processor to convert `Run` and `Span` events into `TraceEvent` records. See `src/macrotrace/adapters/openai_agents.py`.
