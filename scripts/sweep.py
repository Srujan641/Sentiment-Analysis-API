"""Create and run the W&B Bayesian sweep defined in sweeps/sweep.yaml.

    python -m scripts.sweep --count 10
    python -m scripts.sweep --sweep_id <existing-id> --count 3     # add another agent

Afterwards, retrain the winning config with the gates enforced and upload it:

    python -m scripts.train --wandb --log_artifact --fp16 --learning_rate ... --batch_size ...
"""

import argparse
import os

import yaml


def main(argv=None) -> int:
    import wandb

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="sweeps/sweep.yaml")
    p.add_argument("--project", default=os.getenv("WANDB_PROJECT", "sentiment-analysis-distilbert"))
    p.add_argument("--entity", default=os.getenv("WANDB_ENTITY"))
    p.add_argument("--sweep_id", default=None)
    p.add_argument("--count", type=int, default=10)
    args = p.parse_args(argv)

    sweep_id = args.sweep_id
    if not sweep_id:
        with open(args.config) as fh:
            config = yaml.safe_load(fh)
        sweep_id = wandb.sweep(config, project=args.project, entity=args.entity)
        print(f"created sweep {sweep_id}")

    from scripts.train import main as train_main

    # The agent sets wandb.config for each run; train.py reads it as overrides.
    wandb.agent(
        sweep_id,
        function=lambda: train_main(["--wandb", "--fp16", "--no_enforce_gates"]),
        project=args.project,
        entity=args.entity,
        count=args.count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
