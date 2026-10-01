"""Label pull requests with whose turn it is and how complex they are.

Each pull request gets one ``status: ...`` label, decided by the rules in
``status.py`` every time it is triaged, and one ``complexity: ...`` label, estimated
by Claude once and again only if the pull request at least doubles. A label a
maintainer sets by hand wins: a complexity label the bot did not set is left alone.
One comment per pull request explains both and carries the bot's state.
"""

from __future__ import annotations

import dataclasses
import urllib.parse
from typing import Any

import anthropic

from scripts.pr_bot import assess, comments, pulls, status
from scripts.pr_bot.github import GitHub, GitHubError
from scripts.pr_bot.llm import Claude, ClaudeError
from scripts.pr_bot.pulls import Comment, PullRequest
from scripts.pr_bot.status import Status, Verdict

PURPOSE = "triage"
COMPLEXITY_PREFIX = "complexity: "
# Colors and descriptions for the labels the bot creates when they are missing.
LABELS = {
    Status.READY.label: (
        "0e8a16",
        "Approved and required checks passed: a maintainer can merge it",
    ),
    Status.MAINTAINER.label: (
        "fbca04",
        "The next step is a maintainer's: review, re-review or merge",
    ),
    Status.SUBMITTER.label: (
        "d93f0b",
        "The next step is the author's: conflicts, failing checks or open feedback",
    ),
    "complexity: low": ("c2e0c6", "Small, local change: quick to review"),
    "complexity: medium": (
        "bfd4f2",
        "A contained logic change: review needs the surrounding code",
    ),
    "complexity: high": ("d4c5f9", "Cross-cutting or risky change: needs deep review"),
}
STATUS_LABELS = frozenset(s.label for s in Status)
# A bot estimate is redone once the pull request has grown this much.
_GROWTH_FACTOR = 2
_GROWTH_MIN_LINES = 200
_RATIONALE_LIMIT = 400


@dataclasses.dataclass(frozen=True)
class Complexity:
    """The complexity a pull request is labeled with, and who decided it."""

    level: str | None
    rationale: str | None = None
    by_bot: bool = False


@dataclasses.dataclass
class State:
    """What the bot remembers about a pull request, kept in its triage comment."""

    complexity: str | None = None
    rationale: str | None = None
    size: int | None = None
    judged: dict[str, bool] = dataclasses.field(default_factory=dict)

    @classmethod
    def load(cls, body: str | None) -> State:
        """Read the state from the triage comment.

        Args:
            body: The comment's Markdown, or None when there is no comment yet.

        Returns:
            The state; fields that are missing or malformed take their defaults.
        """
        data = comments.decode_state(body or "")
        judged = data.get("judged")
        size = data.get("size")
        return cls(
            complexity=data.get("complexity")
            if data.get("complexity") in assess.LEVELS
            else None,
            rationale=str(data["rationale"]) if data.get("rationale") else None,
            size=size if isinstance(size, int) else None,
            judged={str(key): bool(value) for key, value in judged.items()}
            if isinstance(judged, dict)
            else {},
        )

    def dump(self) -> dict[str, Any]:
        """Return the state for the comment.

        Returns:
            The fields that are set.
        """
        return {
            key: value
            for key, value in dataclasses.asdict(self).items()
            if value not in (None, {})
        }


def render(
    pr: PullRequest, verdict: Verdict, complexity: Complexity, state: State
) -> str:
    """Write the triage comment.

    Args:
        pr: The pull request.
        verdict: Whose turn it is and why.
        complexity: The complexity label and its rationale.
        state: The state to carry.

    Returns:
        The comment's Markdown.
    """
    lines = [comments.marker(PURPOSE), f"**Status: {verdict.status.value}**", ""]
    lines.extend(f"- {reason}" for reason in verdict.reasons)
    lines.append("")
    if complexity.level is None:
        later = (
            " It is estimated once the pull request is ready for review."
            if pr.is_draft
            else ""
        )
        lines.append(f"**Complexity:** not estimated yet.{later}")
    elif not complexity.by_bot:
        lines.append(f"**Complexity: {complexity.level}** (set by a maintainer).")
    elif complexity.rationale:
        rationale = comments.sanitize(complexity.rationale, _RATIONALE_LIMIT)
        lines.append(f"**Complexity: {complexity.level}**. {rationale}")
    else:
        lines.append(f"**Complexity: {complexity.level}**")
    lines.extend([
        "",
        (
            "<sub>The PR triage bot updates this comment as the pull request changes. "
            f"[How it decides]({comments.README})</sub>"
        ),
        comments.encode_state(state.dump()),
    ])
    return "\n".join(lines)


@dataclasses.dataclass
class Triage:
    """Triage pull requests and apply the results."""

    github: GitHub
    claude: Claude | None
    required: frozenset[str]
    # How many complexity estimates this run may make; each costs a Claude request.
    estimates_left: int
    write: comments.Writer
    _label_names: set[str] | None = None

    def _bot_comments(self, pr: PullRequest) -> list[Comment]:
        """Find the bot's triage comments.

        Args:
            pr: The pull request.

        Returns:
            The comments, oldest first.
        """
        found = comments.find(pr.comments, PURPOSE)
        if found or pr.comment_count <= len(pr.comments):
            return found
        # The comment predates the latest comments the facts query fetched.
        return comments.find(comments.all_comments(self.github, pr.number), PURPOSE)

    def _judge(self, pr: PullRequest, state: State) -> None:
        """Have Claude read maintainers' comments that may ask the author for something.

        Args:
            pr: The pull request.
            state: The state; its judgments are updated in place.
        """
        # A draft is the author's turn whatever its comments say.
        requests = [] if pr.is_draft else status.requests_to_judge(pr)
        current = {request.node_id for request in requests}
        # Requests older than the author's last move no longer matter.
        state.judged = {k: v for k, v in state.judged.items() if k in current}
        unjudged = [r for r in requests if r.node_id not in state.judged]
        if not unjudged or self.claude is None:
            return
        try:
            state.judged.update(assess.judge_requests(self.claude, pr, unjudged))
        except (ClaudeError, anthropic.APIError) as error:
            print(f"::warning::#{pr.number}: could not judge comments: {error}")

    def _complexity(self, pr: PullRequest, state: State) -> Complexity:
        """Decide the complexity label, estimating it when needed and allowed.

        Args:
            pr: The pull request.
            state: The state; updated in place with a new estimate.

        Returns:
            The complexity to show.
        """
        labeled = sorted(
            label.removeprefix(COMPLEXITY_PREFIX)
            for label in pr.labels
            if label.startswith(COMPLEXITY_PREFIX)
        )
        current = labeled[0] if labeled else None
        if current is not None and current != state.complexity:
            return Complexity(current)
        grown = (
            current is not None
            and state.size is not None
            and pr.size
            >= max(state.size * _GROWTH_FACTOR, state.size + _GROWTH_MIN_LINES)
        )
        wanted = (current is None or grown) and not pr.is_draft
        if wanted and self.claude is not None and self.estimates_left > 0:
            self.estimates_left -= 1
            try:
                estimate = assess.estimate_complexity(
                    self.claude,
                    pr,
                    self.github.pull_files(pr.number),
                    self.github.pull_diff(pr.number),
                )
            except (ClaudeError, anthropic.APIError, GitHubError) as error:
                # The status label matters more than the estimate; try again later.
                print(
                    f"::warning::#{pr.number}: could not estimate complexity: {error}"
                )
            else:
                state.complexity = estimate.level
                state.rationale = estimate.rationale
                state.size = pr.size
                return Complexity(estimate.level, estimate.rationale, by_bot=True)
        if current is None:
            return Complexity(None)
        return Complexity(current, state.rationale, by_bot=True)

    def _ensure_labels(self, names: set[str]) -> None:
        """Create the bot's labels that the repository does not define yet.

        Args:
            names: Labels about to be added.
        """
        if self._label_names is None:
            self._label_names = self.github.label_names()
        for name in sorted(names - self._label_names):
            color, description = LABELS[name]
            self.write(self.github.create_label, name, color, description)
            self._label_names.add(name)

    def _apply_labels(
        self, pr: PullRequest, verdict: Verdict, complexity: Complexity
    ) -> list[str]:
        """Set the status and complexity labels.

        Args:
            pr: The pull request.
            verdict: Its status.
            complexity: Its complexity.

        Returns:
            The changes, as ``+label`` and ``-label``.
        """
        wanted = {verdict.status.label}
        stale = STATUS_LABELS - wanted
        if complexity.by_bot and complexity.level is not None:
            wanted.add(f"{COMPLEXITY_PREFIX}{complexity.level}")
            stale |= {
                label
                for label in pr.labels
                if label.startswith(COMPLEXITY_PREFIX) and label not in wanted
            }
        add = wanted - pr.labels
        remove = stale & pr.labels
        if add:
            self._ensure_labels(add)
            self.write(self.github.add_labels, pr.number, sorted(add))
        for label in sorted(remove):
            self.write(self.github.remove_label, pr.number, label)
        return [f"+{label}" for label in sorted(add)] + [
            f"-{label}" for label in sorted(remove)
        ]

    def triage(self, pr: PullRequest) -> Verdict:
        """Triage one pull request: labels, comment and state.

        Args:
            pr: The pull request.

        Returns:
            Its status.
        """
        existing = self._bot_comments(pr)
        state = State.load(existing[0].body if existing else None)
        self._judge(pr, state)
        verdict = status.classify(pr, self.required, state.judged)
        complexity = self._complexity(pr, state)
        changes = self._apply_labels(pr, verdict, complexity)
        body = render(pr, verdict, complexity, state)
        # Drafts get labels but no comment until there is something to review.
        outcome = comments.upsert(
            self.github, pr.number, body, existing, self.write, create=not pr.is_draft
        )
        print(
            f"#{pr.number}: {verdict.status.value}, complexity "
            f"{complexity.level or 'unknown'}; labels {' '.join(changes) or 'unchanged'}; "
            f"comment {outcome}"
        )
        return verdict

    def _triage_reporting_errors(self, pr: PullRequest) -> bool:
        """Triage one pull request of a sweep, reporting a GitHub failure.

        Args:
            pr: The pull request.

        Returns:
            Whether it succeeded.
        """
        try:
            self.triage(pr)
        except GitHubError as error:
            print(f"::error::#{pr.number}: {error}")
            return False
        return True

    def sweep(self) -> int:
        """Triage every open pull request.

        Returns:
            How many pull requests failed.
        """
        return sum(
            not self._triage_reporting_errors(pr)
            for pr in pulls.fetch_open(self.github)
        )


def find_by_head(github: GitHub, owner: str, branch: str) -> list[int]:
    """Find the open pull requests whose head is a given branch.

    Args:
        github: The client.
        owner: The owner of the repository holding the branch (a fork's owner).
        branch: The branch name.

    Returns:
        The pull request numbers.
    """
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}"})
    return [
        pull["number"] for pull in github.paginate(github.repo_path(f"pulls?{query}"))
    ]
