---
name: soul-extractor
description: Extract a reviewer's code review soul from GitHub PR history. Takes a GitHub username, list of repos, and time range. Analyzes PR reviews where the person left 5+ comments, reconstructs code context, and extracts core beliefs, ground truths, and review patterns. Outputs a reviewer agent definition that can be used as a subagent_type for code reviews. Use when you want to clone a reviewer's style, create a review agent from someone's PR history, or extract engineering principles from review behavior. Trigger with /soul-extract.
trigger: /soul-extract
---

# Soul Extractor

Turn a GitHub reviewer's PR history into a reusable code review agent that captures their soul — core beliefs, ground truths, review patterns, communication style, and decision framework.

The output is an agent definition at `<agent-directory>/{username}-reviewer.md` that can be used as `subagent_type` for code reviews, matching the format of existing reviewer agents like `david` and `steve`.

Resolve `<agent-directory>` from the active application’s supported custom-agent configuration before writing. Match its existing agent-file format. If it has no custom-agent directory, save the reviewer definition in the current project’s `agents/` directory.

## Usage

```
/soul-extract <username> <repos> [--since YYYY-MM-DD] [--until YYYY-MM-DD]
```

- `<username>`: GitHub login of the reviewer
- `<repos>`: Comma-separated list of repos (format: `owner/repo`)
- `--since`: Start date (default: 1 year ago from today)
- `--until`: End date (default: today)

Examples:
```
/soul-extract torvalds torvalds/linux --since 2024-06-01 --until 2024-12-31
/soul-extract myreviewer org/repo1,org/repo2,org/repo3
```

## What You Must Do When Invoked

Follow these steps in order. Do not skip steps.

### Step 0 — Parse and validate inputs

Parse command arguments:
- Extract `USERNAME` (required, first positional arg)
- Extract `REPOS` as a comma-separated list (required, second positional arg)
- Extract `SINCE` date (default: 1 year ago, format: YYYY-MM-DD)
- Extract `UNTIL` date (default: today, format: YYYY-MM-DD)

Validate:

```bash
# Check gh auth
gh auth status 2>&1 | head -3

# Check each repo is accessible
for REPO in REPO_LIST; do
  gh api "/repos/${REPO}" --jq '.full_name' 2>/dev/null || echo "ERROR: Cannot access $REPO"
done
```

Replace `REPO_LIST` with the actual space-separated list of repos. If any repo is inaccessible, warn the user and exclude it. If ALL repos fail, stop.

Check rate limit before starting:
```bash
gh api /rate_limit --jq '.resources.core | "Rate limit: \(.remaining)/\(.limit) remaining, resets at \(.reset | strftime("%H:%M:%S"))"'
```

If remaining < 500, warn the user that the extraction may hit rate limits.

### Step 1 — Collect review comments

For each repo, fetch all review comments by the user in the time range.

```bash
mkdir -p soul-extract-out

for REPO in REPO_LIST; do
  REPO_SLUG=$(echo "$REPO" | tr '/' '_')
  echo "Fetching review comments from $REPO by USERNAME..."

  gh api "/repos/${REPO}/pulls/comments?since=${SINCE}T00:00:00Z&per_page=100&sort=created&direction=desc" \
    --paginate \
    --jq "[.[] | select(.user.login == \"USERNAME\" and .created_at >= \"${SINCE}\" and .created_at <= \"${UNTIL}T23:59:59Z\") | {
      id: .id,
      pr_number: (.pull_request_url | split(\"/\") | last | tonumber),
      path: .path,
      body: .body,
      diff_hunk: .diff_hunk,
      created_at: .created_at,
      commit_id: .commit_id,
      in_reply_to_id: .in_reply_to_id,
      html_url: .html_url
    }]" > "soul-extract-out/${REPO_SLUG}_raw.jsonl"

  # Flatten paginated arrays
  cat "soul-extract-out/${REPO_SLUG}_raw.jsonl" | jq -s 'flatten | unique_by(.id)' > "soul-extract-out/${REPO_SLUG}_comments.json"

  TOTAL=$(jq length "soul-extract-out/${REPO_SLUG}_comments.json")
  echo "  $REPO: $TOTAL review comments found"
done
```

Replace `USERNAME`, `REPO_LIST`, `SINCE`, `UNTIL` with actual values.

### Step 2 — Group by PR, filter qualifying PRs

Keep only PRs where the reviewer left 5 or more comments.

```bash
for REPO in REPO_LIST; do
  REPO_SLUG=$(echo "$REPO" | tr '/' '_')

  jq --arg repo "$REPO" '
    group_by(.pr_number) |
    map(select(length >= 5)) |
    map({
      pr_number: .[0].pr_number,
      repo: $repo,
      comment_count: length,
      comments: .
    })
  ' "soul-extract-out/${REPO_SLUG}_comments.json" > "soul-extract-out/${REPO_SLUG}_qualifying.json"

  PR_COUNT=$(jq length "soul-extract-out/${REPO_SLUG}_qualifying.json")
  COMMENT_COUNT=$(jq '[.[].comment_count] | add // 0' "soul-extract-out/${REPO_SLUG}_qualifying.json")
  echo "$REPO: $PR_COUNT qualifying PRs, $COMMENT_COUNT comments"
done

# Merge all repos into one file
jq -s 'flatten' soul-extract-out/*_qualifying.json > soul-extract-out/all_qualifying.json
TOTAL_PRS=$(jq length soul-extract-out/all_qualifying.json)
TOTAL_COMMENTS=$(jq '[.[].comment_count] | add // 0' soul-extract-out/all_qualifying.json)
echo ""
echo "Total: $TOTAL_PRS qualifying PRs with $TOTAL_COMMENTS comments"
```

Print a summary:
```
Qualifying PRs (5+ review comments from USERNAME):
  owner/repo1: X PRs, Y comments
  owner/repo2: X PRs, Y comments
  Total: X PRs, Y comments
```

If total qualifying PRs is 0, stop: "No PRs found with 5+ review comments from USERNAME in the given time range. Try a wider date range or checking the username."

If total qualifying PRs > 100, warn the user and cap at the most recent 100:
```bash
jq 'sort_by(-.comments[0].created_at // "") | .[:100]' soul-extract-out/all_qualifying.json > soul-extract-out/all_qualifying_capped.json
mv soul-extract-out/all_qualifying_capped.json soul-extract-out/all_qualifying.json
echo "Capped to 100 most recent qualifying PRs to stay within API limits"
```

### Step 3 — Enrich with PR context and thread resolution

For each qualifying PR, fetch metadata, review verdicts, and full thread context. This tells us:
- **Code at comment time**: already in `diff_hunk`
- **What happened after**: thread replies, PR merge status, review verdict

```bash
# Get all qualifying PR numbers per repo
jq -r '.[] | "\(.repo) \(.pr_number)"' soul-extract-out/all_qualifying.json | sort -u | while read REPO PR_NUM; do
  REPO_SLUG=$(echo "$REPO" | tr '/' '_')

  echo "Enriching $REPO#$PR_NUM..."

  # 1. PR metadata
  PR_META=$(gh api "/repos/${REPO}/pulls/${PR_NUM}" --jq '{
    number: .number,
    title: .title,
    state: .state,
    merged: (.merged // false),
    body: ((.body // "")[0:500]),
    changed_files: .changed_files,
    additions: .additions,
    deletions: .deletions,
    user: .user.login,
    merged_at: .merged_at,
    html_url: .html_url
  }' 2>/dev/null)

  # 2. Review verdicts by the user
  VERDICTS=$(gh api "/repos/${REPO}/pulls/${PR_NUM}/reviews" --paginate --jq "[.[] | select(.user.login == \"USERNAME\") | {
    state: .state,
    body: ((.body // \"\")[0:300]),
    submitted_at: .submitted_at
  }]" 2>/dev/null | jq -s 'flatten')

  # 3. ALL comments on this PR (for thread context)
  ALL_COMMENTS=$(gh api "/repos/${REPO}/pulls/${PR_NUM}/comments" --paginate --jq "[.[] | {
    id: .id,
    user: .user.login,
    body: .body,
    diff_hunk: .diff_hunk,
    path: .path,
    in_reply_to_id: .in_reply_to_id,
    created_at: .created_at,
    commit_id: .commit_id
  }]" 2>/dev/null | jq -s 'flatten | unique_by(.id)')

  # 4. Build enriched record
  echo "$PR_META" | jq --arg repo "$REPO" \
    --argjson verdicts "$VERDICTS" \
    --argjson all_comments "$ALL_COMMENTS" '
    . + {
      repo: $repo,
      review_verdicts: $verdicts,
      review_verdict_final: ([$verdicts[] | .state] | last // "COMMENTED"),
      all_comments: $all_comments
    }
  ' >> "soul-extract-out/enriched_prs.jsonl"

done
```

Replace `USERNAME` with the actual username.

Now build the final enriched dataset — reviewer comments with thread replies:

```bash
jq -s '.' soul-extract-out/enriched_prs.jsonl > soul-extract-out/enriched_prs.json

# For each PR, extract reviewer's comments with their reply threads
jq --arg user "USERNAME" '
  [.[] | . as $pr | {
    repo: .repo,
    pr_number: .number,
    pr_title: .title,
    pr_author: .user,
    pr_merged: .merged,
    pr_html_url: .html_url,
    review_verdict: .review_verdict_final,
    review_body: ((.review_verdicts // []) | map(.body) | map(select(. != "")) | join(" | ")),
    reviewer_comments: [
      .all_comments[] |
      select(.user == $user and .in_reply_to_id == null) |
      . as $comment |
      {
        path: .path,
        diff_hunk: .diff_hunk,
        body: .body,
        created_at: .created_at,
        thread: [$pr.all_comments[] | select(.in_reply_to_id == $comment.id) | {user, body, created_at}]
      }
    ]
  } | select((.reviewer_comments | length) >= 5)]
' soul-extract-out/enriched_prs.json > soul-extract-out/analysis_input.json

FINAL_COUNT=$(jq length soul-extract-out/analysis_input.json)
echo "Enriched dataset ready: $FINAL_COUNT PRs with full thread context"
```

Replace `USERNAME` with the actual username.

Print a progress summary:
```
Data collection complete:
  Repos scanned: N
  Qualifying PRs: N (5+ review comments)
  Total review comments: N
  With thread replies: N
  PRs merged after review: N
  Reviews requesting changes: N
  Reviews approving: N
```

### Step 4 — Dispatch analysis subagents

Split the enriched PRs into chunks of ~15-20 and dispatch parallel subagents.

**MANDATORY: Use the Agent tool here. Do NOT analyze the review data yourself — subagents provide parallel processing and independent analysis perspectives.**

**Step 4a — Split into chunks**

Read `soul-extract-out/analysis_input.json`. Count total PRs. Split into chunks of 15-20 PRs each. Write each chunk to `soul-extract-out/chunk_NN_input.json`.

```bash
TOTAL=$(jq length soul-extract-out/analysis_input.json)
CHUNK_SIZE=15
CHUNKS=$(( (TOTAL + CHUNK_SIZE - 1) / CHUNK_SIZE ))
echo "Splitting $TOTAL PRs into $CHUNKS chunks of ~$CHUNK_SIZE"

for i in $(seq 0 $((CHUNKS - 1))); do
  START=$((i * CHUNK_SIZE))
  jq ".[$START:$((START + CHUNK_SIZE))]" soul-extract-out/analysis_input.json > "soul-extract-out/chunk_$(printf '%02d' $i)_input.json"
  COUNT=$(jq length "soul-extract-out/chunk_$(printf '%02d' $i)_input.json")
  echo "  Chunk $i: $COUNT PRs"
done
```

**Step 4b — Dispatch ALL subagents in a single message**

Call the Agent tool multiple times IN THE SAME RESPONSE — one per chunk. Use `subagent_type="general-purpose"`. Each subagent gets this prompt (substitute CHUNK_NUM, TOTAL_CHUNKS, USERNAME, and the chunk file path):

```
You are analyzing code review comments from GitHub user USERNAME to extract their review personality.

Read the file soul-extract-out/chunk_CHUNK_NUM_input.json. It contains CHUNK_SIZE PRs with the reviewer's comments, code context (diff_hunk), and thread replies.

For each PR, examine:
1. The diff_hunk — this is the code the reviewer was looking at
2. The reviewer's comment body — what they said about it
3. Thread replies — how the discussion resolved (was feedback accepted?)
4. The review verdict — did they approve or request changes?

Extract the following from this batch. Be SPECIFIC and EVIDENCE-BASED — generic advice like "write clean code" is useless. We want this person's UNIQUE perspective.

Output JSON matching this exact schema. Write it to soul-extract-out/analysis_chunk_CHUNK_NUM.json:

{
  "explicit_rules": [
    {
      "rule": "One sentence stating the rule",
      "evidence": ["Direct quote from comment 1", "Direct quote from comment 2"],
      "category": "correctness|style|architecture|security|performance|testing|naming|error-handling|simplicity|api-design",
      "strength": "always|usually|sometimes",
      "adopted": true  // was this feedback typically accepted by PR authors?
    }
  ],
  "implicit_patterns": [
    {
      "pattern": "One sentence describing the pattern",
      "evidence": ["Quote 1", "Quote 2"],
      "category": "...",
      "strength": "...",
      "adopted": true
    }
  ],
  "anti_patterns_flagged": [
    {
      "anti_pattern": "Code pattern they flag as problematic",
      "typical_comment": "How they typically phrase this feedback",
      "category": "...",
      "frequency": 3
    }
  ],
  "approved_patterns": [
    {
      "pattern": "Code pattern they explicitly approve or praise",
      "typical_comment": "How they phrase approval",
      "category": "...",
      "frequency": 2
    }
  ],
  "communication_style": {
    "tone": "direct|gentle|socratic|terse|educational|...",
    "uses_questions": true,
    "provides_alternatives": true,
    "characteristic_phrases": ["exact phrases they use repeatedly"],
    "severity_signals": ["how they signal blocking vs optional"],
    "humor_or_personality": ["any distinctive personality traits in comments"]
  },
  "flexibility_signals": [
    {
      "context": "What the discussion was about",
      "signal": "How they showed flexibility (e.g., 'up to you', backed down)"
    }
  ],
  "conviction_signals": [
    {
      "context": "What the discussion was about",
      "signal": "How they showed conviction (e.g., insisted despite pushback)"
    }
  ],
  "domain_expertise": [
    {
      "domain": "Name of the domain/area",
      "evidence": "What kind of files/code they review deeply in this area",
      "depth": "deep|moderate|surface"
    }
  ],
  "languages_reviewed": ["go", "python", "typescript", "..."],
  "quoted_principles": [
    "Direct quotes that sound like principles or maxims from their comments"
  ]
}

Rules:
- Every finding MUST have evidence — direct quotes from the reviewer's actual comments
- Prefer specific rules over generic ones. "Use errors.Is() instead of string matching" > "Handle errors properly"
- Look for CONSISTENCY — patterns that repeat across multiple PRs are the real beliefs
- Note when the reviewer's feedback was adopted vs ignored (thread replies tell you this)
- Capture their EXACT phrasing for characteristic phrases — this is their voice
- If you find fewer than 3 of any category, that's fine — quality over quantity
- Maximum 10 items per category — focus on the strongest signals
```

**Step 4c — Collect results**

After all subagents complete, verify each chunk file exists:

```bash
for i in $(seq 0 $((CHUNKS - 1))); do
  FILE="soul-extract-out/analysis_chunk_$(printf '%02d' $i).json"
  if [ -f "$FILE" ] && jq empty "$FILE" 2>/dev/null; then
    echo "Chunk $i: OK"
  else
    echo "WARNING: Chunk $i missing or invalid"
  fi
done
```

If more than half the chunks failed, stop and tell the user to re-run.

### Step 5 — Synthesize the soul

Read all `soul-extract-out/analysis_chunk_*.json` files. This is where YOU (the main agent) do the synthesis — not a subagent.

**Step 5a — Merge all analyses**

```bash
jq -s '{
  explicit_rules: [.[].explicit_rules[]] | unique_by(.rule),
  implicit_patterns: [.[].implicit_patterns[]] | unique_by(.pattern),
  anti_patterns_flagged: [.[].anti_patterns_flagged[]] | unique_by(.anti_pattern),
  approved_patterns: [.[].approved_patterns[]] | unique_by(.pattern),
  communication_style: .[0].communication_style,
  flexibility_signals: [.[].flexibility_signals[]],
  conviction_signals: [.[].conviction_signals[]],
  domain_expertise: [.[].domain_expertise[]] | unique_by(.domain),
  languages_reviewed: [.[].languages_reviewed[]] | unique,
  quoted_principles: [.[].quoted_principles[]] | unique
}' soul-extract-out/analysis_chunk_*.json > soul-extract-out/merged_analysis.json
```

**Step 5b — Read the merged analysis and synthesize**

Read `soul-extract-out/merged_analysis.json`. Then:

1. **Deduplicate** — merge similar rules/patterns that express the same belief in different words. Keep the version with the strongest evidence.

2. **Rank by strength** — beliefs marked "always" across multiple chunks are core tenets. "Sometimes" beliefs are preferences, not principles.

3. **Identify uniqueness** — separate beliefs that are UNIQUE to this reviewer from generic best practices (e.g., "validate input" is generic; "use errors.Is() over string matching" is specific).

4. **Select 5-7 core philosophies** — the defining beliefs that make this reviewer distinctive. Each should have:
   - A memorable name (e.g., "Anti-Abstraction Doctrine", "YAGNI Philosophy")
   - A quoted principle from their actual comments
   - Application guidance (how to apply it in reviews)

5. **Build communication style profile** — merge the communication styles from all chunks. Identify:
   - Dominant tone
   - Characteristic phrases (must appear in multiple chunks to be real)
   - How they signal severity

6. **Build decision framework** — from conviction signals (what blocks merge) and flexibility signals (what's a suggestion).

7. **Map expertise** — from domain_expertise entries and languages_reviewed.

### Step 6 — Generate the reviewer agent

Read the template from `references/agent-template.md (relative to this SKILL.md)`.

Fill in every placeholder with the synthesized data from Step 5. The generated agent must:

1. **Use the reviewer's actual voice** — characteristic phrases, tone, severity signals
2. **Include quoted principles** — real quotes from their reviews as the `>` blockquote in each philosophy section
3. **Be specific, not generic** — every rule should be actionable, not platitude
4. **Include example comments** — 3-5 realistic review comments using their voice and patterns
5. **Have a clear decision framework** — what blocks merge vs what's optional

Write the agent definition to `<agent-directory>/{USERNAME}-reviewer.md`.

```bash
# Verify the file was written correctly
head -10 <agent-directory>/USERNAME-reviewer.md
wc -l <agent-directory>/USERNAME-reviewer.md
```

Replace `USERNAME` with the actual username (lowercase).

### Step 7 — Report and clean up

Print the results:

```
Soul extraction complete for USERNAME.

Data analyzed:
  Repos: N
  Qualifying PRs (5+ comments): N
  Total review comments analyzed: N
  Time range: SINCE to UNTIL

Core beliefs extracted:
  1. [Philosophy Name] — one-line summary
  2. [Philosophy Name] — one-line summary
  ...

Communication style: [tone description]
Primary expertise: [domain list]
Languages: [language list]

Agent definition saved to: <agent-directory>/USERNAME-reviewer.md

To use for code review:
  Agent(subagent_type="USERNAME-code-reviewer", prompt="Review this PR: ...")
```

Clean up temporary files:

```bash
rm -rf soul-extract-out/
```

## Rate Limit Management

GitHub API allows 5000 requests/hour for authenticated users. This skill uses approximately:
- Step 1: 1 paginated call per repo (may be multiple pages)
- Step 3: 3 calls per qualifying PR (metadata + reviews + comments)

For 50 qualifying PRs across 3 repos: ~155 calls. Well within limits.

If you hit rate limits during Step 3, pause and tell the user:
```
Rate limit reached. Waiting until [reset_time] before continuing.
Completed: X/Y PRs enriched so far.
```

Use `gh api /rate_limit` to check remaining requests between batches.

## Edge Cases

- **Reviewer uses multiple GitHub accounts**: only one username at a time. Run the skill once per account and manually merge.
- **Archived repos**: `gh api` still works for archived repos, but new PRs won't exist.
- **Private repos**: user must have access. `gh auth status` confirms authentication.
- **Very prolific reviewer (1000+ comments)**: the cap at 100 qualifying PRs prevents API exhaustion. The most recent PRs are kept (most representative of current beliefs).
- **Reviewer who only leaves 1-2 comments per PR**: they won't have qualifying PRs. Suggest lowering the threshold or checking the username.
- **Non-English comments**: the analysis subagents handle any language, but the output agent will be in the same language as the comments.

## Honesty Rules

- Never invent beliefs not supported by evidence. Every rule needs actual comment quotes.
- Never attribute generic best practices as unique beliefs unless the reviewer specifically emphasizes them.
- If the reviewer contradicts themselves across PRs, note it — don't paper over inconsistency.
- Always show the evidence trail. If a belief is based on 2 comments vs 20, say so.
- If the extraction produces fewer than 3 core philosophies, tell the user the data is insufficient — don't pad with filler.
