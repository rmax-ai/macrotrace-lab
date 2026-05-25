"""Specialist agents for the reference workflow."""

from __future__ import annotations

from dataclasses import dataclass, field

from macrotrace.exceptions import ToolFailureError
from macrotrace.runtime.tools import SimulatedToolset

WorkflowConfig = dict[str, object]
AgentPayload = dict[str, object]


@dataclass(frozen=True)
class AgentContext:
    """Shared workflow state provided to each agent."""

    scenario_id: str
    request: dict[str, object]
    workflow_config: WorkflowConfig
    tools: SimulatedToolset
    results: dict[str, AgentPayload] = field(default_factory=dict)


class BaseAgent:
    """Base class shared by all deterministic agents."""

    name = "base"

    def run(self, context: AgentContext) -> AgentPayload:
        """Execute the agent against the provided workflow context."""

        raise NotImplementedError

    def _fault_enabled(self, context: AgentContext, fault_name: str) -> bool:
        """Return whether a named fault is enabled."""

        return bool(context.workflow_config.get(fault_name, False))

    def _agent_output(
        self,
        *,
        decision: str,
        findings: list[str],
        next_steps: list[str],
        tools_used: list[dict[str, object]],
        extra: dict[str, object] | None = None,
    ) -> AgentPayload:
        """Build a structured agent response payload."""

        payload: AgentPayload = {
            "agent_name": self.name,
            "decision": decision,
            "findings": findings,
            "next_steps": next_steps,
            "tools_used": tools_used,
        }
        if extra is not None:
            payload.update(extra)
        return payload


class CoordinatorAgent(BaseAgent):
    """Route the request to the required specialist agents."""

    name = "coordinator"

    def run(self, context: AgentContext) -> AgentPayload:
        """Determine which specialists must review the request."""

        request = context.request
        vendor = str(request.get("vendor", ""))
        data_description = str(request.get("data_description", ""))
        quoted_monthly_cost = float(request.get("quoted_monthly_cost", 0.0))
        vendor_known = bool(request.get("vendor_known", False))
        activates_security = bool(data_description) or not vendor_known

        if self._fault_enabled(context, "coordinator_direct_to_procurement"):
            specialists = ["procurement"]
            rationale = "Fault injected direct routing to procurement."
        else:
            specialists = ["budget", "policy"]
            if activates_security:
                specialists.append("security")
            rationale = "Security review required due to data access or unknown vendor."

            if (
                not vendor_known
                and self._fault_enabled(context, "skip_security_on_unknown_vendor")
                and "security" in specialists
            ):
                specialists.remove("security")
                rationale = "Fault skipped security review for unknown vendor."

            if (
                quoted_monthly_cost <= 500.0
                and self._fault_enabled(context, "coordinator_skip_security_on_low_cost")
                and "security" in specialists
            ):
                specialists.remove("security")
                rationale = "Fault skipped security review for a low-cost request."

        findings = [f"Request routed for vendor={vendor or 'unknown'}."]
        next_steps = [f"Activate specialists: {', '.join(specialists)}."]
        return self._agent_output(
            decision="route",
            findings=findings,
            next_steps=next_steps,
            tools_used=[],
            extra={
                "activated_agents": specialists,
                "routing_rationale": rationale,
            },
        )


class BudgetAgent(BaseAgent):
    """Evaluate budget availability and spend thresholds."""

    name = "budget"

    def run(self, context: AgentContext) -> AgentPayload:
        """Check budget availability for the purchase request."""

        request = context.request
        department = str(request["department"])
        item = str(request["item"])
        vendor = str(request["vendor"])
        budget = context.tools.get_budget(department)
        estimate = context.tools.estimate_cost(item, vendor)

        annual_cost = float(request.get("quoted_annual_cost", estimate["estimated_annual_cost"]))
        if self._fault_enabled(context, "budget_agent_ignore_annualized_cost"):
            evaluated_cost = float(
                request.get("quoted_monthly_cost", estimate["estimated_monthly_cost"])
            )
            findings = ["Fault ignored the annualized spend impact."]
        else:
            evaluated_cost = annual_cost
            findings = ["Annualized spend impact evaluated against department budget."]

        remaining = float(budget["remaining"])
        decision = "clear"
        next_steps = ["Forward budget assessment to procurement."]
        if evaluated_cost > remaining:
            decision = "review_required"
            findings.append("Requested spend exceeds remaining budget.")
            next_steps = ["Escalate to budget owner."]

        return self._agent_output(
            decision=decision,
            findings=findings,
            next_steps=next_steps,
            tools_used=[
                {"tool_name": "get_budget", "result": budget},
                {"tool_name": "estimate_cost", "result": estimate},
            ],
            extra={
                "budget": budget,
                "estimate": estimate,
                "evaluated_cost": evaluated_cost,
            },
        )


class SecurityAgent(BaseAgent):
    """Assess data sensitivity and vendor risk."""

    name = "security"

    def run(self, context: AgentContext) -> AgentPayload:
        """Review the request for security and data handling risk."""

        request = context.request
        data_description = str(request.get("data_description", ""))
        vendor = str(request["vendor"])
        classification = context.tools.classify_data(data_description)
        tools_used: list[dict[str, object]] = [
            {"tool_name": "classify_data", "result": classification},
        ]

        try:
            vendor_risk = context.tools.lookup_vendor_risk(vendor)
        except ToolFailureError as exc:
            findings = [str(exc), "Vendor risk could not be verified automatically."]
            return self._agent_output(
                decision="review_required",
                findings=findings,
                next_steps=["Request manual security validation."],
                tools_used=tools_used,
                extra={
                    "data_classification": classification,
                    "vendor_risk": {"risk_level": "unknown", "known_issues": []},
                },
            )

        tools_used.append({"tool_name": "lookup_vendor_risk", "result": vendor_risk})
        data_classification = str(classification["data_classification"])
        risk_level = str(vendor_risk["risk_level"])

        if self._fault_enabled(context, "security_agent_skip_escalation"):
            decision = "clear"
            findings = ["Fault suppressed escalation despite security findings."]
            next_steps = ["Continue procurement without security escalation."]
        elif risk_level == "high":
            decision = "blocked"
            findings = ["High vendor risk blocks automatic approval."]
            next_steps = ["Do not proceed without remediation."]
        elif data_classification in {"confidential", "restricted"} or risk_level == "medium":
            decision = "review_required"
            findings = ["Sensitive data or medium vendor risk requires security review."]
            next_steps = ["Submit for human security review."]
        else:
            decision = "clear"
            findings = ["No blocking security signals detected."]
            next_steps = ["Security review cleared."]

        return self._agent_output(
            decision=decision,
            findings=findings,
            next_steps=next_steps,
            tools_used=tools_used,
            extra={
                "data_classification": classification,
                "vendor_risk": vendor_risk,
            },
        )


class PolicyAgent(BaseAgent):
    """Determine which policy checks and approvals apply."""

    name = "policy"

    def run(self, context: AgentContext) -> AgentPayload:
        """Identify policy requirements for the request."""

        request = context.request
        data_description = str(request.get("data_description", ""))
        quoted_annual_cost = float(request.get("quoted_annual_cost", 0.0))
        topic = "cost review"
        if data_description:
            topic = (
                "restricted data review"
                if "restricted" in data_description.lower()
                else "confidential data review"
            )
        policy = context.tools.retrieve_policy(topic)
        requirements = list(policy["requirements"])

        if quoted_annual_cost >= 20_000 and "budget_owner_approval_required" not in requirements:
            requirements.append("budget_owner_approval_required")

        if self._fault_enabled(context, "policy_agent_omit_review_requirement"):
            requirements = [
                requirement
                for requirement in requirements
                if requirement not in {"security_review_required", "procurement_review_required"}
            ]

        review_required = any(
            requirement in {"security_review_required", "procurement_review_required"}
            for requirement in requirements
        )

        return self._agent_output(
            decision="review_required" if review_required else "clear",
            findings=[f"Applied policy {policy['policy_reference']}."],
            next_steps=["Include policy requirements in the packet."],
            tools_used=[{"tool_name": "retrieve_policy", "result": policy}],
            extra={
                "policy_reference": policy["policy_reference"],
                "requirements": requirements,
            },
        )


class ProcurementAgent(BaseAgent):
    """Prepare a recommendation based on specialist findings."""

    name = "procurement"

    def run(self, context: AgentContext) -> AgentPayload:
        """Produce the procurement recommendation and packet."""

        request = context.request
        specialists = context.results
        security_result = specialists.get("security")
        budget_result = specialists.get("budget")
        policy_result = specialists.get("policy")

        tools_used: list[dict[str, object]] = []
        existing_contract_result = {"vendor": request["vendor"], "contracts": []}
        if not self._fault_enabled(context, "procurement_bypass_existing_tool_check"):
            existing_contract_result = context.tools.lookup_existing_contract(
                str(request["vendor"])
            )
            tools_used.append(
                {
                    "tool_name": "lookup_existing_contract",
                    "result": existing_contract_result,
                }
            )

        packet_request = {
            "scenario_id": context.scenario_id,
            "request": request,
            "budget": budget_result,
            "security": security_result,
            "policy": policy_result,
            "existing_contracts": existing_contract_result["contracts"],
        }
        packet = context.tools.generate_request_packet(packet_request)
        tools_used.append({"tool_name": "generate_request_packet", "result": packet})

        decision = "approve"
        findings = ["Procurement packet assembled."]
        next_steps = ["Send packet to release reviewer."]

        if security_result is not None and security_result["decision"] == "blocked":
            decision = "blocked"
            findings.append("Security block propagated to procurement.")
            next_steps = ["Stop procurement."]
        elif budget_result is not None and budget_result["decision"] == "review_required":
            decision = "review_required"
            findings.append("Budget owner approval required.")
        elif policy_result is not None and policy_result["decision"] == "review_required":
            decision = "review_required"
            findings.append("Policy requires human review.")
        elif existing_contract_result["contracts"]:
            decision = "review_required"
            findings.append("Existing contract should be reviewed before net-new purchase.")

        return self._agent_output(
            decision=decision,
            findings=findings,
            next_steps=next_steps,
            tools_used=tools_used,
            extra={
                "existing_contract_check": existing_contract_result,
                "packet": packet,
            },
        )


class ReleaseReviewerAgent(BaseAgent):
    """Finalize the workflow disposition."""

    name = "release_reviewer"

    def run(self, context: AgentContext) -> AgentPayload:
        """Approve, block, or request human review."""

        procurement_result = context.results["procurement"]
        packet = dict(procurement_result["packet"])
        decision = str(procurement_result["decision"])
        tools_used: list[dict[str, object]] = []

        if decision == "blocked":
            return self._agent_output(
                decision="blocked",
                findings=["Blocking specialist finding preserved at final review."],
                next_steps=["Do not approve the request."],
                tools_used=tools_used,
                extra={"review_submission": None},
            )

        if decision == "review_required" and not self._fault_enabled(
            context, "reviewer_skip_review"
        ):
            submission = context.tools.submit_for_review(packet)
            tools_used.append({"tool_name": "submit_for_review", "result": submission})
            return self._agent_output(
                decision="review_required",
                findings=["Human release review requested."],
                next_steps=["Await manual review outcome."],
                tools_used=tools_used,
                extra={"review_submission": submission},
            )

        return self._agent_output(
            decision="approved",
            findings=["Request cleared for release."],
            next_steps=["Approve and record the disposition."],
            tools_used=tools_used,
            extra={"review_submission": None},
        )
