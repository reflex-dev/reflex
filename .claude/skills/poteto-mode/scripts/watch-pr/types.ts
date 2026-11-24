declare const prNumberBrand: unique symbol;
export type PrNumber = number & { readonly [prNumberBrand]: "PrNumber" };
export type NonEmpty<T> = readonly [T, ...T[]];
export function nonEmpty<T>(items: readonly T[]): NonEmpty<T> | null {
  return items.length === 0 ? null : [items[0], ...items.slice(1)];
}
export function parsePrNumber(value: unknown, label = "PR number"): PrNumber {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0)
    throw new Error(`${label} must be a positive integer`);
  return value as PrNumber;
}
export interface Repository {
  readonly owner: string;
  readonly repo: string;
}
export interface PrContext extends Repository {
  readonly number: PrNumber;
}
export type MergeStateStatus =
  | "BEHIND"
  | "BLOCKED"
  | "CLEAN"
  | "CONFLICTING"
  | "DIRTY"
  | "DRAFT"
  | "HAS_HOOKS"
  | "UNKNOWN"
  | "UNSTABLE";
export type RollupState =
  | "ERROR"
  | "EXPECTED"
  | "FAILURE"
  | "PENDING"
  | "SUCCESS"
  | null;
export type ReviewDecision =
  | "APPROVED"
  | "CHANGES_REQUESTED"
  | "REVIEW_REQUIRED"
  | null;
export interface PullRequestFacts {
  readonly context: PrContext;
  readonly mergeable: "MERGEABLE" | "CONFLICTING" | "UNKNOWN";
  readonly mergeStateStatus: MergeStateStatus;
  readonly reviewDecision: ReviewDecision;
  readonly headRefOid: string | null;
  readonly headRefName: string;
  readonly baseRefName: string;
  readonly state: "OPEN" | "CLOSED" | "MERGED";
  readonly mergedAt: string | null;
  readonly isDraft: boolean;
}
export interface OpenPullRequest {
  readonly number: PrNumber;
  readonly isCrossRepository: boolean;
  readonly headRefName: string;
  readonly baseRefName: string;
}
export interface ReviewComment {
  readonly authorLogin: string | null;
  readonly body: string;
  readonly path: string | null;
  readonly line: number | null;
  readonly createdAt: string;
}
export interface ReviewThread {
  readonly id: string;
  readonly firstComment: ReviewComment | null;
  readonly isBugbot: boolean;
  readonly bugbotReviewPasses: number;
}
interface CheckDetails {
  readonly name: string;
  readonly reportedState: string;
  readonly description: string;
  readonly link: string;
  readonly workflow: string;
}
export type Check =
  | (CheckDetails & { readonly kind: "passed" })
  | (CheckDetails & { readonly kind: "skipped" })
  | (CheckDetails & { readonly kind: "failed" })
  | (CheckDetails & { readonly kind: "pending" })
  | (CheckDetails & {
      readonly kind: "code-review-gate";
      readonly name: "Code Review Gate";
    });
export type FailedCheck = Extract<Check, { readonly kind: "failed" }>;
export type PendingCheck = Extract<Check, { readonly kind: "pending" }>;
export interface CheckRead {
  readonly source: "gh-pr-checks" | "graphql-rollup";
  readonly checks: NonEmpty<Check>;
}
export interface CommitRollup {
  readonly oid: string;
  readonly state: RollupState;
}
export interface GitHubMergeRefusal {
  readonly kind: "refused";
  readonly mergeStateStatus: "BLOCKED";
  readonly headRollupState: "ERROR" | "FAILURE";
}
export type GitHubMergeAllowed =
  | {
      readonly kind: "allowed";
      readonly basis: "merge-state";
      readonly mergeStateStatus: Exclude<MergeStateStatus, "BLOCKED">;
      readonly headRollupState: RollupState;
    }
  | {
      readonly kind: "allowed";
      readonly basis: "rollup";
      readonly mergeStateStatus: "BLOCKED";
      readonly headRollupState: Exclude<RollupState, "ERROR" | "FAILURE">;
    };
export type GitHubMergeAssessment = GitHubMergeAllowed | GitHubMergeRefusal;
interface CiBase {
  readonly source: CheckRead["source"];
  readonly all: NonEmpty<Check>;
  readonly hadPreviousPassingCi: boolean;
}
export type CiFailing = CiBase & {
  readonly kind: "ci-failing";
  readonly failed: NonEmpty<FailedCheck>;
  readonly pending: readonly PendingCheck[];
  readonly github: GitHubMergeAssessment;
};
export type CiGithubRejected = CiBase & {
  readonly kind: "ci-github-rejected";
  readonly failed: readonly [];
  readonly pending: readonly PendingCheck[];
  readonly github: GitHubMergeRefusal;
};
export type CiPending = CiBase & {
  readonly kind: "ci-pending";
  readonly failed: readonly [];
  readonly pending: NonEmpty<PendingCheck>;
};
export type CiClean = CiBase & {
  readonly kind: "ci-clean";
  readonly failed: readonly [];
  readonly pending: readonly [];
  readonly github: GitHubMergeAllowed;
};
export type CiState = CiFailing | CiGithubRejected | CiPending | CiClean;
export type PrSnapshot =
  | {
      readonly kind: "merged" | "closed";
      readonly context: PrContext;
      readonly facts: PullRequestFacts;
    }
  | {
      readonly kind: "open";
      readonly context: PrContext;
      readonly facts: PullRequestFacts;
      readonly threads: readonly ReviewThread[];
      readonly ci: CiState;
      readonly reviewAutomationRunning: boolean;
    };
export interface ReadyPr {
  readonly kind: "ready-pr";
  readonly context: PrContext;
  readonly proof: {
    readonly mergeability: "clear";
    readonly threads: readonly [];
    readonly ci: CiClean;
    readonly gate: {
      readonly state: "OPEN";
      readonly reviewDecision: Exclude<ReviewDecision, "CHANGES_REQUESTED">;
      readonly draft: "not-draft" | "draft-allowed";
    };
  };
}
export interface MergedPr {
  readonly kind: "merged-pr";
  readonly context: PrContext;
  readonly mergedAt: string | null;
}
export type MergeGateReason =
  | "closed-without-merge"
  | "draft-pr"
  | "changes-requested";
export type MergeBlocker =
  | {
      readonly kind: "merge-conflicts";
      readonly pr: PrContext;
      readonly facts: PullRequestFacts;
    }
  | {
      readonly kind: "review-threads";
      readonly pr: PrContext;
      readonly threads: NonEmpty<ReviewThread>;
    }
  | {
      readonly kind: "failing-checks";
      readonly pr: PrContext;
      readonly ci: CiFailing | CiGithubRejected;
    }
  | {
      readonly kind: "merge-gate";
      readonly pr: PrContext;
      readonly reason: MergeGateReason;
    };
export type QueryFailure =
  | {
      readonly kind: "json-parse";
      readonly retryable: true;
      readonly detail: string;
    }
  | {
      readonly kind: "missing-key";
      readonly retryable: true;
      readonly detail: string;
      readonly rawValue?: string;
    }
  | {
      readonly kind: "command-exit";
      readonly retryable: true;
      readonly detail: string;
      readonly code: number;
    }
  | {
      readonly kind: "checks-unavailable";
      readonly retryable: true;
      readonly detail: string;
    }
  | {
      readonly kind: "invalid-context-url";
      readonly retryable: false;
      readonly detail: string;
      readonly rawValue: string;
    };
/**
 * `frontier` names the lowest unmerged PR that is actually waiting, and
 * `pending` is that PR's checks only. Pooling every row's pending under the
 * bottom PR's number misattributed upstack waits to the frontier.
 *
 * This decision serves single and `--stack` mode. Queued mode deliberately
 * reports its own merge frontier instead: when that PR is blocker-free it
 * emits a merge-queue wait that ignores upstack pending, because upstack
 * checks do not block the frontier's merge. That is the Python watcher's
 * contract, not an attribution bug.
 */
export interface WaitingDecision {
  readonly kind: "waiting";
  readonly frontier: PrContext;
  readonly pending: NonEmpty<PendingCheck>;
}
export type PrDecision =
  | { readonly kind: "blocker"; readonly blocker: MergeBlocker }
  | WaitingDecision
  | { readonly kind: "ready"; readonly pr: ReadyPr }
  | { readonly kind: "merged"; readonly pr: MergedPr };
export type StackDecision =
  | { readonly kind: "blocker"; readonly blocker: MergeBlocker }
  | WaitingDecision
  | { readonly kind: "clear"; readonly prs: NonEmpty<ReadyPr | MergedPr> };
export type WatchMode = "single" | "stack" | "queued-stack";
interface EventBase<K extends string, M extends WatchMode = WatchMode> {
  readonly schemaVersion: 1;
  readonly sequence: number;
  readonly observedAt: string;
  readonly mode: M;
  readonly kind: K;
}
interface Progress<K extends string, M extends WatchMode = WatchMode>
  extends EventBase<K, M> {
  readonly terminal: false;
}
interface Terminal<
  K extends string,
  C extends number,
  M extends WatchMode = WatchMode,
> extends EventBase<K, M> {
  readonly terminal: true;
  readonly exitCode: C;
}
export type ProgressVerdict =
  | (Progress<"QUEUE", "queued-stack"> & {
      readonly queue: NonEmpty<PrContext>;
    })
  | (Progress<"STATUS", "stack" | "queued-stack"> & {
      readonly reason: "poll" | "whole-stack-sweep";
      readonly rows: NonEmpty<PrSnapshot>;
    })
  | (Progress<"WAITING"> & {
      readonly frontier: PrContext;
      readonly reason:
        | {
            readonly kind: "pending-checks";
            readonly pending: NonEmpty<PendingCheck>;
          }
        | { readonly kind: "merge-queue"; readonly unmergedCount: number };
    })
  | (Progress<"ADVANCE", "queued-stack"> & {
      readonly merged: PrContext;
      readonly frontier: PrContext;
      readonly remaining: number;
    })
  | (Progress<"RETRY"> & {
      readonly failure: QueryFailure;
      readonly consecutiveFailures: number;
      readonly retryInSeconds: number;
    });
export type BlockerVerdict =
  | (Terminal<"BLOCKER", 2> & {
      readonly blocker: Extract<
        MergeBlocker,
        { readonly kind: "merge-conflicts" }
      >;
    })
  | (Terminal<"BLOCKER", 3> & {
      readonly blocker: Extract<
        MergeBlocker,
        { readonly kind: "review-threads" }
      >;
    })
  | (Terminal<"BLOCKER", 4> & {
      readonly blocker: Extract<
        MergeBlocker,
        { readonly kind: "failing-checks" }
      >;
    })
  | (Terminal<"BLOCKER", 6> & {
      readonly blocker: Extract<MergeBlocker, { readonly kind: "merge-gate" }>;
    })
  | (Terminal<"BLOCKER", 7> & {
      readonly blocker: {
        readonly kind: "status-query";
        readonly failures: number;
        readonly failure: QueryFailure;
      };
    });
export type TimeoutVerdict = Terminal<"TIMEOUT", 5> & {
  readonly reason:
    | {
        readonly kind: "pending-checks";
        readonly pending: NonEmpty<PendingCheck>;
      }
    | { readonly kind: "status-unavailable"; readonly failure: QueryFailure }
    | {
        readonly kind: "queued-stack";
        readonly frontier: PrContext;
        readonly unmergedCount: number;
      };
};
export type TerminalVerdict =
  | (Terminal<"STATUS", 0> & {
      readonly reason: "status-only";
      readonly rows: NonEmpty<PrSnapshot>;
    })
  | (Terminal<"READY", 0, "single" | "stack"> & {
      readonly scope:
        | { readonly kind: "single"; readonly pr: ReadyPr | MergedPr }
        | {
            readonly kind: "stack";
            readonly prs: NonEmpty<ReadyPr | MergedPr>;
          };
    })
  | (Terminal<"COMPLETE", 0, "queued-stack"> & {
      readonly queue: NonEmpty<PrContext>;
      readonly merged: NonEmpty<MergedPr>;
    })
  | BlockerVerdict
  | TimeoutVerdict;
export type WatcherVerdict = ProgressVerdict | TerminalVerdict;
export type ExitCode = TerminalVerdict["exitCode"];
export type QueueTerminalVerdict =
  | Extract<TerminalVerdict, { readonly kind: "COMPLETE" }>
  | BlockerVerdict
  | TimeoutVerdict;
export type ChecksFastPath =
  | { readonly kind: "checks"; readonly checks: readonly Check[] }
  | {
      readonly kind: "unusable";
      readonly exitCode: number;
      readonly stderr: string;
    };
export interface RollupPage {
  readonly checks: readonly Check[];
  readonly endCursor: string | null;
}
export interface RawReviewThread {
  readonly id: string;
  readonly firstComment: ReviewComment | null;
  readonly resolved: boolean;
}
export interface ReviewThreadPage {
  readonly threads: readonly RawReviewThread[];
  readonly endCursor: string | null;
}
export interface GitHubReader {
  originRepo(): Promise<Repository | null>;
  currentPr(pr: PrNumber | null): Promise<PrContext>;
  pullRequest(context: PrContext): Promise<PullRequestFacts>;
  openPullRequests(repository: Repository): Promise<readonly OpenPullRequest[]>;
  checksFastPath(context: PrContext): Promise<ChecksFastPath>;
  checkRollupPage(
    context: PrContext,
    after: string | null
  ): Promise<RollupPage>;
  reviewThreadPage(
    context: PrContext,
    after: string | null
  ): Promise<ReviewThreadPage>;
  commitRollups(context: PrContext): Promise<readonly CommitRollup[]>;
}
export interface PollingOptions {
  readonly interval: number;
  readonly sweepInterval: number;
  readonly timeout: number;
  readonly maxQueryErrors: number;
  readonly allowDraft: boolean;
}
