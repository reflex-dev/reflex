import httpx
import os

# GraphQL queries (borrowed from https://github.com/anuraghazra/github-readme-stats/blob/master/src/fetchers/stats-fetcher.js).
GRAPHQL_STATS_QUERY = """
  query userInfo($login: String!) {
    user(login: $login) {
      name
      login
      contributionsCollection {
        totalCommitContributions,
        totalPullRequestReviewContributions
      }
      repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
        totalCount
      }
      pullRequests(first: 1) {
        totalCount
      }
      mergedPullRequests: pullRequests(states: MERGED) {
        totalCount
      }
      openIssues: issues(states: OPEN) {
        totalCount
      }
      closedIssues: issues(states: CLOSED) {
        totalCount
      }
      followers {
        totalCount
      }
      repositoryDiscussions {
        totalCount
      }
      repositoryDiscussionComments(onlyAnswers: true) {
        totalCount
      }
    }
  }
"""

# Set your GitHub personal access token (Replace with your actual token)
GITHUB_API_TOKEN = os.environ.get("GITHUB_API_TOKEN")

# Set the GitHub GraphQL API URL
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


async def user_stats(username: str):
    if GITHUB_API_TOKEN is None:
        raise RuntimeError("Set GITHUB_API_TOKEN in the environment")

    # Create a dictionary for the request headers with the Authorization header
    headers = {
        "Authorization": f"Bearer {GITHUB_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # Create a dictionary for the request payload
    payload = {
        "query": GRAPHQL_STATS_QUERY,
        "variables": {
            "login": username,
        },
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(GITHUB_GRAPHQL_URL, headers=headers, json=payload)

        response.raise_for_status()

        print(f"Fetched stats for {username}")

        if response.status_code == 200:
            data = response.json()
            user_data = data["data"]["user"]
            if user_data is None:
                print(f"User {username} not found")
                return None
            for key, value in user_data.items():
                if isinstance(value, dict) and "totalCount" in value:
                    user_data[key] = value["totalCount"]
            return user_data


# Run the asynchronous function
if __name__ == "__main__":
    import asyncio

    asyncio.run(user_stats("masenf"))
