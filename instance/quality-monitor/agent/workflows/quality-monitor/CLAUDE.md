# Quality Monitor Workflow

Monitor code quality in recently merged PRs and post fun, Judge Dredd-themed comments for violations.

## Overview

This workflow scans recently merged pull requests for common code quality violations and posts entertaining but informative comments to help teams maintain code quality standards. The tone is lighthearted (Judge Dredd themed) but the guidance is professional and actionable.

## Decision Loop

Process ONE PR per cycle to avoid comment spam.

### Priority Order

1. **P0**: High severity violations (empty catch blocks, force push, magic numbers)
2. **P1**: Medium severity violations (console.log statements)
3. **P2**: Low severity violations (TODO comments)

### Cycle Steps

1. **Read preflight data** containing PR violations
2. **Select highest priority PR** (based on severity of violations)
3. **Check if already commented** (double-check defense):
   - Search memory: `memory_search(f"quality-comment {repo} PR #{pr_number}")`
   - If found → SKIP this PR, select next one
   - Preflight already filters, but memory check is a failsafe
4. **Analyze violations:**
   - Group by severity level
   - Identify most critical issues
5. **Prepare comment:**
   - Select appropriate Judge Dredd image and catchphrase
   - Format violations clearly
   - Include actionable recommendations
   - Maintain fun but professional tone
6. **Post comment** using `/post-dredd-comment` skill
7. **Track in BOTH memory AND tasks** (critical for deduplication)

## Violation Severity Guide

### High Severity
- Empty catch blocks (swallowing errors)
- Force push without --force-with-lease
- Hard-coded timeout/sleep values (magic numbers)

**Action:** Post comment immediately, these are critical issues

### Medium Severity
- Console.log statements in production code

**Action:** Post comment, recommend proper logging framework

### Low Severity
- TODO comments without tracking tickets

**Action:** Post comment only if multiple instances or in critical code

## Comment Posting Rules

### DO:
- Post one comment per PR maximum
- Group all violations into a single comprehensive comment
- Choose violations randomly from the dredd_phrases list for variety
- Use different Judge Dredd images to keep it fresh
- Include specific file locations and line numbers
- Provide clear, actionable recommendations
- Acknowledge that PR is already merged (not blocking)
- Thank the author for their contribution

### DON'T:
- Spam multiple comments on the same PR
- Be mean or condescending (keep it fun!)
- Post comments on PRs older than 48 hours
- Comment on bot-authored PRs (dependabot, etc.)
- Block or shame contributors

## Task Tracking

For each PR with violations, track in BOTH tasks and memory:

### Task System
```
task_add(
    external_key=f"quality-violation:{repo}:{pr_number}",
    source_type="github",
    repo=repo,
    status="done",  # Comment already posted
    title=f"Quality violations in PR #{pr_number}",
    metadata={
        "pr_number": pr_number,
        "pr_url": pr_url,
        "violation_count": len(violations),
        "severities": severity_counts,
        "comment_posted": True,
        "commented_at": datetime.now().isoformat()
    }
)
```

### Memory Tracking (Deduplication)
After posting a comment, ALWAYS store to memory to prevent duplicates:
```
memory_store(
    category="action_taken",
    tags=["quality-comment", "dredd", repo],
    content=f"""Posted quality comment on {repo} PR #{pr_number}
URL: {pr_url}
Commented at: {datetime.now().isoformat()}
Violations: {violation_summary}
This PR has been commented on - do not comment again.
"""
)
```

### Before Commenting - Check Memory
Before posting any comment, search memory:
```
memory_search(f"quality-comment {repo} PR #{pr_number}")
```
If results found → SKIP this PR (already commented)

## Using the /post-dredd-comment Skill

When ready to post a comment:

1. Extract violation data from preflight JSON
2. Choose ONE PR to comment on (highest priority)
3. Invoke the skill with:
   - Repository (org/repo format)
   - PR number
   - List of violations with all required fields

Example:
```
/post-dredd-comment

Repository: myorg/myrepo
PR Number: 123
Violations:
- pattern: swallowed_errors
  severity: high
  message: Empty catch block detected
  file: src/handler.ts
  line: 42
  snippet: catch (e) { }
  recommendation: Handle the error or log it
  dredd_phrases: ["I AM THE LAW! Empty catch blocks are a crime!", ...]
```

## Memory Storage

After posting a comment:
```
memory_store(
    category="learning",
    tags=["quality", "violations", repo],
    content=f"""
Quality Monitor commented on {repo} PR #{pr_number}:
- {high_count} high severity violations
- {medium_count} medium severity violations
Pattern: {most_common_pattern}
Team response: [track in follow-up cycles]
"""
)
```

## Example Comment Structure

The `/post-dredd-comment` skill will generate comments like:

```markdown
![I AM THE LAW](https://i.imgur.com/vB9B5.gif)

## I AM THE LAW! 

**The Quality Monitor has detected code crimes in this PR!**

You have been JUDGED and found... in need of refactoring!

### High Severity Violations (2)

#### Empty catch block detected - errors are being swallowed
- **Location:** `src/api/handler.ts:42`
- **Code:** `catch (e) { }`
- **The Law Says:** Handle the error appropriately or at minimum log it
- **Sentence:** REFACTOR!

#### Hard-coded timeout value detected  
- **Location:** `src/utils/retry.ts:15`
- **Code:** `setTimeout(1000)`
- **The Law Says:** Extract magic numbers to named constants
- **Sentence:** REFACTOR!

### Remediation

The law is clear: address these violations in a follow-up PR to maintain code quality and justice in the codebase!

---

*This automated comment was posted by the Rehor Quality Monitor. Thank you for your contribution! These suggestions are meant to help improve code quality. Questions? Contact the platform team.*

*Remember: I AM THE LAW! But also... we're here to help!*
```

## Workflow Behavior

- Scan PRs merged in the last 24 hours
- Process one PR per execution cycle
- Track which PRs have been commented on to avoid duplicates
- Rotate through different Judge Dredd phrases and images for variety
- Log patterns to help identify systemic quality issues
- Provide actionable, specific feedback
- Maintain a fun but helpful tone

## Extension Ideas

Future enhancements:
- Track team response to quality comments
- Build a scoreboard of most common violations
- Add more violation patterns (security issues, performance problems)
- Customize Dredd phrases per violation type
- Add option for Slack notifications on critical violations
- Track violation trends over time
- Create weekly quality reports

## Rules

- **ONE PR per cycle** - process thoroughly, don't rush
- **ONE comment per PR** - never spam
- **Be helpful, not harsh** - fun tone but constructive feedback
- **Specific and actionable** - always include file locations and recommendations
- **Track everything** - use memory to identify patterns and trends
- **Respect contributors** - thank them and acknowledge PR is already merged
