#!/usr/bin/env python3
"""
Interactive Terminal Mode for Support Triage Agent
Usage: py -3 code/interactive.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from main import load_corpus, load_samples, triage_ticket

def interactive_mode():
    """Run agent in interactive terminal mode."""
    print("\n" + "="*80)
    print("SUPPORT TICKET TRIAGE AGENT - INTERACTIVE MODE")
    print("="*80)
    print("\nType 'quit' to exit, 'help' for commands\n")
    
    # Load once at startup
    print("Loading corpus and samples...")
    repo_root = Path(__file__).parent.parent
    docs, idf = load_corpus(repo_root)
    samples = load_samples(repo_root)
    print(f"✓ Loaded {len(docs)} support documents\n")
    
    while True:
        try:
            print("-" * 80)
            company = input("Company (HackerRank/Claude/Visa) [press Enter for auto]: ").strip() or "None"
            if company.lower() == "quit":
                print("Goodbye!")
                break
            
            subject = input("Subject line: ").strip()
            if not subject:
                print("Subject required. Try again.\n")
                continue
                
            issue = input("Issue description (or press Enter to use subject): ").strip() or subject
            
            if company.lower() == "quit" or subject.lower() == "quit" or issue.lower() == "quit":
                print("Goodbye!")
                break
            
            # Run triage
            print("\nProcessing...\n")
            result = triage_ticket(
                issue=issue,
                subject=subject,
                company=company,
                docs=docs,
                idf=idf,
                samples=samples
            )
            
            # Display result
            print("=" * 80)
            print("TRIAGE RESULT")
            print("=" * 80)
            print(f"\n📋 ISSUE: {result['issue'][:70]}...")
            print(f"\n🏢 COMPANY: {result['company']}")
            print(f"📂 PRODUCT AREA: {result['product_area']}")
            print(f"🏷️  REQUEST TYPE: {result['request_type']}")
            print(f"\n📊 STATUS: {result['status'].upper()}")
            
            if result['status'] == 'replied':
                print(f"\n✅ RESPONSE:\n{result['response'][:500]}...")
            else:
                print(f"\n⚠️  ESCALATION REASON:\n{result['response']}")
            
            print(f"\n💡 JUSTIFICATION:\n{result['justification']}\n")
            
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            continue

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        print("""
INTERACTIVE TERMINAL MODE - HELP

Usage:
    py -3 code/interactive.py

Features:
    • Input support ticket details interactively
    • Get instant triage decision (replied/escalated)
    • View grounded response or escalation reason
    • See product area and request type classification
    
Commands:
    quit - Exit the program
    help - Show this help message

Example Session:
    Company: HackerRank
    Subject: How to reset my password?
    Issue: I forgot my password and need to reset it
    
Output:
    • Status: replied or escalated
    • Response: Relevant support article excerpt or escalation guidance
    • Justification: Why this decision was made
    • Product Area: Inferred category
    • Request Type: bug/feature_request/invalid/product_issue
""")
    else:
        interactive_mode()
