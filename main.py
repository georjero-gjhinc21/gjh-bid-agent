"""Entry point. Runs once per cron tick.

  python main.py                        # full daily run
  python main.py --dry                  # don't actually send the digest
  python main.py --bid ITB-23-014-JW    # run bid workflow for specific solicitation
  python main.py --status ITB-23-014-JW # check workflow status
  python main.py --plan ITB-23-014-JW   # create workflow plan for solicitation
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


MAX_CRITIC_RETRIES = 3


def run_workflow_with_critic(wf, executor, critic, state, log):
    """Execute workflow with critic evaluation and retry loop."""
    from agents.critic import save_critique
    
    while wf.can_proceed():
        step = wf.get_current_step()
        if not step:
            break
            
        step.status = "in_progress"
        log.info("Step: %s - %s", step.name, step.goal)
        
        task = f"Execute step: {step.name}. Goal: {step.goal}. Success criteria: {step.success_criteria}"
        result = executor.run(task, context={
            "step": step.step_id, 
            "bid_id": wf.solicitation_id,
            "step_name": step.name,
            "step_goal": step.goal,
            "success_criteria": step.success_criteria
        })
        
        if "error" in result.lower()[:100]:
            log.error("Step failed: %s", result[:500])
            wf.fail_step(result)
            break
        
        evaluation = critic.evaluate(
            deliverable=result,
            success_criteria=step.success_criteria,
            step_name=step.name,
            step_goal=step.goal
        )
        
        save_critique(wf.workflow_id, step.step_id, evaluation, result)
        
        if critic.should_retry(evaluation) and step.retry_count < MAX_CRITIC_RETRIES:
            log.warning("Critic found issues, retrying step: %s (attempt %d)", step.name, step.retry_count + 1)
            step.retry_count += 1
            step.status = "pending"
            continue
        
        if evaluation.get("verdict") == "FAIL":
            log.error("Step failed critic: %s", evaluation.get("issues", []))
            wf.fail_step(str(evaluation))
            break
        
        wf.complete_step(result)
        log.info("✓ %s (score: %d)", step.name, evaluation.get("score", 100))
    
    log.info("Workflow complete: %s", wf.summary())
    return wf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="Skip sending the digest.")
    parser.add_argument("--task", default=None,
                        help="Override the orchestrator task (default: daily run).")
    parser.add_argument("--bid", default=None,
                        help="Run bid workflow for specific solicitation")
    parser.add_argument("--status", default=None,
                        help="Check workflow status for a bid")
    parser.add_argument("--plan", default=None,
                        help="Create workflow plan for a solicitation")
    parser.add_argument("--solicitation-file", default=None,
                        help="Path to solicitation document")
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("main")

    state = State(config.DB_PATH)
    state.seed_compliance(config.COMPLIANCE_ITEMS)
    state.seed_contacts(config.SEED_CONTACTS)

    client = anthropic.Anthropic(api_key=config.secret("ANTHROPIC_API_KEY"))

    if args.bid:
        from workflow import BidWorkflow, create_default_workflow
        from agents.bid_executor import BidExecutorAgent
        from agents.critic import CriticAgent
        
        wf_path = f"/tmp/workflow_{args.bid}.json"
        
        try:
            wf = BidWorkflow.load(wf_path)
            log.info("Loaded existing workflow from: %s", wf_path)
        except Exception:
            wf = create_default_workflow(args.bid)
            wf.save(wf_path)
            log.info("Created new workflow, saved to: %s", wf_path)
        
        executor = BidExecutorAgent(client, state)
        critic = CriticAgent(client, state)
        
        run_workflow_with_critic(wf, executor, critic, state, log)
        
        wf.save(wf_path)
        print(f"\n{wf.summary()}")
        return

    if args.plan:
        from agents.planner import PlannerAgent
        from workflow import BidWorkflow
        
        planner = PlannerAgent(client, state)
        
        solicitation_content = ""
        if args.solicitation_file:
            solicitation_content = open(args.solicitation_file).read()
        
        task = f"Create a bid response workflow for {args.plan}"
        result = planner.run(task, context={
            "solicitation_id": args.plan,
            "solicitation_content": solicitation_content
        })
        
        try:
            wf = BidWorkflow.from_json(result)
            wf_path = f"/tmp/workflow_{args.plan}.json"
            wf.save(wf_path)
            print(f"Workflow created: {wf.summary()}")
            print(f"Saved to: {wf_path}")
        except Exception as e:
            print(f"Could not parse as workflow JSON: {e}")
            print("Raw result:", result[:500])
        return

    if args.status:
        from workflow import BidWorkflow
        wf_path = f"/tmp/workflow_{args.status}.json"
        try:
            wf = BidWorkflow.load(wf_path)
            print(wf.summary())
            print("\nSteps:")
            for s in wf.steps:
                print(f"  [{s.status}] {s.step_id}: {s.name}")
        except Exception as e:
            print(f"Workflow not found: {e}")
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


if __name__ == "__main__":
    main()