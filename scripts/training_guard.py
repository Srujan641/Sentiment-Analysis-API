"""Safety rails for fine-tuning.

1. Accelerator lock: training runs only on the requested GPU (Apple MPS or CUDA). If the
   device is missing, or the model ends up anywhere else, training aborts before step 1.
   With MPS, PYTORCH_ENABLE_MPS_FALLBACK=0 makes unsupported ops raise instead of silently
   running on the CPU.

2. Overfitting guard: validation is run every `eval_steps`. Training stops at once when
     - the loss becomes NaN / inf (diverged), or
     - validation loss jumps more than `spike_tolerance` above its best (sharp overfit), or
     - validation loss fails to improve on its best for `patience` evaluations in a row, or
     - validation F1 macro falls more than `f1_tolerance` below its best.
   Because the Trainer is configured with load_best_model_at_end, the weights that are kept
   are the best checkpoint, never the over-trained ones that triggered the stop.

3. Learning curve: every train-loss log and every evaluation is appended to a CSV, and a
   PNG of train vs. validation loss is rendered at the end.
"""

import csv
import gc
import logging
import math
import os
from pathlib import Path

from transformers import TrainerCallback

log = logging.getLogger("train.guard")


class AcceleratorRequired(RuntimeError):
    pass


def lock_accelerator(device: str) -> str:
    """Validate the accelerator. Must run before `import torch` for the MPS fallback switch."""
    if device == "mps":
        os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "0"
    import torch

    if device == "mps":
        if not torch.backends.mps.is_available():
            raise AcceleratorRequired("Apple GPU (MPS) is not available; refusing to train on CPU")
    elif device == "cuda":
        if not torch.cuda.is_available():
            raise AcceleratorRequired("CUDA GPU is not available; refusing to train on CPU")
    elif device != "cpu":
        raise AcceleratorRequired(f"unknown device {device!r}")
    log.info("accelerator locked: %s", device)
    return device


class DeviceGuardCallback(TrainerCallback):
    """Abort if the model is not on the required device when training starts."""

    def __init__(self, device: str):
        self.device = device

    def on_train_begin(self, args, state, control, model=None, **kwargs):
        actual = {p.device.type for p in model.parameters()}
        if actual != {self.device}:
            raise AcceleratorRequired(f"model parameters are on {actual}, required {self.device}")
        log.info("device check passed: all %d parameter tensors on %s", len(list(model.parameters())), actual)


class MemoryGuardCallback(TrainerCallback):
    """Keep GPU memory flat on Apple silicon.

    The MPS caching allocator holds on to blocks for every new tensor shape it sees; on a
    16 GB unified-memory Mac that can grow until the OS swaps and training slows ~20x.
    This releases cached blocks every `every` steps and after each evaluation, and logs
    the driver's allocation at every evaluation.
    """

    def __init__(self, device: str, every: int = 25):
        self.device = device
        self.every = every

    def _release(self):
        gc.collect()
        if self.device == "mps":
            import torch

            torch.mps.empty_cache()

    def on_step_end(self, args, state, control, **kwargs):
        if state.global_step % self.every == 0:
            self._release()

    def on_evaluate(self, args, state, control, **kwargs):
        self._release()
        if self.device == "mps":
            import torch

            log.info(
                "GPU memory after eval: allocated %.2f GB, driver %.2f GB",
                torch.mps.current_allocated_memory() / 1e9,
                torch.mps.driver_allocated_memory() / 1e9,
            )


class OverfitGuardCallback(TrainerCallback):
    def __init__(
        self,
        curve_path: Path,
        patience: int = 2,
        min_delta: float = 0.002,
        spike_tolerance: float = 0.05,
        f1_tolerance: float = 0.01,
    ):
        self.curve_path = Path(curve_path)
        self.patience = patience
        self.min_delta = min_delta
        self.spike_tolerance = spike_tolerance
        self.f1_tolerance = f1_tolerance

        self.best_loss = math.inf
        self._patience_ref = math.inf
        self.best_f1 = -math.inf
        self.best_step = None
        self.bad_evals = 0
        self.stop_reason: str | None = None
        self.history: list[dict] = []

        self.curve_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.curve_path.exists()
        self._fh = self.curve_path.open("a", newline="")
        self._csv = csv.writer(self._fh)
        if new:
            self._csv.writerow(["step", "epoch", "kind", "loss", "f1_macro", "accuracy", "learning_rate"])

    # ------------------------------------------------------------------ helpers
    def _row(self, step, epoch, kind, loss, f1=None, acc=None, lr=None):
        self._csv.writerow([step, round(epoch or 0, 4), kind, loss, f1, acc, lr])
        self._fh.flush()
        self.history.append({"step": step, "kind": kind, "loss": loss, "f1": f1})

    def _stop(self, control, reason: str):
        self.stop_reason = reason
        control.should_training_stop = True
        log.warning("STOPPING TRAINING: %s", reason)

    # ------------------------------------------------------------------ hooks
    def on_train_begin(self, args, state, control, **kwargs):
        """On resume, rebuild best loss / F1 / patience from the checkpoint's eval history."""
        evals = [h for h in state.log_history if "eval_loss" in h]
        for h in evals:
            loss = float(h["eval_loss"])
            if loss < self._patience_ref - self.min_delta:
                self._patience_ref, self.bad_evals = loss, 0
            else:
                self.bad_evals += 1
            if loss < self.best_loss:
                self.best_loss, self.best_step = loss, h.get("step")
            self.best_f1 = max(self.best_f1, float(h.get("eval_f1_macro", float("-inf"))))
        if evals:
            log.info(
                "guard restored from checkpoint: %d evals, best val loss %.4f @ step %s, best F1 %.4f, "
                "patience %d/%d",
                len(evals),
                self.best_loss,
                self.best_step,
                self.best_f1,
                self.bad_evals,
                self.patience,
            )

    def on_log(self, args, state, control, logs=None, **kwargs):
        if not logs or "loss" not in logs:
            return
        loss = float(logs["loss"])
        self._row(state.global_step, state.epoch, "train", loss, lr=logs.get("learning_rate"))
        if not math.isfinite(loss):
            self._stop(control, f"training loss diverged ({loss}) at step {state.global_step}")

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if not metrics or "eval_loss" not in metrics:
            return
        step = state.global_step
        loss = float(metrics["eval_loss"])
        f1 = float(metrics.get("eval_f1_macro", float("nan")))
        acc = float(metrics.get("eval_accuracy", float("nan")))
        self._row(step, state.epoch, "eval", loss, f1, acc)

        if not math.isfinite(loss):
            self._stop(control, f"validation loss diverged ({loss}) at step {step}")
            return

        # Patience counts evaluations without a *meaningful* improvement (> min_delta) over the
        # loss at the last meaningful improvement; best_loss/best_step track the true minimum,
        # which is also the checkpoint the Trainer keeps.
        if loss < self._patience_ref - self.min_delta:
            self._patience_ref, self.bad_evals = loss, 0
            verdict = "improved"
        else:
            self.bad_evals += 1
            verdict = f"no meaningful improvement ({self.bad_evals}/{self.patience})"
        if loss < self.best_loss:
            self.best_loss, self.best_step = loss, step
        self.best_f1 = max(self.best_f1, f1)

        log.info(
            "EVAL step=%d  val_loss=%.4f (best %.4f @ %s)  f1=%.4f  acc=%.4f  -> %s",
            step,
            loss,
            self.best_loss,
            self.best_step,
            f1,
            acc,
            verdict,
        )

        if loss > self.best_loss * (1 + self.spike_tolerance):
            self._stop(
                control,
                f"overfitting: val loss {loss:.4f} is >{self.spike_tolerance:.0%} above best "
                f"{self.best_loss:.4f} (step {self.best_step})",
            )
        elif self.bad_evals >= self.patience:
            self._stop(
                control,
                f"overfitting: val loss has not improved for {self.patience} evaluations "
                f"(best {self.best_loss:.4f} at step {self.best_step})",
            )
        elif self.best_f1 - f1 > self.f1_tolerance:
            self._stop(control, f"learning curve dropping: val F1 {f1:.4f} vs best {self.best_f1:.4f}")

    def on_train_end(self, args, state, control, **kwargs):
        self._fh.close()
        log.info(
            "guard summary: best val loss %.4f at step %s; stop reason: %s",
            self.best_loss,
            self.best_step,
            self.stop_reason or "completed all planned epochs",
        )


def plot_curve(curve_csv: Path, out_png: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError:
        return False

    df = pd.read_csv(curve_csv)
    train, ev = df[df.kind == "train"], df[df.kind == "eval"]
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(train.step, train.loss, label="train loss", alpha=0.7)
    ax1.plot(ev.step, ev.loss, "o-", label="validation loss")
    ax1.set_xlabel("step")
    ax1.set_ylabel("loss")
    ax2 = ax1.twinx()
    ax2.plot(ev.step, ev.f1_macro, "s--", color="tab:green", label="validation F1 macro")
    ax2.set_ylabel("F1 macro")
    lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
    ax1.legend(lines, labels, loc="center right")
    ax1.set_title("DistilBERT fine-tuning: learning curve")
    fig.tight_layout()
    fig.savefig(out_png, dpi=120)
    plt.close(fig)
    return True
