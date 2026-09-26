"""Worked examples of durable workflows, each with its pass condition as a test.

Not part of the published package: these are read and run from the repository, so
the engine keeps being tested against the workflows it claims to support.
"""

from examples import (
    ex01_leads,
    ex02_weekly_update,
    ex03_client_setup,
    ex04_support_triage,
    ex05_social_posts,
    ex06_invoices,
    ex07_long_wait_approval,
    ex08_sweep,
    ex09_webhook_sync,
    ex10_research,
    ex11_background_job,
    ex12_media_pipeline,
    ex13_conversation,
)
from examples.base import Base
from examples.services import ProviderError, World, world

__all__ = [
    "Base",
    "ProviderError",
    "World",
    "ex01_leads",
    "ex02_weekly_update",
    "ex03_client_setup",
    "ex04_support_triage",
    "ex05_social_posts",
    "ex06_invoices",
    "ex07_long_wait_approval",
    "ex08_sweep",
    "ex09_webhook_sync",
    "ex10_research",
    "ex11_background_job",
    "ex12_media_pipeline",
    "ex13_conversation",
    "world",
]
