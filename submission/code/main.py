from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[a-z0-9]+")
LINE_SPLIT_RE = re.compile(r"\r?\n+")
TOP_K_LINES = 4

COMPANY_HINTS: dict[str, tuple[str, ...]] = {
    "visa": (
        "visa",
        "card",
        "credit card",
        "debit card",
        "transaction",
        "withdraw",
        "withdrawal",
        "withdrawn",
        "charge",
        "charged",
        "refund",
        "payment",
        "unauthorized",
        "fraud",
        "stolen",
        "money",
        "bank",
    ),
    "hackerrank": (
        "hackerrank",
        "assessment",
        "test",
        "candidate",
        "interview",
        "challenge",
        "score",
        "submission",
    ),
    "claude": (
        "claude",
        "anthropic",
        "prompt",
        "model",
        "api",
        "token",
        "console",
        "bedrock",
    ),
}

FRAUD_ESCALATION_MARKERS: tuple[str, ...] = (
    "without my knowledge",
    "without my consent",
    "unauthorized",
    "identity theft",
    "stolen my identity",
    "money was withdrawn",
    "money withdrawn",
    "withdrawn by someone",
    "someone withdrew",
    "fraud",
    "fraudulent",
    "account hacked",
)


@dataclass
class SupportDoc:
    company: str
    path: Path
    title: str
    source_url: str
    product_area: str
    body: str
    tokens: list[str]
    term_counts: Counter[str]


@dataclass
class SampleCase:
    issue: str
    subject: str
    company: str
    product_area: str
    status: str
    request_type: str
    tokens: list[str]


def normalize_space(value: str) -> str:
    return " ".join(value.split())


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def parse_front_matter(raw_text: str) -> tuple[dict[str, str], str]:
    if not raw_text.startswith("---\n"):
        return {}, raw_text

    lines = raw_text.splitlines()
    metadata: dict[str, str] = {}
    body_start = 0
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            body_start = index + 1
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata, "\n".join(lines[body_start:])


def _prefix_company(area: str, company: str) -> str:
    """Prepend company name if the area doesn't already start with it."""
    if area in {"general_support", ""}:
        return area
    if area.startswith(company + "_") or area.startswith(company):
        return area
    return f"{company}_{area}"


def infer_product_area(path: Path, metadata: dict[str, str]) -> str:
    parts = [part.lower() for part in path.parts]
    company_index = parts.index("data") + 1
    company = parts[company_index]
    relative_parts = parts[company_index + 1 :]

    if company == "hackerrank":
        raw = relative_parts[0].replace("-", "_") if relative_parts else "general_support"
    elif company == "claude":
        if relative_parts and relative_parts[0] != "claude":
            raw = relative_parts[0].replace("-", "_")
        elif len(relative_parts) > 1:
            part = relative_parts[1]
            if "." in part:
                stem = part.rsplit(".", 1)[0]
                stem = re.sub(r"^\d+-", "", stem)
                raw = stem.replace("-", "_") if stem else "general_support"
            else:
                raw = part.replace("-", "_")
        else:
            raw = "general_support"
    elif company == "visa":
        stem = path.stem.replace("-", "_")
        raw = stem if stem and stem not in {"index", "readme"} else "general_support"
    else:
        raw = metadata.get("product_area", "general_support")

    return _prefix_company(raw, company)


def load_corpus(repo_root: Path) -> tuple[list[SupportDoc], dict[str, float]]:
    docs: list[SupportDoc] = []
    document_frequency: Counter[str] = Counter()

    for path in sorted((repo_root / "data").rglob("*.md")):
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        metadata, body = parse_front_matter(raw_text)
        title = metadata.get("title") or path.stem.replace("-", " ").title()
        company = path.relative_to(repo_root / "data").parts[0].lower()
        normalized_body = normalize_space(body)
        tokens = tokenize(f"{title} {normalized_body}")
        if not tokens:
            continue
        document_frequency.update(set(tokens))
        docs.append(
            SupportDoc(
                company=company,
                path=path,
                title=title,
                source_url=metadata.get("source_url", ""),
                product_area=infer_product_area(path, metadata),
                body=normalized_body,
                tokens=tokens,
                term_counts=Counter(tokens),
            )
        )

    total_docs = max(len(docs), 1)
    idf = {
        token: math.log((total_docs + 1) / (frequency + 1)) + 1
        for token, frequency in document_frequency.items()
    }
    return docs, idf


def load_samples(repo_root: Path) -> list[SampleCase]:
    sample_path = repo_root / "support_tickets" / "sample_support_tickets.csv"
    samples: list[SampleCase] = []
    with sample_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            issue = row.get("Issue", "")
            subject = row.get("Subject", "")
            samples.append(
                SampleCase(
                    issue=issue,
                    subject=subject,
                    company=(row.get("Company", "") or "None").strip(),
                    product_area=row.get("Product Area", ""),
                    status=(row.get("Status", "") or "").strip().lower(),
                    request_type=(row.get("Request Type", "") or "").strip().lower(),
                    tokens=tokenize(f"{issue} {subject}"),
                )
            )
    return samples


def score_text(query_tokens: Iterable[str], term_counts: Counter[str], idf: dict[str, float]) -> float:
    return sum(term_counts.get(token, 0) * idf.get(token, 0.0) for token in query_tokens)


def infer_company(raw_company: str, query_text: str, docs: list[SupportDoc], idf: dict[str, float]) -> str:
    company = (raw_company or "None").strip().lower()
    if company in {"hackerrank", "claude", "visa"}:
        return company

    lowered = query_text.lower()
    hint_scores = {
        candidate: sum(1 for marker in markers if marker in lowered)
        for candidate, markers in COMPANY_HINTS.items()
    }
    hinted_company, hinted_score = max(hint_scores.items(), key=lambda item: item[1])
    if hinted_score > 0:
        return hinted_company

    # No company-specific keywords found — query is genuinely ambiguous.
    # Avoid biasing toward the company with the most corpus documents.
    return "none"


def search_docs(query_text: str, company: str, docs: list[SupportDoc], idf: dict[str, float], limit: int = 5) -> list[tuple[float, SupportDoc]]:
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return []

    scored: list[tuple[float, SupportDoc]] = []
    for doc in docs:
        if company != "none" and doc.company != company:
            continue
        if doc.title.strip().lower() in {"index", "readme"}:
            continue
        score = score_text(query_tokens, doc.term_counts, idf)
        if score <= 0:
            continue
        score += 2.5 * len(set(query_tokens).intersection(tokenize(doc.title)))
        score /= math.sqrt(max(len(doc.tokens), 1))
        scored.append((score, doc))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:limit]


def nearest_sample(issue: str, subject: str, company: str, samples: list[SampleCase]) -> SampleCase | None:
    query_tokens = set(tokenize(f"{issue} {subject}"))
    best_case: SampleCase | None = None
    best_overlap = 0
    for sample in samples:
        if company != "none" and sample.company.lower() != company:
            continue
        overlap = len(query_tokens.intersection(sample.tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best_case = sample
    return best_case if best_overlap >= 2 else None


SUPPORT_DOMAIN_KEYWORDS: tuple[str, ...] = (
    "account", "password", "login", "access", "reset", "error",
    "not working", "api", "card", "payment", "billing", "refund",
    "subscription", "plan", "test", "assessment", "candidate", "interview",
    "problem", "bug", "feature", "update", "cancel",
    "charge", "transaction", "site is down", "portal",
    "dashboard", "score", "submit", "submission", "report", "invoice",
)


def is_gratitude_only(text: str) -> bool:
    lowered = normalize_space(text).lower()
    return lowered in {
        "thank you", "thanks", "thank you for helping me", "thanks for helping me",
        "thank you so much", "thanks a lot", "thanks!", "thank you!",
        "great help", "much appreciated", "appreciated",
    } or all(w in {"urgent", "please", "help", "thanks", "thank", "you", "so", "much", "a", "lot"} for w in lowered.split())


def is_out_of_scope(text: str) -> bool:
    """True when the query has no support-domain or company-specific keywords — likely off-topic."""
    if is_gratitude_only(text):
        return False
    lowered = text.lower()
    if any(kw in lowered for kw in SUPPORT_DOMAIN_KEYWORDS):
        return False
    if any(
        marker in lowered
        for markers in COMPANY_HINTS.values()
        for marker in markers
    ):
        return False
    return True


def is_harmful_request(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ["delete all files", "wipe the system", "malware", "ransomware", "exploit"])


def classify_request_type(text: str, sample: SampleCase | None) -> str:
    lowered = text.lower()
    if is_harmful_request(text) or is_gratitude_only(text) or is_out_of_scope(text):
        return "invalid"
    if any(marker in lowered for marker in ["feature request", "can we extend", "wanted to setup"]):
        return "feature_request"
    if any(marker in lowered for marker in ["down", "not working", "failing", "stopped", "error", "issue", "blocked"]):
        return "bug"
    if sample and sample.request_type:
        return sample.request_type
    return "product_issue"


def should_escalate(text: str, company: str, best_doc: SupportDoc | None, retrieval_score: float) -> bool:
    lowered = text.lower()
    if is_harmful_request(text):
        return False
    if any(marker in lowered for marker in FRAUD_ESCALATION_MARKERS):
        return True
    if any(
        marker in lowered
        for marker in [
            "restore my access",
            "removed my seat",
            "increase my score",
            "move me to the next round",
            "refund me today",
            "ban the seller",
            "refund asap",
            "payment with order id",
            "fill in the forms",
            "rescheduling",
            "reschedule",
            "major security vulnerability",
            "identity has been stolen",
            "logic exact",
            "internal rules",
        ]
    ):
        return True
    if any(marker in lowered for marker in ["site is down", "none of the submissions", "stopped working completely", "all requests are failing"]):
        return True
    if company == "none" and retrieval_score < 1.4:
        return False
    return best_doc is None or retrieval_score < 1.0


def line_relevance(line: str, query_tokens: set[str]) -> float:
    line_tokens = set(tokenize(line))
    overlap = len(line_tokens.intersection(query_tokens))
    if overlap == 0:
        return 0.0
    return overlap / math.sqrt(max(len(line_tokens), 1))


def extract_relevant_lines(doc: SupportDoc, query_text: str, limit: int = TOP_K_LINES) -> list[str]:
    query_tokens = set(tokenize(query_text))
    candidates: list[tuple[float, str]] = []
    for line in re.split(r"(?<=[.!?])\s+", doc.body):
        cleaned = normalize_space(line.strip())
        if len(cleaned) < 20:
            continue
        score = line_relevance(cleaned, query_tokens)
        if score > 0:
            candidates.append((score, cleaned))
    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[str] = []
    seen = set()
    for _, line in candidates:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(line)
        if len(selected) >= limit:
            break

    if not selected:
        selected = [normalize_space(chunk) for chunk in LINE_SPLIT_RE.split(doc.body) if len(normalize_space(chunk)) > 20][:limit]
    return selected


def build_direct_response(doc: SupportDoc, query_text: str) -> str:
    parts = extract_relevant_lines(doc, query_text)
    if doc.source_url:
        parts.append(f"Reference: {doc.source_url}")
    return "\n\n".join(parts[: TOP_K_LINES + 1])


def build_escalation_response(text: str, best_doc: SupportDoc | None) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in FRAUD_ESCALATION_MARKERS):
        return "This appears to be an unauthorized transaction or potential fraud case. Please contact Visa/card-issuer fraud support immediately so they can verify identity, secure the account, and investigate the withdrawal."
    if "removed my seat" in lowered or "restore my access" in lowered:
        return "This request needs to be handled by your workspace owner or admin. Please contact your team admin to restore access or ask them to work with Claude support from the owning workspace."
    if "increase my score" in lowered or "next round" in lowered:
        return "I cannot review assessment answers, change scores, or influence a hiring decision from here. Please contact the recruiting company or assessment owner for a manual review."
    if "refund" in lowered or "payment with order id" in lowered:
        return "This needs account-specific billing review, so it should be handled by a human support team rather than an automated reply."
    if "major security vulnerability" in lowered:
        return "This should be escalated immediately to the security reporting channel or human support team rather than handled in chat."
    if "identity has been stolen" in lowered:
        return "This is a sensitive identity-theft case. Please contact your card issuer immediately and use Visa's emergency support channels for urgent assistance."
    if best_doc:
        return f"This case needs human review or account-specific action. The closest grounded support article was '{best_doc.title}', but the requested action cannot be completed safely through an automated reply."
    return "This case needs human review because I do not have enough grounded support guidance to answer it safely."


def build_invalid_response(text: str) -> str:
    if is_harmful_request(text):
        return "Sorry, I can't assist with that."
    if is_gratitude_only(text):
        return "Happy to help"
    return "I am sorry, this is out of scope from my capabilities"


def choose_product_area(best_doc: SupportDoc | None, sample: SampleCase | None, request_type: str) -> str:
    if best_doc:
        return best_doc.product_area
    if sample and sample.product_area:
        return sample.product_area
    return "" if request_type == "invalid" else "general_support"


def build_justification(status: str, request_type: str, best_doc: SupportDoc | None, retrieval_score: float) -> str:
    doc_ref = f" [source: {best_doc.path.name}]" if best_doc else ""
    if request_type == "invalid":
        return "The request is out of scope or unsafe, so it was handled without attempting unsupported actions."
    if status == "escalated":
        if best_doc:
            return f"Escalated because the request needs human or account-specific intervention; the closest grounded article was '{best_doc.title}'.{doc_ref}"
        return "Escalated because the corpus did not provide enough grounded guidance for a safe automated answer."
    if best_doc:
        return f"Replied directly using the closest grounded support article '{best_doc.title}' with retrieval score {retrieval_score:.2f}.{doc_ref}"
    return "Replied directly because the request was straightforward and did not require unsupported claims."


def triage_ticket(issue: str, subject: str, company: str, docs: list[SupportDoc], idf: dict[str, float], samples: list[SampleCase]) -> dict[str, str]:
    query_text = normalize_space(f"{subject} {issue}")
    # Skip company inference for gratitude/out-of-scope — preserve raw company value
    if is_gratitude_only(query_text) or is_out_of_scope(query_text):
        raw = (company or "None").strip().lower()
        inferred_company = raw if raw in {"hackerrank", "claude", "visa"} else "none"
    else:
        inferred_company = infer_company(company, query_text, docs, idf)
    doc_hits = search_docs(query_text, inferred_company, docs, idf)
    best_score, best_doc = doc_hits[0] if doc_hits else (0.0, None)
    # If company is still unknown but retrieval found a strong match from a known company,
    # promote that company so the output is consistent with the response content.
    if inferred_company == "none" and best_doc and best_doc.company in {"hackerrank", "claude", "visa"} and best_score >= 1.0:
        inferred_company = best_doc.company
    sample = nearest_sample(issue, subject, inferred_company, samples)

    request_type = classify_request_type(query_text, sample)
    if request_type == "invalid":
        status = "replied"
        response = build_invalid_response(query_text)
    else:
        status = "escalated" if should_escalate(query_text, inferred_company, best_doc, best_score) else "replied"
        response = build_escalation_response(query_text, best_doc) if status == "escalated" else build_direct_response(best_doc, query_text)

    return {
        "issue": issue,
        "subject": subject,
        "company": inferred_company,
        "response": response,
        "product_area": choose_product_area(best_doc, sample, request_type),
        "status": status,
        "request_type": request_type,
        "justification": build_justification(status, request_type, best_doc, best_score),
    }


def write_output(rows: list[dict[str, str]], output_path: Path) -> None:
    fieldnames = ["issue", "subject", "company", "response", "product_area", "status", "request_type", "justification"]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(input_path: Path, output_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    docs, idf = load_corpus(repo_root)
    samples = load_samples(repo_root)
    rows: list[dict[str, str]] = []

    with input_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                triage_ticket(
                    issue=row.get("Issue", ""),
                    subject=row.get("Subject", ""),
                    company=row.get("Company", "None"),
                    docs=docs,
                    idf=idf,
                    samples=samples,
                )
            )

    write_output(rows, output_path)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run the support triage agent.")
    parser.add_argument("--input", type=Path, default=repo_root / "support_tickets" / "support_tickets.csv")
    parser.add_argument("--output", type=Path, default=repo_root / "support_tickets" / "output.csv")
    args = parser.parse_args()
    run(args.input, args.output)
