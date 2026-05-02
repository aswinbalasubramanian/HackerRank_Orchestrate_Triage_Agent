## Support Triage Agent

A deterministic, terminal-based support triage agent for the HackerRank Orchestrate challenge (May 2026).

---

### Requirements

- Python 3.10 or higher (uses `|` union type syntax)
- No external dependencies — stdlib only (`csv`, `math`, `re`, `argparse`, `pathlib`, `collections`)

---

### How it works

```
Input ticket (issue + subject + company)
        │
        ▼
1. Tokenise + infer company          ← keyword hints for HackerRank / Claude / Visa
        │
        ▼
2. TF-IDF lexical search             ← scores all corpus docs, returns top-K matches
        │                               title-overlap boosted, generic index docs excluded
        ▼
3. Rule-based classification         ← request_type: product_issue / bug / feature_request / invalid
        │
        ▼
4. Escalation check                  ← fraud, identity theft, account access, security,
        │                               low-confidence retrieval → escalated
        ▼
5. Response assembly
        ├── replied  → top relevant lines extracted from best corpus article + source URL
        └── escalated → context-specific escalation guidance (fraud / refund / security / access)
        │
        ▼
Output row: issue, subject, company, response, product_area, status, request_type, justification
```

---

### Output columns

| Column | Allowed values |
|---|---|
| `status` | `replied`, `escalated` |
| `product_area` | category inferred from corpus path / best matching doc |
| `response` | grounded answer from corpus or escalation guidance |
| `justification` | concise reason for routing / answering decision |
| `request_type` | `product_issue`, `feature_request`, `bug`, `invalid` |

---

### Run — batch mode (CSV → CSV)

From the repo root:

```bash
# Full run (writes to support_tickets/output.csv by default)
py -3 code/main.py

# Explicit paths
py -3 code/main.py --input support_tickets/support_tickets.csv --output support_tickets/output.csv

# Validate against sample tickets
py -3 code/main.py --input support_tickets/sample_support_tickets.csv --output support_tickets/sample_output.csv
```

---

### Run — interactive terminal mode

Test the agent live by entering tickets in the terminal:

```bash
py -3 code/interactive.py
```

You will be prompted for:
- Company (HackerRank / Claude / Visa — or press Enter for auto-detection)
- Subject line
- Issue description

Type `quit` or press Ctrl+C to exit.

---

### Key design decisions

- **No hallucination**: responses are extracted verbatim from corpus documents; no text is invented.
- **Company auto-detection**: if company is blank, keyword hints (e.g. "card", "withdrawal", "assessment", "api") route the ticket to the right corpus subset before retrieval.
- **Fraud / sensitive escalation**: explicit markers for unauthorized transactions, identity theft, account takeover, and security vulnerabilities always escalate regardless of retrieval score.
- **Generic doc suppression**: index/readme docs are excluded from retrieval to avoid low-quality top-match noise.
- **Deterministic**: no random sampling; same input always produces same output.

---

### Notes

- The agent uses only the local corpus (`../data/`) — no network calls at runtime.
- `../support_tickets/sample_support_tickets.csv` is used at startup for request-type pattern guidance only.
- All predictions for the final submission are in `../support_tickets/output.csv`.
