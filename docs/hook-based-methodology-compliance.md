# Hook-Based Methodology Compliance — General Framework

**Purpose:** Use Kiro agent hooks as automated guardrails to ensure humans and agents follow established development methodology. Hooks fire at decision points where process steps are most likely to be skipped.

**Philosophy:** Gate, don't block. Log everything. Minimize noise.

---

## Core Principles

1. **Gate at decision moments** — Hooks should fire when work is about to happen (pre-write, pre-task), not continuously. Target the points where shortcuts occur.
2. **Remind, don't hard-stop** — The human can always proceed, but the record shows they were warned and acknowledged the deviation.
3. **Layer defenses** — No single hook catches everything. Combine pre-write + file-event + post-session as a minimum.
4. **Keep prompts short and actionable** — "What story is this for?" beats a paragraph of instructions.
5. **Audit trail over enforcement** — The compliance value is in having a record of what was done, when, and whether it followed process.

---

## Layer 1: Pre-Write Gates

**Hook type:** `preToolUse` → `toolTypes: ["write"]`

**When it fires:** Before any file is created or modified by the agent.

**What it enforces:**
- No code without a ticket/story
- No architecture changes without a change request
- No spec modifications without version bumps
- No infrastructure changes without security review

**Example hook:**

```json
{
  "name": "Write Justification Gate",
  "version": "1.0.0",
  "when": {
    "type": "preToolUse",
    "toolTypes": ["write"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "Before writing this file: What ticket, story, or change request does this belong to? If untracked, label it as ad-hoc and log in the progress tracker."
  }
}
```

**Variations:**
- Scope to specific directories: use `fileEdited` with patterns instead for narrower targeting
- Add security gate: "Does this file contain credentials, IAM policies, or auth logic? If yes, has security review been completed?"

---

## Layer 2: File Event Watchers

**Hook type:** `fileEdited` / `fileCreated` / `fileDeleted`

**When it fires:** When humans edit project artifacts directly (bypassing the agent workflow).

**What it enforces:**
- Every doc change is logged with date + reason
- New implementation files trace to a backlog story
- Deletions are flagged for review
- Cross-document consistency is maintained

### 2a: Document Change Tracker

```json
{
  "name": "Track Doc Changes",
  "version": "1.0.0",
  "when": {
    "type": "fileEdited",
    "patterns": ["docs/*.md", "specs/**/*.md"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "A project document was edited. Check: (1) Is this part of the current workflow? If not, log as out-of-band. (2) Are cross-references in other docs now stale? (3) Does the progress tracker need updating?"
  }
}
```

### 2b: New Implementation File Tracker

```json
{
  "name": "Track New Source Files",
  "version": "1.0.0",
  "when": {
    "type": "fileCreated",
    "patterns": ["src/**/*.ts", "src/**/*.tsx", "backend/**/*.ts", "infrastructure/**/*.yaml"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "A new implementation file was created. Verify: (1) Does it correspond to a story in the backlog? (2) Is there an approved spec for this work? (3) If unplanned, log it for review."
  }
}
```

### 2c: Deletion Guard

```json
{
  "name": "Deletion Audit",
  "version": "1.0.0",
  "when": {
    "type": "fileDeleted",
    "patterns": ["src/**/*", "docs/**/*", "infrastructure/**/*"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "A file was deleted. Confirm: (1) Was this intentional and approved? (2) Are there references to this file in other docs or imports that are now broken? (3) Log the deletion with reason."
  }
}
```

---

## Layer 3: Prompt-Time Methodology Nudges

**Hook type:** `promptSubmit`

**When it fires:** Before the agent starts working on any user request.

**What it enforces:**
- Humans don't skip planning and jump straight to implementation
- Security-sensitive requests get flagged early
- Scope creep is identified before work begins

```json
{
  "name": "Methodology Check on Prompt",
  "version": "1.0.0",
  "when": {
    "type": "promptSubmit"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Before starting work: (1) Is this request covered by an existing story or spec? (2) If it involves security, auth, or infrastructure, has the appropriate reviewer been consulted? (3) If this is new unplanned work, should we create a ticket first or proceed as ad-hoc?"
  }
}
```

**Warning:** This hook fires on every message. Use sparingly or make the prompt very short. Consider disabling during exploratory/research conversations and enabling only during implementation phases.

---

## Layer 4: Post-Session Audits

**Hook type:** `agentStop`

**When it fires:** After every agent execution completes.

**What it enforces:**
- Progress tracker stays current
- No work falls through the cracks
- Cross-document consistency is verified at session boundaries

```json
{
  "name": "Session Audit",
  "version": "1.0.0",
  "when": {
    "type": "agentStop"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Session ended. Review what was accomplished: (1) Update the progress tracker with completed work. (2) Flag any unfinished items. (3) Check if any docs were modified without updating cross-references."
  }
}
```

---

## Layer 5: Task Lifecycle Gates

**Hook type:** `preTaskExecution` / `postTaskExecution`

**When it fires:** Before/after spec tasks change status (in Kiro spec-driven development).

**What it enforces:**
- No implementation starts without a complete spec
- Quality checks run after every task completes
- Dependencies are verified before work begins

### 5a: Pre-Task Readiness Check

```json
{
  "name": "Spec Readiness Gate",
  "version": "1.0.0",
  "when": {
    "type": "preTaskExecution"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Before starting this task: (1) Is the architecture doc complete with no open gaps? (2) Are all acceptance criteria testable? (3) Are dependencies resolved? If any answer is no, do not proceed — flag the blocker."
  }
}
```

### 5b: Post-Task Quality Gate (command-based)

```json
{
  "name": "Post-Task Quality Check",
  "version": "1.0.0",
  "when": {
    "type": "postTaskExecution"
  },
  "then": {
    "type": "runCommand",
    "command": "npm run lint && npm run type-check"
  }
}
```

### 5c: Post-Task Quality Gate (agent-based alternative)

```json
{
  "name": "Post-Task Verification",
  "version": "1.0.0",
  "when": {
    "type": "postTaskExecution"
  },
  "then": {
    "type": "askAgent",
    "prompt": "Task completed. Verify: (1) All acceptance criteria are met. (2) Tests pass. (3) No lint or type errors. (4) Progress tracker updated. (5) Cross-document references are consistent."
  }
}
```

---

## Layer 6: Tool-Specific Guards

**Hook type:** `preToolUse` / `postToolUse` with regex `toolTypes`

**When it fires:** Before/after specific tool categories or MCP tools are invoked.

**What it enforces:**
- Database operations have corresponding migrations
- Deployments have passed review
- Destructive operations are confirmed

### 6a: Database Operation Guard

```json
{
  "name": "DB Operation Check",
  "version": "1.0.0",
  "when": {
    "type": "preToolUse",
    "toolTypes": [".*sql.*", ".*database.*", ".*postgres.*"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "A database operation is about to execute. Confirm: (1) Is there a corresponding migration file? (2) Is the data model doc updated? (3) Has this been tested in a non-production environment?"
  }
}
```

### 6b: Shell Command Safety

```json
{
  "name": "Shell Command Review",
  "version": "1.0.0",
  "when": {
    "type": "preToolUse",
    "toolTypes": ["shell"]
  },
  "then": {
    "type": "askAgent",
    "prompt": "A shell command is about to run. Check: (1) Is this destructive or irreversible? (2) Does it affect shared infrastructure? (3) If it deploys or modifies production resources, has it been approved?"
  }
}
```

---

## Recommended Hook Sets by Team Maturity

### Minimum Viable (any project, day one)

| # | Hook | Event | Purpose |
|---|------|-------|---------|
| 1 | Write justification | `preToolUse: write` | Trace every change to a reason |
| 2 | Doc change tracker | `fileEdited: docs/**` | Catch out-of-band edits |
| 3 | Session audit | `agentStop` | Keep progress tracker current |

### Standard (established workflow)

All of Minimum Viable, plus:

| # | Hook | Event | Purpose |
|---|------|-------|---------|
| 4 | New file tracker | `fileCreated: src/**` | Verify code traces to stories |
| 5 | Post-task quality | `postTaskExecution` | Lint + type-check after tasks |
| 6 | Deletion guard | `fileDeleted: src/**` | Audit removals |

### Full Compliance (regulated/enterprise)

All of Standard, plus:

| # | Hook | Event | Purpose |
|---|------|-------|---------|
| 7 | Pre-task readiness | `preTaskExecution` | Block work without complete specs |
| 8 | Prompt methodology check | `promptSubmit` | Catch scope creep early |
| 9 | DB operation guard | `preToolUse: .*sql.*` | Enforce migration discipline |
| 10 | Shell safety | `preToolUse: shell` | Review destructive commands |

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It Fails | Better Approach |
|--------------|--------------|-----------------|
| Hook on every keystroke | Alert fatigue — gets ignored | Target decision moments only |
| Long multi-paragraph prompts | Agent buries the instruction | One clear question per hook |
| Hard blocks with no override | Frustrates humans, gets disabled | Log + warn, let human proceed |
| Duplicate hooks on same event | Conflicting instructions | One hook per concern per event |
| Hooks that require external state | Fragile, breaks when state is stale | Self-contained checks only |
| `promptSubmit` hooks in exploratory phases | Interrupts brainstorming | Enable only during implementation |

---

## Measuring Effectiveness

Track these metrics over time to tune your hook set:

1. **Untracked changes per week** — Are out-of-band edits decreasing?
2. **Cross-document inconsistencies found in review** — Are hooks catching drift before reviewers do?
3. **Stories started without specs** — Is the pre-task gate working?
4. **Rollbacks due to process skips** — Are quality gates preventing rework?
5. **Hook disable rate** — If humans keep disabling hooks, they're too noisy. Tune or remove.

---

## Implementation Checklist

- [ ] Identify your team's top 3 process compliance failures (where do shortcuts happen?)
- [ ] Map each failure to a hook event type (when does the shortcut occur?)
- [ ] Write short, actionable prompts (what should the human/agent do instead?)
- [ ] Start with Minimum Viable set — add layers only when needed
- [ ] Review hook effectiveness monthly — disable noisy hooks, add missing ones
- [ ] Document the hook set in your project README so new team members understand the guardrails
