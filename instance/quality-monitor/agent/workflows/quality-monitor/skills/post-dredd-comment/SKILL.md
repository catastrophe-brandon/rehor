# Post Dredd Comment

Post a fun Judge Dredd-themed comment to a PR that has quality violations.

## Purpose

When code quality violations are detected in a merged PR, this skill posts an entertaining but informative comment to the PR explaining the violation and providing guidance on how to fix it.

## When to Use

Use this skill after detecting quality violations in a PR. It should:
- Highlight the specific violation(s) found
- Use Judge Dredd-themed language and imagery
- Provide actionable remediation steps
- Maintain a fun but professional tone

## Inputs

The skill expects the following information:
- `repo`: Repository name (org/repo format)
- `pr_number`: Pull request number
- `violations`: List of violation objects containing:
  - `pattern`: Type of violation
  - `severity`: high/medium/low
  - `message`: Description of the violation
  - `file`: File path where violation was found
  - `line`: Line number
  - `snippet`: Code snippet
  - `recommendation`: How to fix it
  - `dredd_phrases`: List of Judge Dredd catchphrases to choose from

## Comment Format

The comment should include:
1. A Judge Dredd image/gif
2. A dramatic Judge Dredd catchphrase appropriate to the violation
3. Clear description of violations found
4. Specific file locations and code snippets
5. Actionable recommendations for fixes
6. Maintain a lighthearted but informative tone

## Example Comment

```markdown
![I AM THE LAW](https://i.imgur.com/vB9B5.gif)

## I AM THE LAW!

**GUILTY of code crimes!** The Quality Monitor has detected violations in this PR:

### High Severity Violations

**Empty catch block detected - errors are being swallowed**
- Location: `src/api/handler.ts:42`
- Code: `catch (e) { }`
- **The Law Says:** Handle the error appropriately or at minimum log it

**Sentence:** REFACTOR!

---

*This comment was posted by the Rehor Quality Monitor. These violations were detected in the merged code. While the PR is already merged, please consider addressing these issues in a follow-up PR.*

*Remember: I am the law! Follow quality standards for justice!*
```

## Implementation Notes

- Use `gh pr comment <pr_number> --repo <repo> --body <comment>`
- Choose a random Dredd phrase from the violation's dredd_phrases list
- Choose a random Dredd image from the available options
- Group violations by severity (high, medium, low)
- Limit to top 5 violations if there are many
- Include a link to quality standards documentation if available
- Only post one comment per PR (don't spam)

## Success Criteria

- Comment is posted successfully to the PR
- Comment is informative and actionable
- Tone is fun but professional
- All violation details are clearly presented
- GitHub CLI command succeeds
- **CRITICAL**: Comment recorded in memory to prevent duplicates

## After Posting Comment

ALWAYS record in memory immediately after posting:

```
memory_store(
    category="action_taken",
    tags=["quality-comment", "dredd", repo_name],
    content=f"""Posted quality comment on {repo} PR #{pr_number}
URL: {pr_url}
Commented at: {timestamp}
Violations: {violation_count} ({high} high, {medium} medium, {low} low)
This PR has been commented on - do not comment again.
"""
)
```

This creates a permanent record that prevents duplicate comments even if the workflow runs multiple times on the same PR.
