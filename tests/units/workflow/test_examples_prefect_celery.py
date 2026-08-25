"""Canonical Prefect and Celery examples expressed as Reflex workflows.

The examples intentionally follow the official documentation shapes closely:

* Prefect API-sourced ETL:
  https://docs.prefect.io/v3/examples/run-api-sourced-etl
* Celery chains, groups, and chords:
  https://docs.celeryq.dev/en/stable/userguide/canvas.html

External API and database calls are simulated so the durable orchestration is
tested deterministically against every configured workflow store.
"""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus, StepStatus
from reflex.workflow.testing import WorkflowTestHarness

Article = dict[str, str | int]

FETCH_ATTEMPTS: dict[int, int] = {}
FETCH_FAILURES_REMAINING: dict[int, int] = {}
FETCH_ALWAYS_FAIL: set[int] = set()
LOADED_BATCHES: list[list[Article]] = []


def _reset_prefect_io() -> None:
    """Reset the deterministic API and database doubles."""
    FETCH_ATTEMPTS.clear()
    FETCH_FAILURES_REMAINING.clear()
    FETCH_ALWAYS_FAIL.clear()
    LOADED_BATCHES.clear()


def _simulated_api_page(page: int) -> list[Article]:
    """Return the deterministic response for one API page.

    Args:
        page: The requested page number.

    Returns:
        Two article records.

    Raises:
        TransientWorkflowError: When the configured API double is unavailable.
    """
    FETCH_ATTEMPTS[page] = FETCH_ATTEMPTS.get(page, 0) + 1
    failures_remaining = FETCH_FAILURES_REMAINING.get(page, 0)
    if page in FETCH_ALWAYS_FAIL or failures_remaining:
        if failures_remaining:
            FETCH_FAILURES_REMAINING[page] = failures_remaining - 1
        msg = f"article API returned 503 for page {page}"
        raise TransientWorkflowError(msg)
    return [
        {
            "id": page * 10 + offset,
            "title": f"article-{page}-{offset}",
            "published_at": f"2026-08-{page + offset:02d}",
            "url": f"https://example.test/articles/{page}-{offset}",
        }
        for offset in (1, 2)
    ]


class PrefectFetchPage(rx.State):
    """One independently retryable API-page task."""

    __workflow__ = WorkflowConfig(id="examples.prefect.fetch_page")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="read",
        retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
    )
    def fetch(self, page: int):
        """Fetch and return one page.

        Args:
            page: The requested page number.

        Returns:
            Completion carrying that page's records.
        """
        return rx.complete(result=_simulated_api_page(page))


class PrefectApiEtl(rx.State):
    """Fan out extraction, transform the join, then durably load it."""

    __workflow__ = WorkflowConfig(id="examples.prefect.api_etl")
    articles: list[Article] = []
    page_count: int = 0

    @rx.event(durable=True, trigger=manual(), effect="none")
    def etl(self, pages: list[int]):
        """Start one durable child run per API page.

        Args:
            pages: Page numbers to extract.

        Returns:
            A fan-out joined by ``combine_pages``.
        """
        self.page_count = len(pages)
        return rx.parallel(
            *(PrefectFetchPage.fetch(page) for page in pages),
            then=PrefectApiEtl.combine_pages,
        )

    @rx.event(durable=True, effect="none")
    def combine_pages(self, results: list):
        """Flatten successful pages or fail the ETL before transformation.

        Args:
            results: Ordered child-run outcomes from the fan-out.

        Returns:
            The transform step, or terminal failure.
        """
        failures = [result for result in results if result["status"] != "COMPLETED"]
        if failures:
            return rx.fail(reason=f"{len(failures)} API page(s) failed")
        records = [article for result in results for article in result["result"]]
        return PrefectApiEtl.transform(records)

    @rx.event(durable=True, effect="none")
    def transform(self, records: list[Article]):
        """Normalize the joined API response into the load schema.

        Args:
            records: Flattened raw articles.

        Returns:
            The durable load step.
        """
        self.articles = [
            {
                "id": record["id"],
                "title": str(record["title"]).upper(),
                "published_at": record["published_at"],
                "url": record["url"],
            }
            for record in records
        ]
        return PrefectApiEtl.load

    @rx.event(durable=True, effect="idempotent_write")
    def load(self):
        """Write the transformed batch to the simulated database.

        Returns:
            Completion carrying the load summary.
        """
        LOADED_BATCHES.append([dict(article) for article in self.articles])
        return rx.complete(
            result={"loaded": len(self.articles), "pages": self.page_count}
        )


class CeleryChain(rx.State):
    """The official ``add(2, 2) | add(4) | add(8)`` Canvas chain."""

    __workflow__ = WorkflowConfig(id="examples.celery.chain")
    value: int = 0
    intermediate_results: list[int] = []

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, left: int, right: int):
        """Run the first addition and allocate the rest of the chain.

        Args:
            left: First addend.
            right: Second addend.

        Returns:
            The remaining additions and final result step.
        """
        self.value = left + right
        self.intermediate_results = [self.value]
        return [
            CeleryChain.add_previous(4),
            CeleryChain.add_previous(8),
            CeleryChain.finish,
        ]

    @rx.event(durable=True, effect="none")
    def add_previous(self, addend: int):
        """Add to the durable result of the preceding handler.

        Args:
            addend: Value from the next Celery partial signature.
        """
        self.value += addend
        self.intermediate_results = [*self.intermediate_results, self.value]

    @rx.event(durable=True, effect="none")
    def finish(self):
        """Return the chain's final value.

        Returns:
            Completion carrying the final sum.
        """
        return rx.complete(result=self.value)


class CeleryAdd(rx.State):
    """The task placed in the Celery-style group header."""

    __workflow__ = WorkflowConfig(id="examples.celery.add")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def add(self, left: int, right: int):
        """Add two values.

        Args:
            left: First addend.
            right: Second addend.

        Returns:
            Completion carrying their sum.
        """
        return rx.complete(result=left + right)


class CeleryChord(rx.State):
    """A parallel group whose ordered results feed a sum callback."""

    __workflow__ = WorkflowConfig(id="examples.celery.chord")
    group_results: list[int] = []

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, size: int):
        """Create the equivalent of ``group(add.s(i, i)) | tsum.s()``.

        Args:
            size: Number of additions in the group.

        Returns:
            A parallel fan-out joined by the sum callback.
        """
        return rx.parallel(
            *(CeleryAdd.add(index, index) for index in range(size)),
            then=CeleryChord.sum_results,
        )

    @rx.event(durable=True, effect="none")
    def sum_results(self, results: list):
        """Fail like a chord or sum every successful group result.

        Args:
            results: Ordered child-run outcomes from the group.

        Returns:
            Terminal failure or completion carrying the total.
        """
        failures = [result for result in results if result["status"] != "COMPLETED"]
        if failures:
            return rx.fail(reason=f"{len(failures)} chord task(s) failed")
        self.group_results = [result["result"] for result in results]
        return rx.complete(result=sum(self.group_results))


async def test_prefect_etl_retries_one_page_then_loads():
    """Each page retries independently before transform and load resume."""
    _reset_prefect_io()
    FETCH_FAILURES_REMAINING[2] = 1

    async with WorkflowTestHarness(PrefectApiEtl, PrefectFetchPage) as harness:
        started = await harness.start(PrefectApiEtl.etl([1, 2, 3]))
        assert started.run_id is not None

        waiting = await harness.get_run(started.run_id)
        assert waiting is not None
        assert waiting.status is RunStatus.WAITING
        assert waiting.steps[1].status is StepStatus.BLOCKED
        assert waiting.steps[1].join_arrived == 2
        assert FETCH_ATTEMPTS == {1: 1, 2: 1, 3: 1}
        assert not LOADED_BATCHES

        await harness.advance("1s")

        completed = await harness.get_run(started.run_id)
        assert completed is not None
        assert completed.status is RunStatus.COMPLETED
        assert completed.result == {"loaded": 6, "pages": 3}
        assert FETCH_ATTEMPTS == {1: 1, 2: 2, 3: 1}
        assert len(LOADED_BATCHES) == 1
        assert [article["id"] for article in LOADED_BATCHES[0]] == [
            11,
            12,
            21,
            22,
            31,
            32,
        ]
        assert all(
            str(article["title"]).startswith("ARTICLE-")
            for article in LOADED_BATCHES[0]
        )


async def test_prefect_etl_does_not_load_after_page_retry_exhaustion():
    """A terminal page failure fails the parent without calling the loader."""
    _reset_prefect_io()
    FETCH_ALWAYS_FAIL.add(2)

    async with WorkflowTestHarness(PrefectApiEtl, PrefectFetchPage) as harness:
        started = await harness.start(PrefectApiEtl.etl([1, 2, 3]))
        assert started.run_id is not None
        await harness.advance("1s")

        failed = await harness.get_run(started.run_id)
        assert failed is not None
        assert failed.status is RunStatus.FAILED
        assert FETCH_ATTEMPTS == {1: 1, 2: 2, 3: 1}
        assert not LOADED_BATCHES


async def test_celery_canvas_chain_threads_each_intermediate_result():
    """The official three-addition chain produces 4, then 8, then 16."""
    async with WorkflowTestHarness(CeleryChain) as harness:
        started = await harness.start(CeleryChain.start(2, 2))
        assert started.run_id is not None

        completed = await harness.get_run(started.run_id)
        assert completed is not None
        assert completed.status is RunStatus.COMPLETED
        assert completed.result == 16
        assert completed.state["intermediate_results"] == [4, 8, 16]
        assert [step.status for step in completed.steps] == [
            StepStatus.SUCCEEDED,
            StepStatus.SUCCEEDED,
            StepStatus.SUCCEEDED,
            StepStatus.SUCCEEDED,
        ]


async def test_celery_group_chord_adds_in_parallel_then_sums():
    """Ten ``add(i, i)`` child runs join into the documented total of 90."""
    async with WorkflowTestHarness(CeleryChord, CeleryAdd) as harness:
        started = await harness.start(CeleryChord.start(10))
        assert started.run_id is not None

        completed = await harness.get_run(started.run_id)
        assert completed is not None
        assert completed.status is RunStatus.COMPLETED
        assert completed.result == 90
        assert completed.state["group_results"] == list(range(0, 20, 2))
        assert completed.steps[1].join_expected == 10
        assert completed.steps[1].join_arrived == 10

        runs = await harness.kernel.list_runs()
        children = [run for run in runs if run.parent_run_id == started.run_id]
        assert len(children) == 10
        assert all(child.status is RunStatus.COMPLETED for child in children)
