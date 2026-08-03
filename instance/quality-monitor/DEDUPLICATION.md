# Deduplication Strategy

The Quality Monitor uses a **triple-layer defense** to ensure each PR only receives one Judge Dredd comment, ever.

## Layer 1: Preflight Filtering

**Location:** `preflight/01-scan-prs-for-violations.py`

**Function:** `has_bot_commented(org_repo, pr_number)`

**How it works:**
- Fetches existing comments on the PR using `gh pr view --json comments`
- Checks each comment's body for bot signatures:
  - "Rehor Quality Monitor"
  - "I AM THE LAW"
- Checks comment author for bot patterns:
  - Contains `[bot]`
  - Contains `rehor`
- Returns `True` if bot signature found
- Preflight skips PRs where this returns `True`

**Why:** Prevents wasted API calls and AI tokens on PRs we've already commented on.

## Layer 2: Memory Check (Failsafe)

**Location:** `CLAUDE.md` workflow instructions

**When:** Before posting a comment in the AI decision loop

**How it works:**
```
memory_search(f"quality-comment {repo} PR #{pr_number}")
```
- Searches memory for existing comment records
- If results found → skip this PR, select next one
- Acts as a failsafe in case Layer 1 missed something

**Why:** Double-checks even if preflight filtering had issues. Protects against edge cases like:
- Comment body was edited and signature removed
- API race conditions
- Preflight cache issues

## Layer 3: Memory Recording

**Location:** Post-comment action in workflow

**When:** Immediately after posting a comment

**How it works:**
```python
memory_store(
    category="action_taken",
    tags=["quality-comment", "dredd", repo],
    content=f"""Posted quality comment on {repo} PR #{pr_number}
URL: {pr_url}
Commented at: {timestamp}
Violations: {violation_summary}
This PR has been commented on - do not comment again.
"""
)
```

**Why:** Creates a permanent, searchable record that:
- Persists across workflow runs
- Can be queried by Layer 2
- Provides audit trail of all comments posted
- Survives even if the GitHub comment is deleted

## Why Three Layers?

Each layer serves a different purpose:

1. **Performance** (Layer 1): Don't waste resources on already-commented PRs
2. **Reliability** (Layer 2): Catch edge cases that slip through Layer 1
3. **Auditability** (Layer 3): Create permanent record for tracking and learning

## Example Flow

```
PR #123 merged
    ↓
Preflight runs
    ↓
Check: has_bot_commented(PR #123)?
    ↓ NO
Include PR #123 in results
    ↓
AI workflow starts
    ↓
Check: memory_search("quality-comment PR #123")?
    ↓ NO
Post Judge Dredd comment
    ↓
Record: memory_store(action_taken: "commented on PR #123")
    ↓
Next run:
    ↓
Check: has_bot_commented(PR #123)?
    ↓ YES (finds the comment we posted)
Skip PR #123 ← DEDUPLICATED
```

## Testing Deduplication

To verify deduplication is working:

1. Run workflow on a PR with violations (should comment)
2. Run workflow again (should skip the PR)
3. Check memory: `memory_list category:action_taken`
4. Verify PR comments show only one bot comment
5. Check preflight output (should say "No violations found" or show different PRs)

## Troubleshooting

### PR getting commented on multiple times?

Check each layer:

1. **Layer 1**: Does `has_bot_commented()` return True?
   - Test: `gh pr view <NUMBER> --json comments`
   - Verify bot signature in comment body
   - Check author field

2. **Layer 2**: Is memory search finding the record?
   - Test: Search memory for the PR number
   - Check tags and category match

3. **Layer 3**: Is memory being stored after posting?
   - Check workflow logs
   - Verify `memory_store` is called
   - Check memory server connectivity

### False positives (skipping PRs that should be commented)?

- Check if another bot has similar signatures
- Verify the bot signature strings are unique
- Review memory search query syntax
- Check for stale memory records

## Maintenance

- **Memory cleanup**: Old `action_taken` records can be archived after 90 days
- **Signature updates**: If changing bot comment format, update `has_bot_commented()` signatures
- **Memory search**: Keep tag schema consistent (`quality-comment`, `dredd`, repo name)
