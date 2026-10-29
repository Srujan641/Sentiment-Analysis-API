"""Runs analyses in a background thread so requests return immediately (JOB-1).

One worker thread: the models are shared and analyses are CPU/GPU bound, so running them
one at a time is fastest overall. The embedding model loads on first use. In production
the same function runs in a separate worker process fed by Redis.
"""

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import select

from app.analysis.engine import ChangeInput, ReviewInput, analyse
from app.platform.models import Analysis, ProductChange, Review

logger = logging.getLogger(__name__)


class AnalysisRunner:
    def __init__(self, db, get_classifier, encoder_factory, get_connectors=lambda: {}):
        self._db = db
        self._get_connectors = get_connectors
        self._get_classifier = get_classifier
        self._encoder_factory = encoder_factory
        self._encoder = None
        self._matcher = None
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")

    def submit(self, analysis_id: str):
        return self._pool.submit(self._run, analysis_id)

    def submit_research(self, research_id: str):
        return self._pool.submit(self._research, research_id)

    def _research(self, research_id: str) -> None:
        from app.platform.models import Research
        from app.research.identify import IdentifyError
        from app.research.pipeline import research

        def update(**fields):
            with self._db.sessionmaker() as s:
                r = s.get(Research, research_id)
                for k, v in fields.items():
                    setattr(r, k, v)
                s.commit()

        with self._db.sessionmaker() as s:
            query = s.get(Research, research_id).query
        update(status="running", stage="starting")
        try:
            encoder, matcher = self._models()
            result = research(
                query,
                self._get_connectors(),
                self._get_classifier(),
                encoder,
                matcher,
                progress=lambda stage: update(stage=stage),
            )
            update(
                status="complete",
                stage=None,
                product_name=result["product"]["name"],
                identified_from=result["product"]["identified_from"],
                result=json.dumps(result, default=str),
                finished_at=datetime.now(UTC),
            )
        except IdentifyError as exc:
            update(status="failed", stage=None, error=str(exc), finished_at=datetime.now(UTC))
        except Exception as exc:  # noqa: BLE001
            logger.exception("research failed", extra={"research_id": research_id})
            update(
                status="failed",
                stage=None,
                error=f"Research failed: {type(exc).__name__}",
                finished_at=datetime.now(UTC),
            )

    def submit_collection(self, run_id: str):
        return self._pool.submit(self._collect, run_id)

    def _collect(self, run_id: str) -> None:
        """Collect from every source of a product; one failing source doesn't stop the others."""
        from app.connectors.base import ConnectorError
        from app.platform.deps import Principal
        from app.platform.models import CollectionRun, Organization, Product, ProductSource
        from app.platform.routes.reviews import store_reviews

        connectors = self._get_connectors()
        results = []
        try:
            with self._db.sessionmaker() as s:
                run = s.get(CollectionRun, run_id)
                run.status = "running"
                s.commit()
                product = s.get(Product, run.product_id)
                principal = Principal(org=s.get(Organization, run.org_id))
                sources = s.scalars(select(ProductSource).where(ProductSource.product_id == product.id)).all()
                for src in sources:
                    run.stage = f"Collecting from {src.label}"
                    s.commit()
                    entry = {"source_id": src.id, "label": src.label, "connector": src.connector}
                    try:
                        connector = connectors.get(src.connector)
                        if connector is None or not connector.available():
                            raise ConnectorError(
                                getattr(connector, "requires", None) or "Connector unavailable."
                            )
                        raw = connector.collect(src.ref, product.name)
                        rows = [
                            {
                                "text": r.text,
                                "rating": r.rating,
                                "reviewed_on": r.reviewed_on,
                                "external_id": r.external_id,
                            }
                            for r in raw
                        ]
                        res = store_reviews(s, principal, product.id, rows, src.connector, allow_partial=True)
                        entry |= {"fetched": len(raw), **res.model_dump()}
                        src.last_error, src.last_added = None, res.added
                    except ConnectorError as exc:
                        entry["error"] = str(exc)
                        src.last_error = str(exc)
                    except Exception as exc:  # noqa: BLE001 - one source must not break the run
                        logger.exception("collection failed", extra={"source_id": src.id})
                        entry["error"] = f"Unexpected error: {type(exc).__name__}"
                        src.last_error = entry["error"]
                    src.last_collected_at = datetime.now(UTC)
                    s.commit()
                    results.append(entry)
                run.status, run.stage = "complete", None
                run.results = json.dumps(results, default=str)
                run.finished_at = datetime.now(UTC)
                s.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("collection run failed", extra={"run_id": run_id})
            with self._db.sessionmaker() as s:
                run = s.get(CollectionRun, run_id)
                run.status, run.stage, run.error = "failed", None, str(exc)[:500]
                run.results = json.dumps(results, default=str)
                run.finished_at = datetime.now(UTC)
                s.commit()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _models(self):
        with self._lock:
            if self._encoder is None:
                from app.analysis.aspects import AspectMatcher

                self._encoder = self._encoder_factory()
                self._matcher = AspectMatcher(self._encoder)
        return self._encoder, self._matcher

    def _set(self, analysis_id: str, **fields) -> None:
        with self._db.sessionmaker() as s:
            a = s.get(Analysis, analysis_id)
            for k, v in fields.items():
                setattr(a, k, v)
            s.commit()

    def _run(self, analysis_id: str) -> None:
        self._set(analysis_id, status="running", stage="loading models", started_at=datetime.now(UTC))
        try:
            with self._db.sessionmaker() as s:
                a = s.get(Analysis, analysis_id)
                rows = s.scalars(select(Review).where(Review.product_id == a.product_id)).all()
                reviews = [ReviewInput(r.id, r.text, r.rating, r.reviewed_on, r.source) for r in rows]
                changes = [
                    ChangeInput(c.id, c.changed_on, json.loads(c.aspects), c.description)
                    for c in s.scalars(select(ProductChange).where(ProductChange.product_id == a.product_id))
                ]
                kind = a.kind
            encoder, matcher = self._models()
            report = analyse(
                reviews,
                self._get_classifier(),
                encoder,
                matcher,
                changes,
                kind=kind,
                progress=lambda stage: self._set(analysis_id, stage=stage),
            )
            self._set(
                analysis_id,
                status="complete",
                stage=None,
                review_count=len(reviews),
                report=json.dumps(report, default=str),
                finished_at=datetime.now(UTC),
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure on the analysis record
            logger.exception("analysis failed", extra={"analysis_id": analysis_id})
            self._set(
                analysis_id, status="failed", stage=None, error=str(exc)[:500], finished_at=datetime.now(UTC)
            )
