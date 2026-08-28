# Kiro Agent Setup

## Agent Orchestration Model

This project uses a multi-agent orchestration approach where specialized AI agents collaborate through a central orchestrator to deliver software from requirements to implementation.

### Agent Team

| Agent                   | Role                                                              | Phase         |
| ----------------------- | ----------------------------------------------------------------- | ------------- |
| **Orchestrator**        | Central dispatcher — routes work, enforces gates, tracks progress | All phases    |
| **Product Analyst**     | Creates SRS from meeting notes and customer docs                  | Phase 1       |
| **AWS Architect**       | Reviews SRS, designs architecture, creates data model             | Phase 1-2     |
| **Plan Reviewer**       | Validates architecture, edge cases, cross-feature consistency     | Phase 2-3     |
| **Security Reviewer**   | Security + compliance + Well-Architected review                   | Phase 2 gates |
| **Technical PM**        | Sprint planning, JIRA backlog, timeline estimation                | Phase 3       |
| **Backend Developer**   | Implements Lambda handlers, services, DB migrations               | Phase 4       |
| **Frontend Developer**  | Implements UI components, hooks, pages                            | Phase 4       |
| **CloudFormation Developer** | Creates SAM/CloudFormation templates and infrastructure                      | Phase 4       |

### Delivery Workflow

```
Phase 0: Discovery & Compliance
  └─ Search meetings for HIPAA/SOC2/PCI-DSS/CCPA
  └─ Prompt customer if compliance unclear

Phase 1: SRS Creation
  └─ Product Analyst creates SRS (every FR has a Source tag)
  └─ AWS Architect reviews (traceability, completeness, ACs, NFRs)
  └─ Iterate max 3 rounds → SRS approved

Phase 2: Architecture (sequential, gated)
  Step 1: Domain decomposition     → Plan Reviewer + Product Analyst
  Step 2: Feature list             → Plan Reviewer + Product Analyst
  Step 3: Per-feature arch docs    → Plan Reviewer (+ edge cases)
  Step 4: Security Gate 1          → Security Reviewer
  Step 5: Unified data model       → Plan Reviewer + Security Reviewer
  Step 6: Architecture diagram     → Plan Reviewer
  Step 7: Security Gate 2          → Security Reviewer (Well-Architected)
  Step 8: Cost estimate            → Plan Reviewer

Phase 3: Sprint Planning
  └─ Technical PM asks for team size
  └─ Creates implementation strategy + JIRA backlog CSV
  └─ Dual timeline: spec-based vs traditional development
  └─ AWS Architect reviews technical accuracy
  └─ Plan Reviewer validates capacity and dependencies

Phase 4: Implementation
  └─ Orchestrator dispatches stories from approved backlog
  └─ Backend/Frontend/CloudFormation developers implement
  └─ Plan Reviewer reviews completed work
```

### Key Rules

- **Spec-based development** — all code is generated from architecture specs by Kiro agents
- **Source traceability** — every FR must trace to a customer meeting or document. No hallucinated requirements.
- **Max 3 review rounds** per step — then escalate to human
- **Approval threshold** — zero Critical/High findings to pass any gate
- **Session resumption** — `docs/project-progress.md` tracks which step is current. New sessions read this file and resume.
- **Cost-conscious** — reuse existing infrastructure, prefer serverless, justify every new AWS service

---

## How to Use This Workflow (kiro-cli)

### Starting a Session

```bash
kiro-cli chat
```

This opens a chat with the **Orchestrator** agent. The orchestrator automatically:

1. Reads `docs/project-progress.md` to find where you left off
2. Resumes from the first unchecked step
3. Delegates work to specialized subagents as needed

You never talk to subagents directly — everything goes through the orchestrator.

### Typical Conversation Flow

**Starting a new project:**

```
You: We have a new project. Here are the meeting notes: [paste or reference files]
Orchestrator: [reads notes, runs compliance check, delegates to product-analyst to create SRS]
```

**Resuming work:**

```
You: [just open kiro-cli chat]
Orchestrator: Resuming from Phase 2 Step 3 — per-feature architecture docs.
              Last completed: domain decomposition (Apr 2). Next: feature list review.
```

**Handling new requirements:**

```
You: Josh sent new feedback. File is at .kiro/knowledge/uww-docs/feedback.txt
Orchestrator: [reads file, runs change request workflow, produces impact analysis]
```

**Asking about status:**

```
You: What's the sprint 2 status?
Orchestrator: [reads backlog CSV and implementation strategy, summarizes]
```

**Triggering specific work:**

```
You: Make E3-S05 spec-ready
Orchestrator: [checks architecture doc, delegates to aws-architect if gaps exist,
              then security-reviewer if security-related, then adds to backlog]
```

### How the Knowledge Base Works

Customer documents (meeting transcripts, PDFs, CSVs) are indexed in `.kiro/knowledge/`. The orchestrator and subagents use semantic search to find relevant content without you having to specify which file to look in.

```
.kiro/knowledge/
  uww-docs/
    Documentation/
      meetings/          ← meeting transcripts
      customer-provided/ ← PDFs, CSVs, specs from customer
```

To add new customer documents, place them in the appropriate subfolder. The knowledge base re-indexes automatically.

### How Subagent Delegation Works

When you ask the orchestrator to do something, it:

1. Determines which specialized agent(s) are needed
2. Invokes them via `use_subagent` with full context
3. Routes their output to a reviewer agent
4. Returns the final result to you

You see a summary of what each agent did. If a review fails, the orchestrator iterates automatically (up to 3 rounds) before escalating to you.

### When the Orchestrator Escalates to You

The orchestrator will stop and ask for your input when:

- A review round limit (3) is exceeded with unresolved findings
- A stakeholder decision is needed (options presented, you choose)
- A questionnaire answer is required before work can proceed
- A Critical/High finding cannot be resolved without architectural changes

### Project State Files

| File                                        | Purpose                                              |
| ------------------------------------------- | ---------------------------------------------------- |
| `docs/project-progress.md`                  | Current phase and step — read on every session start |
| `docs/sprint-planning/jira-backlog.csv`      | All stories, sprint assignments, dependencies        |
| `docs/srs.md`                                | Living requirements document                         |
| `docs/data-model.md`                         | Living data model                                    |
| `docs/change-requests/`                     | Impact analyses and stakeholder decisions            |
| `docs/srs-questionnaire.md`                 | All stakeholder questions and resolved answers       |

---

## Code Structure Doc (`docs/code-structure.md`)

This is the **most referenced file in the entire workflow** — 9 out of 11 agents load it as a resource. It is the single source of truth for:

- Monorepo folder layout and domain boundaries
- Lambda handler patterns and naming conventions
- CloudFormation stack design (backend-stack.yaml)
- Frontend page/component/hook structure
- Shared types and middleware patterns
- Domain isolation rules (what can import what)

### When It Must Exist

`docs/code-structure.md` must exist **before Phase 4 (implementation) begins**. Every spec a developer agent writes references it. Every code review validates against it.

### How It Gets Created

The AWS Architect creates it during Phase 2 architecture work:

1. If starting a new project — architect copies `.kiro/steering/code-structure-template.md` and fills in project-specific details
2. If rebuilding an existing system — architect reads the legacy codebase and documents the new structure

### What Happens Without It

If `docs/code-structure.md` is missing when a developer agent is invoked:

- The agent will look for it, not find it
- It will fall back to `.kiro/steering/code-structure-template.md` (generic)
- Generated code may not match your actual project structure

**Always ensure `docs/code-structure.md` exists and is up to date before starting Phase 4.**

### Steering Files

| File                                         | Purpose                                                |
| -------------------------------------------- | ------------------------------------------------------ |
| `.kiro/steering/orchestrator-standards.md`   | Delivery workflow, agent routing, compliance rules     |
| `.kiro/steering/aws-architect-standards.md`  | Architecture rules, SRS review checklist, traceability |
| `.kiro/steering/product-analyst-standard.md` | SRS writing standards, source traceability             |
| `.kiro/steering/reviewer-standards.md`       | Plan reviewer quality gates                            |
| `.kiro/steering/lambda-docs.md`              | Lambda documentation three-tier standard               |
| `.kiro/steering/code-structure-template.md`  | Generic code structure template for new projects       |

---

## AWS Credentials

The MCP servers (pricing, diagrams, documentation) require valid AWS credentials.

### 1. Configure SSO

```bash
aws configure sso
```

When prompted:

- **SSO start URL**: `https://d-906778ee70.awsapps.com/start`
- **SSO region**: `us-east-1`

Pick your account and role, then note the profile name it creates.

### 2. Set your profile

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export AWS_PROFILE=<your-sso-profile>
```

### 3. Login before using Kiro

```bash
aws sso login
```

---

## Installing uvx (WSL / Linux)

The agent MCP servers auto-install `uvx` if missing, but if you need to install it manually:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then add to your `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Reload your shell:

```bash
source ~/.bashrc
```

Verify:

```bash
uvx --version
```

### WSL-specific notes

- Make sure `curl` is installed: `sudo apt install -y curl`
- If you're behind a corporate proxy, set `HTTPS_PROXY` before running the install script
- The install goes to `~/.local/bin` inside WSL, not your Windows PATH — this is expected
