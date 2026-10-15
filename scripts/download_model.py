"""Put a servable model into models/distilbert-sentiment/.

    python -m scripts.download_model                          # public SST-2 DistilBERT (quick start)
    python -m scripts.download_model --hub your-user/distilbert-sentiment
    python -m scripts.download_model --wandb entity/project/distilbert-sentiment:latest

The quick-start checkpoint (distilbert-base-uncased-finetuned-sst-2-english) is a public
DistilBERT fine-tuned on movie-review sentences. It lets the API run immediately; train
your own with `python -m scripts.train` for product reviews and real acceptance numbers.
"""

import argparse
import json
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("download")

QUICKSTART = "distilbert/distilbert-base-uncased-finetuned-sst-2-english"


def from_hub(repo: str, output: Path) -> None:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    log.info("downloading %s from the Hugging Face Hub", repo)
    AutoTokenizer.from_pretrained(repo).save_pretrained(output)
    AutoModelForSequenceClassification.from_pretrained(repo).save_pretrained(output)


def from_wandb(ref: str, output: Path) -> None:
    import wandb

    log.info("downloading W&B artifact %s", ref)
    path = wandb.Api().artifact(ref, type="model").download()
    shutil.copytree(path, output, dirs_exist_ok=True)


def build_reference(output: Path, samples: int) -> None:
    """Score a held-out sample so the drift monitor has a baseline for this checkpoint."""
    import numpy as np
    from datasets import load_dataset
    from transformers import pipeline

    from scripts.train import _text_column, write_reference

    log.info("building drift reference from %d amazon_polarity test reviews", samples)
    # Streamed, so only the sampled rows are fetched rather than the full ~700 MB dataset.
    ds = load_dataset("fancyzhx/amazon_polarity", split="test", streaming=True)
    texts = [_text_column(ex) for ex in ds.shuffle(seed=0, buffer_size=10_000).take(samples)]
    clf = pipeline("text-classification", model=str(output), top_k=None, truncation=True, max_length=256)
    probs = []
    for row in clf(texts, batch_size=32):
        by_label = {r["label"].upper(): r["score"] for r in row}
        probs.append(
            [
                by_label.get("NEGATIVE", by_label.get("LABEL_0")),
                by_label.get("POSITIVE", by_label.get("LABEL_1")),
            ]
        )
    write_reference(output, texts, np.array(probs))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--hub", default=None, help="Hugging Face Hub repo id")
    src.add_argument("--wandb", default=None, help="W&B artifact reference")
    p.add_argument("--output", default="models/distilbert-sentiment")
    p.add_argument(
        "--reference_samples",
        type=int,
        default=1000,
        help="reviews scored to build the drift baseline (0 to skip)",
    )
    args = p.parse_args(argv)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.wandb:
        from_wandb(args.wandb, output)
    else:
        from_hub(args.hub or QUICKSTART, output)

    if args.reference_samples and not (output / "reference_stats.json").exists():
        try:
            build_reference(output, args.reference_samples)
        except Exception as exc:  # noqa: BLE001 - the model is usable without a drift baseline
            log.warning("could not build drift reference (%s); drift scores will be disabled", exc)

    metrics = output / "metrics.json"
    if metrics.exists():
        log.info("checkpoint metrics: %s", json.loads(metrics.read_text()).get("test_metrics"))
    log.info("model ready in %s", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
