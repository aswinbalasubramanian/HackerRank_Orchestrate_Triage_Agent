# Interactive Terminal Mode - Usage Guide

Run the agent interactively to test support ticket triage in real-time.

## Quick Start

```bash
py -3 code/interactive.py
```

## How It Works

1. **Start the agent** - It loads 774 support documents (takes 2-3 seconds)
2. **Enter ticket details**:
   - Company: HackerRank, Claude, Visa, or press Enter for auto-detection
   - Subject: One-line summary of the issue
   - Issue: Full description (or press Enter to use subject)
3. **Get instant result**:
   - ✅ REPLIED: Direct answer from grounded support article
   - ⚠️ ESCALATED: Needs human review with context

## Example Interactions

### Example 1: Password Reset (Auto-Reply)
```
Company: HackerRank
Subject: How do I reset my password?
Issue: I forgot my password and cannot access my account
```
**Result**: REPLIED with password reset instructions

### Example 2: Access Error (Auto-Reply)
```
Company: Claude
Subject: Getting 403 forbidden error
Issue: I keep getting 403 when trying to access my account
```
**Result**: REPLIED with troubleshooting steps

### Example 3: Security Issue (ESCALATE)
```
Company: HackerRank
Subject: Account hacked - identity theft
Issue: Someone stole my identity and changed my password. Need immediate help!
```
**Result**: ESCALATED - high-risk issue needs human agent

### Example 4: Refund Request (May auto-reply or escalate)
```
Company: Visa
Subject: Refund request for disputed charge
Issue: I want a refund for a charge I don't recognize
```
**Result**: Depends on keywords and corpus match

## Commands

- `quit` - Exit the program (type anytime)
- `Ctrl+C` - Force exit

## Output Fields

Each response includes:

| Field | Meaning |
|-------|---------|
| **COMPANY** | Detected or auto-inferred company |
| **PRODUCT AREA** | Category inferred from ticket content |
| **REQUEST TYPE** | bug / feature_request / invalid / product_issue |
| **STATUS** | replied (auto-answer) or escalated (needs human) |
| **RESPONSE** | Either direct answer or escalation reason |
| **JUSTIFICATION** | Why this decision was made + TF-IDF score |

## Tips for Testing

✓ **Test escalation triggers**: Try "refund me today", "restore my access", "security vulnerability"

✓ **Test company detection**: Leave Company blank to see auto-detection

✓ **Test product areas**: Different queries should infer different categories

✓ **Test request types**: Bug reports, feature requests, general questions

✓ **Test edge cases**: Typos, vague descriptions, multi-issue tickets

## Automation

To run non-interactively with piped input:

```bash
cat test_tickets.txt | py -3 code/interactive.py
```

Or with a heredoc:

```bash
py -3 code/interactive.py <<EOF
HackerRank
Subject line
Full issue description
quit
