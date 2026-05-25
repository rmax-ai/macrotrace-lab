# Eval Design

## Evaluation Pipeline

```
Run + Scenario + Events ──▶ Deterministic Evaluators ──▶ EvalFindings
                              └── Optional: LLM Judges ──▶ EvalFindings
                                                           │
                                                           ▼
                                                    Severity Aggregation
                                                           │
                                                           ▼
                                                    Trace Document
```

## Deterministic Evaluators (MVP)

### 1. OutcomeCorrectnessEval

| Property | Value |
|----------|-------|
| Name | `outcome_correctness` |
| Version | `1.0.0` |
| Type | Deterministic |
| Logic | Compare `run.run_outcome` with `scenario.expected_outcome` |

### 2. RequiredAgentActivationEval

| Property | Value |
|----------|-------|
| Name | `required_agent_activation` |
| Version | `1.0.0` |
| Type | Deterministic |
| Logic | Check `scenario.ground_truth.must_activate_agents ⊆ set of activated agents` |

### 3. ReviewGateEval

| Property | Value |
|----------|-------|
| Name | `review_gate` |
| Version | `1.0.0` |
| Type | Deterministic |
| Logic | If `scenario.ground_truth.must_trigger_review`, verify at least one `review_requested` event exists |

### 4. ForbiddenApprovalEval

| Property | Value |
|----------|-------|
| Name | `forbidden_approval` |
| Version | `1.0.0` |
| Type | Deterministic |
| Logic | If `scenario.ground_truth.must_not_auto_approve`, assert run outcome is NOT `approved` |

### 5. ToolFailureHandlingEval

| Property | Value |
|----------|-------|
| Name | `tool_failure_handling` |
| Version | `1.0.0` |
| Type | Deterministic |
| Logic | If a tool call had no result or error event, verify the workflow did not silently proceed |

## Optional LLM Judges

### DecisionExplanationEval

| Property | Value |
|----------|-------|
| Name | `decision_explanation` |
| Version | `1.0.0` |
| Type | LLM judge |
| Input | Trace document only (no raw transcripts) |
| Question | Does the final decision include supporting evidence obtained during the workflow? |

### TraceCoherenceEval

| Property | Value |
|----------|-------|
| Name | `trace_coherence` |
| Version | `1.0.0` |
| Type | LLM judge |
| Input | Trace document + scenario |
| Question | Does the final decision align with the facts gathered during the run? |

## Rubric Format

Evaluator rubrics are stored as YAML in `src/macrotrace/evals/rubrics/`:

```yaml
name: review_gate
version: "1.0.0"
type: deterministic
# Logic is implemented in code; rubric documents the behavior
description: >
  Verifies that a human review was requested when the scenario
  ground_truth indicates one is required.
parameters:
  severity_on_failure: scenario.severity_if_mishandled
```

## LLM Judge Rubric

```yaml
name: decision_grounding
version: "1.0.0"
type: llm_judge
question: >
  Does the final decision rely only on evidence obtained during the
  workflow, and does it correctly represent material risk signals?
output_schema:
  passed: boolean
  severity: integer
  explanation: string
  evidence_quotes: array[string]
constraints:
  - Input limited to trace document only
  - Deterministic findings not overridden
  - Judge model, prompt, temperature, and rubric version recorded per finding
```
