"""Entry point. Runs once per cron tick.

  python main.py                        # full daily run
  python main.py --dry                  # don't actually send the digest
  python main.py --bid ITB-23-014-JW    # run bid workflow for specific solicitation
  python main.py --status ITB-23-014-JW # check workflow status
"""
from __future__ import annotations
import argparse
import logging
import os
import sys
from datetime import date

import anthropic

import config
from state.db import State
from orchestrator import Orchestrator


def setup_logging():
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Skip sending the digest.")
    parser.add_argument("--task", default=None,
                        help="Override the orchestrator task (default: daily run).")
    parser.add_argument("--bid", default=None,
                        help="Run bid workflow for specific solicitation (e.g., ITB-23-014-JW)")
    parser.add_argument("--status", default=None,
                        help="Check workflow status for a bid")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("main")

    state = State(config.DB_PATH)
    state.seed_compliance(config.COMPLIANCE_ITEMS)
    state.seed_contacts(config.SEED_CONTACTS)

    client = anthropic.Anthropic(api_key=config.secret("ANTHROPIC_API_KEY"))

    if args.bid:
        from workflow import BidWorkflow
        wf = BidWorkflow(
            bid_id=args.bid,
            bid_title="M-DCPS Website Development",
            deadline="2024-09-17"
        )
        log.info("Starting bid workflow for: %s", args.bid)
        from agents.bid_executor import BidExecutorAgent
        executor = BidExecutorAgent(client, state)
        
        while wf.can_proceed():
            step = wf.get_current_step()
            log.info("Step: %s - %s", step.name, step.description)
            
            task = f"Execute: {step.name}. Description: {step.description}. Bid: {args.bid}"
            result = executor.run(task, context={"step": step.step_id, "bid_id": args.bid})
            
            if "error" in result.lower()[:100]:
                log.error("Failed: %s", result[:500])
                break
                
            wf.complete_step(result)
            print(f"✓ {step.name}")
        
        print(f"\nWorkflow complete: {wf.summary()}")
        return

    if args.status:
        from workflow import BidWorkflow
        wf = BidWorkflow(bid_id=args.status, bid_title="", deadline="")
        print(wf.summary())
        return

    orch = Orchestrator(client, state)

    today = date.today().isoformat()
    task = args.task or (
        f"Run today's daily cycle ({today}). Discover new opportunities, "
        f"check compliance, compose the digest, and send it. "
        + ("DRY RUN: do everything except call send_digest." if args.dry else "")
    )

    result = orch.run(task)
    log.info("Orchestrator finished. Summary:\n%s", result)


def run_bid_workflow(bid_id: str, state, client):
    """Run the bid execution workflow for a specific solicitation."""
    from agents.bid_executor import BidExecutorAgent
    from workflow import BidWorkflow

    log = logging.getLogger("bid_workflow")

    workflow = BidWorkflow(
        bid_id=bid_id,
        bid_title="M-DCPS Website Development",
        deadline="2024-09-17"  # TODO: fetch from solicitation
    )

    executor = BidExecutorAgent(client, state)

    while workflow.can_proceed():
        step = workflow.get_current_step()
        log.info("Running step: %s - %s", step.step_id, step.name)

        task = f"""
        Execute step: {step.name}
        Description: {step.description}
        
        Bid ID: {bid_id}
        Current workflow progress: {workflow.summary()}
        
        Provide your analysis and deliverable for this step.
        """

        result = executor.run(task, context={"step": step.step_id, "bid_id": bid_id})

        if "error" in result.lower() or "failed" in result.lower():
            workflow.fail_step(result)
            log.error("Step failed: %s", result)
            break

        workflow.complete_step(result)
        log.info("Step completed: %s", step.name)

    log.info("Workflow complete: %s", workflow.summary())
    return workflow


if __name__ == "__main__":
    main()
