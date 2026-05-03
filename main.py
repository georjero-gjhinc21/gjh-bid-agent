"""Entry point. Runs once per cron tick.

  python main.py            # full daily run
  python main.py --dry      # don't actually send the digest
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
    args = parser.parse_args()

    setup_logging()
    log = logging.getLogger("main")

    state = State(config.DB_PATH)
    state.seed_compliance(config.COMPLIANCE_ITEMS)
    state.seed_contacts(config.SEED_CONTACTS)

    client = anthropic.Anthropic(api_key=config.secret("ANTHROPIC_API_KEY"))
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
