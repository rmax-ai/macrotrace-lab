"""Deterministic simulated tools for the reference workflow."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from macrotrace.exceptions import ToolFailureError


def _normalize_name(value: str) -> str:
    """Normalize a free-form lookup key."""

    return " ".join(value.strip().lower().split())


@dataclass(frozen=True)
class ToolSeedConfig:
    """Seeded configuration for deterministic tool behavior."""

    seed: int
    timeout_vendors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimulatedToolset:
    """Collection of deterministic tool implementations."""

    config: ToolSeedConfig = field(default_factory=lambda: ToolSeedConfig(seed=0))

    def _digest(self, *parts: str) -> str:
        """Return a stable digest for the provided inputs."""

        joined = "|".join((str(self.config.seed), *parts))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def _number(self, minimum: int, maximum: int, *parts: str) -> int:
        """Return a deterministic integer within the provided range."""

        span = (maximum - minimum) + 1
        digest_prefix = self._digest(*parts)[:8]
        return minimum + (int(digest_prefix, 16) % span)

    def get_budget(self, department: str) -> dict[str, object]:
        """Return allocated, spent, and remaining budget for a department."""

        normalized_department = _normalize_name(department)
        allocated = self._number(120_000, 250_000, "budget", normalized_department)
        spent_ratio = self._number(35, 82, "spent-ratio", normalized_department)
        spent = round(allocated * spent_ratio / 100, 2)
        remaining = round(allocated - spent, 2)
        return {
            "department": department,
            "allocated": float(allocated),
            "spent": spent,
            "remaining": remaining,
        }

    def estimate_cost(self, item: str, vendor: str) -> dict[str, object]:
        """Return deterministic monthly and annual cost estimates."""

        normalized_item = _normalize_name(item)
        normalized_vendor = _normalize_name(vendor)
        monthly_cost = float(self._number(150, 4_500, "cost", normalized_item, normalized_vendor))
        annual_cost = round(monthly_cost * 12, 2)
        return {
            "item": item,
            "vendor": vendor,
            "estimated_monthly_cost": monthly_cost,
            "estimated_annual_cost": annual_cost,
        }

    def classify_data(self, description: str) -> dict[str, object]:
        """Classify the data described in a request."""

        normalized_description = _normalize_name(description)
        keywords = {
            "restricted": ("phi", "hipaa", "ssn", "passport", "genomic", "restricted"),
            "confidential": ("customer", "employee", "finance", "confidential", "student"),
            "internal": ("internal", "team", "roadmap", "ops"),
        }
        classification = "public"
        rationale = "No sensitive keywords detected."
        for candidate, terms in keywords.items():
            if any(term in normalized_description for term in terms):
                classification = candidate
                rationale = f"Matched sensitive keyword set for {candidate} data."
                break
        return {
            "data_classification": classification,
            "rationale": rationale,
        }

    def lookup_vendor_risk(self, vendor_name: str) -> dict[str, object]:
        """Return deterministic vendor risk information."""

        normalized_vendor = _normalize_name(vendor_name)
        if normalized_vendor in {_normalize_name(vendor) for vendor in self.config.timeout_vendors}:
            raise ToolFailureError(f"lookup_vendor_risk timed out for vendor={vendor_name}")

        if "highrisk" in normalized_vendor or "breach" in normalized_vendor:
            risk_level = "high"
            issues = ["Recent security incident", "Open corrective action plan"]
        elif "sensitive" in normalized_vendor or "unknown" in normalized_vendor:
            risk_level = "medium"
            issues = ["Security questionnaire incomplete"]
        else:
            risk_level = "low"
            issues = []

        return {
            "vendor_name": vendor_name,
            "risk_level": risk_level,
            "known_issues": issues,
        }

    def retrieve_policy(self, topic: str) -> dict[str, object]:
        """Return policy requirements for a review topic."""

        normalized_topic = _normalize_name(topic)
        if "restricted" in normalized_topic or "confidential" in normalized_topic:
            reference = "POL-SEC-200"
            requirements = [
                "security_review_required",
                "procurement_review_required",
                "manager_approval_required",
            ]
        elif "cost" in normalized_topic or "budget" in normalized_topic:
            reference = "POL-FIN-110"
            requirements = ["budget_owner_approval_required"]
        else:
            reference = "POL-PROC-001"
            requirements = ["procurement_review_required"]

        return {
            "topic": topic,
            "policy_reference": reference,
            "requirements": requirements,
        }

    def lookup_existing_contract(self, vendor: str) -> dict[str, object]:
        """Return deterministic contract information for a vendor."""

        normalized_vendor = _normalize_name(vendor)
        if "contract" in normalized_vendor or "enterprise" in normalized_vendor:
            contracts: list[dict[str, object]] = [
                {
                    "contract_id": f"CTR-{self._number(1000, 9999, 'contract', normalized_vendor)}",
                    "status": "active",
                    "notes": "Existing enterprise agreement available.",
                }
            ]
        else:
            contracts = []
        return {
            "vendor": vendor,
            "contracts": contracts,
        }

    def generate_request_packet(self, request: dict[str, object]) -> dict[str, object]:
        """Return a deterministic purchase request packet."""

        digest = self._digest("packet", str(sorted(request.items())))[:10]
        return {
            "packet_id": f"PKT-{digest}",
            "request": request,
            "status": "draft",
        }

    def submit_for_review(self, packet: dict[str, object]) -> dict[str, object]:
        """Return a deterministic review submission result."""

        packet_id = str(packet["packet_id"])
        digest = self._digest("review", packet_id)[:8].upper()
        return {
            "submitted": True,
            "review_ticket_id": f"REV-{digest}",
        }
