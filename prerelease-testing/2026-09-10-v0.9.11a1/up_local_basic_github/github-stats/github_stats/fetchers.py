"""STUBBED for offline pre-release testing (cluster up_local_basic_github).

The upstream reflex-examples version of this module POSTs a GraphQL query to
https://api.github.com/graphql and requires GITHUB_API_TOKEN. This test copy replaces
`user_stats()` with a deterministic local generator so the app can be driven end to end
with no network and no credentials. Everything else about the app (state, LocalStorage
vars, background events, rx.recharts bar charts) is untouched upstream code.

The pristine upstream module is kept next to this one as `fetchers.py.orig`.
"""

import asyncio
import hashlib

# usernames the stub refuses to resolve, so the "user not found" branch is reachable
UNKNOWN_USERS = {"nosuchuser", "doesnotexist"}

FIELDS = (
    "totalCommitContributions",
    "repositoriesContributedTo",
    "pullRequests",
    "mergedPullRequests",
    "openIssues",
    "closedIssues",
    "followers",
    "repositoryDiscussions",
    "repositoryDiscussionComments",
)


def _n(username: str, field: str, mod: int) -> int:
    h = hashlib.sha256(f"{username}:{field}".encode()).hexdigest()
    return int(h[:8], 16) % mod


async def user_stats(username: str):
    """Return deterministic fake stats for `username` (offline stub).

    Args:
        username: the github login to "fetch".

    Returns:
        A dict shaped like the real GraphQL response, or None for an unknown user.
    """
    await asyncio.sleep(0.2)  # keep the background-event/"Fetching Data..." window observable
    if username.lower() in UNKNOWN_USERS:
        print(f"User {username} not found")
        return None
    data = {
        "name": f"Stub {username.title()}",
        "login": username,
        "contributionsCollection": {
            "totalCommitContributions": _n(username, "commits", 5000),
            "totalPullRequestReviewContributions": _n(username, "reviews", 900),
        },
    }
    for f in FIELDS:
        data[f] = _n(username, f, 400) + 1
    print(f"Fetched stats for {username} (STUB)")
    return data


if __name__ == "__main__":
    print(asyncio.run(user_stats("masenf")))
