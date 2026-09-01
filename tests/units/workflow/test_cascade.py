"""Closing a parent closes the children it fanned out to.

An operator cancels a rollout to stop the blast radius. If the regional
deploys it spawned keep deploying, the button did not do the one thing it
exists to do. Fan-out children are cancelled with their parent by default;
``parent_close="abandon"`` opts a fan-out out, for the genuine
delegation case where a child should outlive whoever started it.
"""

from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness

DEPLOYED: list[str] = []


class Region(rx.State):
    """A regional deploy that acts after a soak delay."""

    __workflow__ = WorkflowConfig(id="cascade.region")
    region: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, region: str):
        """Soak, then deploy.

        Args:
            region: The region to deploy to.

        Returns:
            A deferral.
        """
        self.region = region
        return rx.after("1h", Region.deploy(region))

    @rx.event(durable=True, effect="non_idempotent_write")
    def deploy(self, region: str):
        """Perform the deploy.

        Args:
            region: The region to deploy to.

        Returns:
            Completion.
        """
        DEPLOYED.append(region)
        return rx.complete(result={"region": region})


def _rollout(**fan_out_kwargs):
    """Build a rollout parent fanning out to three regions.

    Args:
        fan_out_kwargs: Passed through to ``rx.parallel``.

    Returns:
        The parent workflow class.
    """

    class Rollout(rx.State):
        __workflow__ = WorkflowConfig(id="cascade.rollout")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out to every region.

            Returns:
                The fan-out.
            """
            return rx.parallel(
                Region.start("us-east"),
                Region.start("us-west"),
                Region.start("eu"),
                then=Rollout.report,
                **fan_out_kwargs,
            )

        @rx.event(durable=True, effect="none")
        def report(self, results: list):
            """Report the rollout.

            Args:
                results: One entry per region.

            Returns:
                Completion.
            """
            return rx.complete(result={"regions": len(results)})

    return Rollout


async def _children(harness: WorkflowTestHarness, parent_id: str):
    """List the runs fanned out from a parent.

    Args:
        harness: The running harness.
        parent_id: The parent run.

    Returns:
        The child run records.
    """
    runs = await harness.kernel.list_runs()
    return [run for run in runs if run.parent_run_id == parent_id]


async def test_cancelling_a_parent_stops_the_regions_it_started(
    forked_registration_context,
):
    """The cancel button stops the blast radius, not just the parent.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    DEPLOYED.clear()
    rollout = _rollout()
    async with WorkflowTestHarness(rollout, Region) as harness:
        result = await harness.start(rollout.begin())
        assert result.run_id is not None
        assert len(await _children(harness, result.run_id)) == 3

        await harness.cancel(result.run_id)
        await harness.advance("2h")

        assert DEPLOYED == [], (
            f"cancelling the rollout must stop the regions; deployed {DEPLOYED}"
        )
        statuses = {run.status for run in await _children(harness, result.run_id)}
        assert statuses == {RunStatus.CANCELLED}, statuses


async def test_abandon_lets_a_delegated_child_outlive_its_parent(
    forked_registration_context,
):
    """Delegation is a real shape, so it stays available -- just not silent.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    DEPLOYED.clear()
    rollout = _rollout(parent_close="abandon")
    async with WorkflowTestHarness(rollout, Region) as harness:
        result = await harness.start(rollout.begin())
        assert result.run_id is not None
        await harness.cancel(result.run_id)
        await harness.advance("2h")

        assert sorted(DEPLOYED) == ["eu", "us-east", "us-west"]
        statuses = {run.status for run in await _children(harness, result.run_id)}
        assert statuses == {RunStatus.COMPLETED}, statuses


class Shard(rx.State):
    """A grandchild that acts after a delay."""

    __workflow__ = WorkflowConfig(id="cascade.shard")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, shard: str):
        """Soak, then write.

        Args:
            shard: The shard to write.

        Returns:
            A deferral.
        """
        return rx.after("1h", Shard.write(shard))

    @rx.event(durable=True, effect="non_idempotent_write")
    def write(self, shard: str):
        """Perform the write.

        Args:
            shard: The shard to write.

        Returns:
            Completion.
        """
        DEPLOYED.append(f"shard:{shard}")
        return rx.complete(result={"shard": shard})


class Tier(rx.State):
    """A child that fans out again."""

    __workflow__ = WorkflowConfig(id="cascade.tier")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, tier: str):
        """Fan out to two shards.

        Args:
            tier: The tier being rolled out.

        Returns:
            The fan-out.
        """
        return rx.parallel(
            Shard.start(f"{tier}-a"), Shard.start(f"{tier}-b"), then=Tier.done
        )

    @rx.event(durable=True, effect="none")
    def done(self, results: list):
        """Finish the tier.

        Args:
            results: One entry per shard.

        Returns:
            Completion.
        """
        return rx.complete(result={"shards": len(results)})


class Deep(rx.State):
    """A rollout three levels deep."""

    __workflow__ = WorkflowConfig(id="cascade.deep")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self):
        """Fan out to two tiers.

        Returns:
            The fan-out.
        """
        return rx.parallel(Tier.start("web"), Tier.start("api"), then=Deep.report)

    @rx.event(durable=True, effect="none")
    def report(self, results: list):
        """Finish the rollout.

        Args:
            results: One entry per tier.

        Returns:
            Completion.
        """
        return rx.complete(result={"tiers": len(results)})


async def test_the_close_reaches_grandchildren(forked_registration_context):
    """Depth is not a loophole; the close walks the whole tree.

    Each level marks only its own branches, and a branch blocked on its own
    join holds no claim -- so it is control-pending at once, finalizes, and
    closes the level below it. A tier that could not drain until its shards
    reported would deadlock the whole scheme.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    DEPLOYED.clear()
    async with WorkflowTestHarness(Deep, Tier, Shard) as harness:
        result = await harness.start(Deep.begin())
        assert result.run_id is not None
        await harness.cancel(result.run_id)
        await harness.advance("2h")

        assert DEPLOYED == [], f"grandchildren kept writing: {DEPLOYED}"
        runs = await harness.kernel.list_runs()
        shards = [run for run in runs if run.workflow_id == "cascade.shard"]
        assert len(shards) == 4, f"expected four shards, got {len(shards)}"
        assert {run.status for run in shards} == {RunStatus.CANCELLED}


async def test_a_failed_parent_closes_its_branches(forked_registration_context):
    """Cancellation is not the only way a parent stops existing.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    DEPLOYED.clear()
    rollout = _rollout()
    async with WorkflowTestHarness(rollout, Region) as harness:
        result = await harness.start(rollout.begin())
        assert result.run_id is not None
        assert await harness.force_fail(result.run_id, "operator gave up")
        await harness.advance("2h")

        assert DEPLOYED == [], f"a failed rollout kept deploying: {DEPLOYED}"
        statuses = {run.status for run in await _children(harness, result.run_id)}
        assert statuses == {RunStatus.CANCELLED}, statuses
