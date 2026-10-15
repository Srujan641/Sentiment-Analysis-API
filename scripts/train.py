"""Fine-tune DistilBERT for binary product-review sentiment.

    python -m scripts.train                                  # amazon_polarity, sensible defaults
    python -m scripts.train --wandb --wandb_project sentiment-analysis-distilbert
    python -m scripts.train --data_file reviews.csv          # your own CSV (text,label)

Splits: train and validation are carved disjointly from the training split; the test set
comes from the dataset's own test split and is evaluated exactly once, at the end.
A checkpoint is only written to --output if it clears all three acceptance gates
(unless --no_enforce_gates is passed).

Under a W&B sweep agent, hyperparameters from `wandb.config` override the CLI defaults.

Safety (see scripts/training_guard.py): GPU-only by default, validation + checkpoint every
--eval_steps, automatic stop on overfitting or divergence, best checkpoint kept, resumable
with --resume, and the final model is swapped into --output atomically.
"""

import argparse
import json
import logging
import os
import random
import shutil
from pathlib import Path

# Unsupported GPU ops must fail loudly, never run silently on the CPU. Set before torch loads.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "0")
# Hard cap on Apple-GPU memory, as a fraction of torch.mps.recommended_max_memory()
# (~12.7 GB on a 16 GB Mac -> ~7 GB), so the allocator can never push the OS into swap.
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.55")
# The allocator starts releasing cached blocks above the low mark (must be <= the high mark).
os.environ.setdefault("PYTORCH_MPS_LOW_WATERMARK_RATIO", "0.45")

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("train")

GATES = {"accuracy": 0.92, "f1_macro": 0.91, "roc_auc": 0.95}
LABELS = {0: "NEGATIVE", 1: "POSITIVE"}
CONFIDENCE_EDGES = [0.6, 0.7, 0.8, 0.9, 0.95, 0.99]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # data
    p.add_argument("--dataset", default="fancyzhx/amazon_polarity", help="HF dataset id")
    p.add_argument("--data_file", default=None, help="CSV with `text,label` (label 0/1) instead of --dataset")
    p.add_argument("--train_samples", type=int, default=60000)
    p.add_argument("--val_samples", type=int, default=5000)
    p.add_argument("--test_samples", type=int, default=10000)
    # model / optimisation
    p.add_argument("--base_model", default="distilbert-base-uncased")
    p.add_argument("--max_length", type=int, default=256)
    p.add_argument("--learning_rate", type=float, default=3e-5)
    p.add_argument("--batch_size", type=int, default=32, help="per-step batch on the device")
    p.add_argument(
        "--grad_accum", type=int, default=1, help="effective batch = batch_size * grad_accum (saves memory)"
    )
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--warmup_ratio", type=float, default=0.1)
    p.add_argument("--weight_decay", type=float, default=0.01)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--fp16", action="store_true", help="mixed precision (use on a CUDA GPU, e.g. Colab T4)")
    p.add_argument(
        "--device",
        default="auto",
        choices=["auto", "mps", "cuda", "cpu"],
        help="auto = the available GPU (MPS or CUDA); never falls back to CPU unless 'cpu' is explicit",
    )
    # safety
    p.add_argument("--eval_steps", type=int, default=250, help="validate + checkpoint every N steps")
    p.add_argument("--logging_steps", type=int, default=50)
    p.add_argument("--patience", type=int, default=2, help="evals without val-loss improvement before stop")
    p.add_argument(
        "--spike_tolerance", type=float, default=0.05, help="stop at once if val loss > best*(1+x)"
    )
    p.add_argument("--save_total_limit", type=int, default=3, help="checkpoints kept (best is always kept)")
    p.add_argument("--run_name", default="distilbert-amazon")
    p.add_argument("--resume", action="store_true", help="resume from the latest checkpoint of --run_name")
    # output / tracking
    p.add_argument("--output", default="models/distilbert-sentiment")
    p.add_argument("--work_dir", default="runs")
    p.add_argument("--wandb", action="store_true", help="log to Weights & Biases")
    p.add_argument("--wandb_project", default=os.getenv("WANDB_PROJECT", "sentiment-analysis-distilbert"))
    p.add_argument("--log_artifact", action="store_true", help="upload the final model as a W&B artifact")
    p.add_argument("--no_enforce_gates", action="store_true", help="save the model even if gates fail")
    return p.parse_args(argv)


# ---------------------------------------------------------------- data
def _text_column(example: dict) -> str:
    if "content" in example:  # amazon_polarity: title + content
        title = (example.get("title") or "").strip()
        body = (example.get("content") or "").strip()
        return f"{title}. {body}" if title else body
    return example["text"]


def load_splits(args):
    from datasets import Dataset, load_dataset

    if args.data_file:
        import pandas as pd

        df = pd.read_csv(args.data_file)[["text", "label"]].dropna()
        df = df.sample(frac=1, random_state=args.seed).reset_index(drop=True)
        n_test = min(args.test_samples, len(df) // 5)
        test_df, rest = df.iloc[:n_test], df.iloc[n_test:]
        full_train = Dataset.from_pandas(rest, preserve_index=False)
        test = Dataset.from_pandas(test_df, preserve_index=False)
    else:
        raw = load_dataset(args.dataset)
        full_train, test = raw["train"], raw["test"]

    def normalise(ds, n):
        ds = ds.shuffle(seed=args.seed).select(range(min(n, len(ds))))
        return ds.map(
            lambda ex: {"text": _text_column(ex), "label": int(ex["label"])},
            remove_columns=[c for c in ds.column_names if c not in ("label",)],
        )

    pool = normalise(full_train, args.train_samples + args.val_samples)
    split = pool.train_test_split(test_size=min(args.val_samples, len(pool) // 10), seed=args.seed)
    train, val = split["train"], split["test"]
    test = normalise(test, args.test_samples)

    # Leakage guard: drop training rows whose exact text appears in validation or test.
    held_out = set(val["text"]) | set(test["text"])
    before = len(train)
    train = train.filter(lambda ex: ex["text"] not in held_out)
    if before != len(train):
        log.info("removed %d train rows duplicated in val/test", before - len(train))

    for name, ds in (("train", train), ("val", val), ("test", test)):
        pos = sum(ds["label"]) / len(ds)
        log.info("%-5s n=%-6d positive=%.3f", name, len(ds), pos)
        if not 0.3 <= pos <= 0.7:
            log.warning("%s split is imbalanced (positive=%.2f); watch F1 macro, not accuracy", name, pos)
    return train, val, test


# ---------------------------------------------------------------- metrics
def compute_metrics(eval_pred):
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    logits, labels = eval_pred
    logits = np.asarray(logits)
    probs = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs /= probs.sum(axis=1, keepdims=True)
    preds = probs.argmax(axis=1)
    return {
        "accuracy": accuracy_score(labels, preds),
        "f1_macro": f1_score(labels, preds, average="macro"),
        "roc_auc": roc_auc_score(labels, probs[:, 1]),
    }


def reference_stats(texts: list[str], probs: np.ndarray) -> dict:
    """Distribution snapshot the serving layer's drift monitor compares live traffic against."""
    lengths = np.array([len(t) for t in texts])
    length_edges = sorted(set(np.quantile(lengths, np.linspace(0.1, 0.9, 9)).round().astype(int).tolist()))
    conf = probs.max(axis=1)

    def freqs(values, edges):
        idx = np.searchsorted(edges, values, side="right")
        counts = np.bincount(idx, minlength=len(edges) + 1)
        return (counts / counts.sum()).round(6).tolist()

    return {
        "n": len(texts),
        "positive_rate": float((probs.argmax(axis=1) == 1).mean()),
        "text_length": {"edges": length_edges, "freqs": freqs(lengths, length_edges)},
        "confidence": {"edges": CONFIDENCE_EDGES, "freqs": freqs(conf, CONFIDENCE_EDGES)},
    }


def write_reference(output: Path, texts: list[str], probs: np.ndarray) -> None:
    import pandas as pd

    (output / "reference_stats.json").write_text(json.dumps(reference_stats(texts, probs), indent=2))
    sample = pd.DataFrame(
        {
            "text_length": [len(t) for t in texts],
            "word_count": [len(t.split()) for t in texts],
            "confidence": probs.max(axis=1),
            "label": [LABELS[i] for i in probs.argmax(axis=1)],
        }
    )
    sample.to_csv(output / "reference_sample.csv", index=False)


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    args = parse_args(argv)

    run = None
    if args.wandb or os.getenv("WANDB_SWEEP_ID"):
        import wandb

        run = wandb.init(project=args.wandb_project, config=vars(args), job_type="train")
        for key, value in dict(wandb.config).items():  # sweep overrides
            if hasattr(args, key):
                setattr(args, key, value)
    else:
        os.environ["WANDB_DISABLED"] = "true"

    from scripts.training_guard import (
        DeviceGuardCallback,
        MemoryGuardCallback,
        OverfitGuardCallback,
        lock_accelerator,
        plot_curve,
    )

    device = args.device
    if device == "auto":
        import torch

        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else None
        if device is None:
            log.error("no GPU found; pass --device cpu explicitly to train on the CPU")
            return 3
    lock_accelerator(device)

    import torch
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
        set_seed,
    )
    from transformers.trainer_utils import get_last_checkpoint

    set_seed(args.seed)
    random.seed(args.seed)

    train, val, test = load_splits(args)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=args.max_length)

    train_tok = train.map(tokenize, batched=True, remove_columns=["text"])
    val_tok = val.map(tokenize, batched=True, remove_columns=["text"])
    test_tok = test.map(tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=2,
        id2label=LABELS,
        label2id={v: k for k, v in LABELS.items()},
        ignore_mismatched_sizes=True,
    )

    steps_per_epoch = max(len(train_tok) // (args.batch_size * args.grad_accum), 1)
    warmup_steps = int(steps_per_epoch * args.epochs * args.warmup_ratio)
    run_dir = Path(args.work_dir) / (run.id if run else args.run_name)
    total_steps = steps_per_epoch * args.epochs
    log.info(
        "plan: %d train rows, %d steps/epoch, %d total steps, validate+checkpoint every %d steps on %s",
        len(train_tok),
        steps_per_epoch,
        total_steps,
        args.eval_steps,
        device,
    )

    training_args = TrainingArguments(
        output_dir=str(run_dir),
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        per_device_eval_batch_size=args.batch_size * 2,
        num_train_epochs=args.epochs,
        weight_decay=args.weight_decay,  # AdamW, decoupled weight decay
        warmup_steps=warmup_steps,  # linear warmup, then linear decay
        lr_scheduler_type="linear",
        max_grad_norm=1.0,  # gradient clipping guards against loss spikes
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=args.eval_steps,  # a checkpoint at every validation
        save_total_limit=args.save_total_limit,
        load_best_model_at_end=True,  # final weights = best checkpoint, not the last one
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_steps=args.logging_steps,
        use_cpu=device == "cpu",
        dataloader_pin_memory=device == "cuda",
        fp16=args.fp16 and device == "cuda",
        report_to=["wandb"] if run else [],
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=val_tok,
        processing_class=tokenizer,
        # Padding to a multiple of 32 tokens limits the number of distinct tensor shapes.
        data_collator=DataCollatorWithPadding(tokenizer, pad_to_multiple_of=32),
        compute_metrics=compute_metrics,
        callbacks=[
            DeviceGuardCallback(device),
            MemoryGuardCallback(device),
            guard := OverfitGuardCallback(
                run_dir / "learning_curve.csv",
                patience=args.patience,
                spike_tolerance=args.spike_tolerance,
            ),
        ],
    )

    # DistilBERT's forward() takes **kwargs, so the Trainer assumes the model normalises the loss
    # across gradient-accumulation steps itself; it does not. Without this, loss and gradients
    # are summed over micro-batches (2x with --grad_accum 2) instead of averaged.
    trainer.model_accepts_loss_kwargs = False

    resume = None
    if args.resume:
        resume = get_last_checkpoint(str(run_dir)) if run_dir.exists() else None
        log.info("resuming from %s", resume or "scratch (no checkpoint found)")
    trainer.train(resume_from_checkpoint=resume)
    log.info("best checkpoint: %s", trainer.state.best_model_checkpoint)
    curve_png = run_dir / "learning_curve.png"
    plot_curve(run_dir / "learning_curve.csv", curve_png)

    # The one and only look at the test set.
    out = trainer.predict(test_tok, metric_key_prefix="test")
    test_metrics = {
        k.removeprefix("test_"): float(v) for k, v in out.metrics.items() if k.removeprefix("test_") in GATES
    }
    gates = {name: test_metrics[name] >= bar for name, bar in GATES.items()}
    passed = all(gates.values())

    log.info(
        "TEST  "
        + "  ".join(
            f"{k}={v:.4f} (gate {GATES[k]:.2f} {'PASS' if gates[k] else 'FAIL'})"
            for k, v in test_metrics.items()
        )
    )
    if run:
        run.summary.update({f"test/{k}": v for k, v in test_metrics.items()} | {"gates_passed": passed})

    report = {
        "test_metrics": test_metrics,
        "gates": GATES,
        "gates_passed": passed,
        "dataset": args.data_file or args.dataset,
        "splits": {"train": len(train), "val": len(val), "test": len(test)},
        "hyperparameters": {
            k: getattr(args, k)
            for k in (
                "base_model",
                "learning_rate",
                "batch_size",
                "grad_accum",
                "epochs",
                "warmup_ratio",
                "weight_decay",
                "max_length",
                "seed",
            )
        },
        "training": {
            "device": device,
            "steps_completed": trainer.state.global_step,
            "steps_planned": total_steps,
            "best_checkpoint": trainer.state.best_model_checkpoint,
            "best_val_loss": guard.best_loss,
            "stop_reason": guard.stop_reason or "completed all planned epochs",
        },
        "wandb_run": run.url if run else None,
    }

    if not passed and not args.no_enforce_gates:
        log.error("acceptance gates FAILED; checkpoint not written to %s", args.output)
        (run_dir / "metrics.json").parent.mkdir(parents=True, exist_ok=True)
        (run_dir / "metrics.json").write_text(json.dumps(report, indent=2))
        if run:
            run.finish(exit_code=1)
        return 1

    # Write everything to a temp folder, then swap it in, so --output is never half-written.
    output = Path(args.output)
    staging = output.with_name(output.name + ".tmp")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    trainer.save_model(str(staging))
    tokenizer.save_pretrained(str(staging))
    (staging / "metrics.json").write_text(json.dumps(report, indent=2))

    logits = np.asarray(out.predictions)
    probs = np.exp(logits - logits.max(axis=1, keepdims=True))
    probs /= probs.sum(axis=1, keepdims=True)
    write_reference(staging, test["text"], probs)
    shutil.copy(run_dir / "learning_curve.csv", staging)
    if curve_png.exists():
        shutil.copy(curve_png, staging)

    if output.exists():
        previous = output.with_name(output.name + ".previous")
        shutil.rmtree(previous, ignore_errors=True)
        output.rename(previous)
        log.info("previous model kept at %s", previous)
    staging.rename(output)
    log.info("saved model, metrics.json, learning curve and drift reference to %s", output)

    if run:
        if args.log_artifact:
            import wandb

            artifact = wandb.Artifact("distilbert-sentiment", type="model", metadata=report)
            artifact.add_dir(str(output))
            run.log_artifact(artifact, aliases=["latest"] + (["gated"] if passed else []))
        run.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
