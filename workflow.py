"""Bid Workflow — clear execution steps for ITB-23-014-JW.

This module defines the sequential steps the BidExecutor follows.
Each step produces a deliverable and gates to the next.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

log = logging.getLogger(__name__)


StepStatus = Literal["pending", "in_progress", "completed", "failed", "skipped"]


@dataclass
class WorkflowStep:
    """A single step in the bid workflow."""
    step_id: str
    name: str
    description: str
    status: StepStatus = "pending"
    deliverable: str | None = None
    output_file: str | None = None
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class BidWorkflow:
    """Complete workflow for a bid response."""
    bid_id: str
    bid_title: str
    deadline: str
    steps: list[WorkflowStep] = field(default_factory=list)
    current_step: int = 0

    def __post_init__(self):
        self.steps = self._default_steps()

    def _default_steps(self) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                step_id="1_compliance_audit",
                name="Compliance Audit",
                description="Check all fail-points: attachments, references, registrations, signatures",
            ),
            WorkflowStep(
                step_id="2_document_collection",
                name="Document Collection",
                description="Gather all required forms: W-9, FM-3921, FM-7594, cr2e007, Coercion Affidavit, Vallejo license",
            ),
            WorkflowStep(
                step_id="3_reference_validation",
                name="Reference Validation",
                description="Replace First Republic Bank reference with live K-12/government reference",
            ),
            WorkflowStep(
                step_id="4_technical_enhancement",
                name="Technical Proposal Enhancement",
                description="Enhance: name Umbraco version, add WCAG 2.1 AA, clarify US-based team, add FERPA/COPPA/SOC2",
            ),
            WorkflowStep(
                step_id="5_subcontractor_review",
                name="Subcontractor Review",
                description="Verify Ikomet disclosure, FL 287.138 compliance, data residency commitments",
            ),
            WorkflowStep(
                step_id="6_registration_check",
                name="Registration Check",
                description="Verify FL foreign corp registration (Sunbiz), file CR2E007 if missing",
            ),
            WorkflowStep(
                step_id="7_assembly",
                name="Submission Assembly",
                description="Package all documents with consistent subcontractor declarations",
            ),
            WorkflowStep(
                step_id="8_final_verify",
                name="Final Responsiveness Verification",
                description="Double-check all attachments, signatures, dates, consistency across all forms",
            ),
            WorkflowStep(
                step_id="9_submission",
                name="Submit Bid",
                description="Upload to procurement portal before deadline",
            ),
        ]

    def get_current_step(self) -> WorkflowStep | None:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def complete_step(self, deliverable: str, output_file: str | None = None):
        step = self.get_current_step()
        if step:
            step.status = "completed"
            step.deliverable = deliverable
            step.output_file = output_file
            step.completed_at = datetime.now()
            self.current_step += 1
            log.info("[workflow] completed step: %s", step.step_id)

    def fail_step(self, error: str):
        step = self.get_current_step()
        if step:
            step.status = "failed"
            step.error = error
            log.error("[workflow] failed step: %s - %s", step.step_id, error)

    def can_proceed(self) -> bool:
        return self.current_step < len(self.steps)

    def summary(self) -> str:
        completed = sum(1 for s in self.steps if s.status == "completed")
        total = len(self.steps)
        return f"Workflow progress: {completed}/{total} steps completed"