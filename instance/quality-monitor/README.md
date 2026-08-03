# Quality Monitor Instance

A fun and helpful Rehor bot instance that monitors code quality in recently merged PRs and posts Judge Dredd-themed comments when violations are detected.

## Overview

The Quality Monitor scans PRs merged in the last 24 hours for common code quality issues like:
- Empty catch blocks (swallowed errors)
- Console.log statements in production code
- TODO comments without tracking
- Hard-coded timeout values (magic numbers)
- Force push without --force-with-lease

When violations are found, it posts entertaining but informative comments using Judge Dredd imagery and catchphrases.

## Features

- **Automated PR Scanning**: Monitors recently merged PRs across configured repositories
- **Judge Dredd Themed Comments**: Fun but professional feedback with random phrases and images
- **Severity-Based Prioritization**: Focuses on high severity issues first
- **No Spam**: Triple-layer deduplication ensures only one comment per PR, ever
  - Layer 1: Preflight checks PR comments for bot signature
  - Layer 2: AI workflow searches memory before commenting
  - Layer 3: Memory stores comment record after posting
- **Actionable Feedback**: Specific file locations, code snippets, and fix recommendations
- **Memory Tracking**: Learns patterns over time to identify systemic issues

## Configuration

### Project Repositories

Edit `project-repos.json` to configure which repositories to monitor:

```json
{
  "repo-name": {
    "upstream": "https://github.com/org/repo.git",
    "host": "github"
  }
}
```

### Violation Patterns

Violation patterns are defined in the preflight script. To add new patterns, edit:
`agent/workflows/quality-monitor/preflight/01-scan-prs-for-violations.py`

Each pattern includes:
- `regex`: Pattern to match in code diffs
- `severity`: high/medium/low
- `message`: Description of the violation
- `dredd_phrases`: List of Judge Dredd catchphrases
- `recommendation`: How to fix it

### Scheduling

The workflow is designed to run on a schedule via KEDA cron scaler. Configure in your deployment template:

```yaml
triggers:
- type: cron
  metadata:
    timezone: "America/New_York"
    start: "0 9 * * 1-5"    # Daily at 9 AM weekdays
    end: "5 9 * * 1-5"      # 5-min window
    desiredReplicas: "1"
```

## How It Works

### 1. Preflight Scan

The preflight script (`01-scan-prs-for-violations.py`):
- Uses `last_merge_check_scan` from state to determine scan window (self-correcting)
- Fallback: scans last 48 hours if no previous scan timestamp exists
- Fetches PRs merged since last scan
- Checks if bot has already commented (avoids duplicates)
- Gets the diff for each PR
- Scans added lines for violation patterns
- Updates state with current timestamp for next run
- Returns "skip" if no violations found, "start" with details if violations detected

**Smart Time Window**: The scan window adapts automatically based on the last successful scan, so it works correctly regardless of KEDA schedule changes or missed runs.

### 2. AI Decision Loop

When violations are found, the bot:
- Reads the preflight violation data
- Selects the highest priority PR (based on violation severity)
- **Double-checks memory** to ensure we haven't commented (failsafe layer)
- Formats a Judge Dredd-themed comment
- Posts the comment using `/post-dredd-comment` skill
- **Records in memory** with `action_taken` category and PR details
- Tracks the violation in task system

### Deduplication Strategy

Three layers prevent duplicate comments:

1. **Preflight Layer**: `has_bot_commented()` function checks existing PR comments for bot signatures before including PR in results
2. **Memory Check**: AI workflow searches memory for `quality-comment {repo} PR #{number}` before posting
3. **Memory Recording**: After posting, creates permanent memory record with `action_taken` category

This ensures that even if the workflow runs multiple times, each PR only gets commented on once.

### 3. Comment Posted

Example comment structure:
```markdown
![I AM THE LAW](https://i.imgur.com/dredd.gif)

## I AM THE LAW!

**GUILTY of code crimes!** Empty catch blocks detected!

### High Severity Violations
- Location: src/handler.ts:42
- Code: catch (e) { }
- Fix: Handle the error or log it

**Sentence: REFACTOR!**
```

## Skills

### `/post-dredd-comment`

Posts a Judge Dredd-themed quality violation comment to a PR.

**Inputs:**
- Repository (org/repo)
- PR number  
- Violation details

**Output:**
- Posted GitHub PR comment
- Updated task tracking

## Development

### Testing Locally

Run the test suite:
```bash
cd /path/to/rehor
./instance/quality-monitor/run-tests.sh
```

Or run tests manually with pytest:
```bash
cd /path/to/rehor
pytest instance/quality-monitor/agent/workflows/quality-monitor/preflight/tests/ -v
```

Test the preflight script manually:
```bash
cd /path/to/rehor
export PYTHONPATH=presets/shared/preflight:.claude/skills
export GH_TOKEN=your_token
python3 instance/quality-monitor/agent/workflows/quality-monitor/preflight/01-scan-prs-for-violations.py
```

Or use the convenience script:
```bash
./instance/quality-monitor/test-preflight.sh
```

### Adding New Violation Patterns

1. Edit the preflight script
2. Add pattern to `VIOLATION_PATTERNS` dict:
```python
"pattern_name": {
    "regex": r'your-regex-here',
    "severity": "high",  # or medium/low
    "message": "Description",
    "dredd_phrases": [
        "I AM THE LAW! Your violation description!",
        "GUILTY! Alternative phrase!",
    ],
    "recommendation": "How to fix it"
}
```

3. Test the pattern against sample code
4. Deploy and monitor

### Adding More Judge Dredd Images

Edit the `DREDD_IMAGES` list in the preflight script:
```python
DREDD_IMAGES = [
    "https://i.imgur.com/vB9B5.gif",
    "https://your-image-url.gif",
    # Add more!
]
```

## Token Efficiency

The preflight script does all the heavy lifting (git operations, pattern matching) without using AI tokens. The AI is only invoked when violations are found, making this workflow very token-efficient.

**Cost profile:**
- No violations found: 0 AI tokens (just preflight script execution)
- Violations found: ~500-2000 tokens per PR processed

## Customization

### Tone Adjustment

Edit `CLAUDE.md` to adjust the tone:
- More serious: Reduce Judge Dredd references, focus on technical details
- More fun: Add more phrases, gifs, and personality
- Custom theme: Replace Judge Dredd with another theme (RoboCop? Terminator?)

### Violation Thresholds

Adjust when comments are posted:
- Only high severity: Change priority order in CLAUDE.md
- Require multiple violations: Add threshold check in workflow
- Different severities: Modify VIOLATION_PATTERNS in preflight script

### Notification Channels

Add Slack notifications:
- Configure SLACK_WEBHOOK_URL environment variable
- Use `/slack-notify` skill in CLAUDE.md workflow
- Send notifications for high-severity violations

## Maintenance

### Monitor Bot Behavior

Check bot logs to ensure:
- Preflight scripts run successfully  
- PRs are being scanned
- Comments are posted correctly
- No spam or duplicate comments

### Track Patterns

Use memory to identify:
- Most common violations
- Repositories with frequent issues
- Teams that need additional training
- Whether violations decrease over time

### Update Patterns

As coding standards evolve:
- Add new violation patterns
- Remove obsolete ones
- Adjust severity levels
- Update recommendations

## Future Enhancements

Potential additions:
- **Weekly reports**: Aggregate violations and send summary
- **Violation trends**: Track improvements over time
- **Custom images**: Per-team or per-repo custom reaction images
- **Security patterns**: Add security-focused violation detection
- **Performance patterns**: Detect performance anti-patterns
- **Auto-fix PRs**: Create follow-up PRs to fix simple violations
- **Gamification**: Scoreboard of teams with best code quality

## Troubleshooting

### Preflight Not Finding PRs
- Check GH_TOKEN is configured
- Verify repository access permissions
- Confirm repos in project-repos.json are correct
- Check state file: `data/preflight-state.json` contains `last_merge_check_scan`
- First run: Uses 48-hour fallback window (this is normal)
- Invalid timestamp in state: Falls back to 48-hour window with warning in logs

### No Comments Posted
- Verify bot has permission to comment on PRs
- Check task tracking - is it hitting capacity?
- Review bot logs for errors
- Ensure /post-dredd-comment skill is working

### Too Many Comments
- Check deduplication logic in CLAUDE.md
- Verify "ONE PR per cycle" rule is being followed
- Adjust priority order to focus on critical issues

### False Positives
- Refine regex patterns to be more specific
- Add file/path exclusions (e.g., test files, generated code)
- Adjust severity levels
- Add pattern exceptions

## Contributing

To improve the Quality Monitor:

1. Test new patterns thoroughly
2. Maintain the fun but helpful tone
3. Keep comments actionable and specific
4. Document pattern changes
5. Monitor impact on teams

## License

Part of the Rehor project.
