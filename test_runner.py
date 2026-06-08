import sys
import time

sys.path.insert(0, "/content/BIFAS")

from engine import run_bifas_pipeline
from bifas_agents import DEPTH_CONFIG

QUERIES = {
    "Stocks": "Analyze the current outlook for NVIDIA (NVDA), Apple (AAPL), and Microsoft (MSFT) stocks including technical indicators, valuation metrics, and growth prospects",
    "Crypto": "Analyze Bitcoin (BTC) and Ethereum (ETH) price trends, on-chain metrics, and market sentiment for the current quarter",
    "Forex": "Analyze Forex correlations and trends between EUR/USD, GBP/USD, and USD/JPY pairs including macroeconomic factors"
}

DEPTHS = ["Quick", "Standard", "Deep"]

OUTPUT_FILE = "/content/BIFAS/RAW_TEST_OUTPUT.md"

def run_all_tests():
    lines = []
    lines.append("# BIFAS Raw Test Output — Sprint Architecture (v5.0)")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%B %d, %Y')}")
    lines.append(f"**Architecture:** Sprint — Parallel Agent Execution + Live Market Data")
    lines.append(f"**Engine:** MiMo-V2.5pro (agents) / MiMo-V2.5 (orchestrator)")
    lines.append(f"**Data Sources:** yfinance (stocks/forex/commodities), Kraken (crypto OHLCV), CoinGecko (crypto market), Blockchain.com (on-chain), Alternative.me (sentiment), Frankfurter (forex rates)")
    lines.append("")
    lines.append("---")
    lines.append("")

    test_num = 0
    total_start = time.time()

    for domain, query in QUERIES.items():
        for depth in DEPTHS:
            test_num += 1
            max_agents = DEPTH_CONFIG[depth]["max_agents"]

            print(f"\n{'='*60}")
            print(f"TEST #{test_num} — {domain} / {depth} ({max_agents} agents)")
            print(f"{'='*60}")
            print(f"Query: {query}")
            print(f"Starting...")

            lines.append(f"## TEST #{test_num} — {domain} / {depth}")
            lines.append("")
            lines.append(f"**Query:** {query}")
            lines.append(f"**Depth:** {depth} ({max_agents} agents)")
            lines.append(f"**Expected Calls:** {max_agents + 3} (1 decompose + {max_agents} parallel + 1 synth + 1 audit)")
            lines.append("")
            lines.append("---")
            lines.append("")

            try:
                result = run_bifas_pipeline(query, depth=depth)

                lines.append("### AGENT SQUAD")
                lines.append("")
                for i, agent in enumerate(result.get("agent_squad", []), 1):
                    lines.append(f"{i}. **{agent['name']}** — {agent['prompt'][:120]}")
                lines.append("")

                lines.append("### PHASE 2 — AGENT CONTRIBUTIONS")
                lines.append("")
                for round_data in result.get("rounds", []):
                    agent_name = round_data.get("next_agent", "Unknown")
                    contribution = round_data.get("contribution", "N/A")
                    lines.append(f"**[{agent_name}]**")
                    lines.append("")
                    lines.append(f"```")
                    lines.append(contribution)
                    lines.append(f"```")
                    lines.append("")

                if not result.get("rounds"):
                    lines.append("*No agent contributions recorded.*")
                    lines.append("")

                lines.append("### PHASE 3 — FINAL REPORT")
                lines.append("")
                lines.append("```markdown")
                lines.append(result.get("final_report", "No report generated."))
                lines.append("```")
                lines.append("")

                lines.append("### PHASE 4 — AUDIT VERDICT")
                lines.append("")
                lines.append(f"**{result.get('audit_status', 'N/A')}**")
                lines.append("")

                lines.append("### METRICS")
                lines.append("")
                lines.append(f"| Metric | Value |")
                lines.append(f"|--------|-------|")
                lines.append(f"| Execution Time | {result.get('execution_time', 0):.1f}s |")
                lines.append(f"| Total Messages | {result.get('total_messages', 0)} |")
                lines.append(f"| Agents Generated | {len(result.get('agent_squad', []))} |")
                lines.append(f"| Rounds Completed | {len(result.get('rounds', []))} |")
                guardrail = result.get('guardrail_triggered')
                lines.append(f"| Guardrail | {guardrail if guardrail else 'None'} |")
                data_sources = result.get('data_sources', [])
                lines.append(f"| Data Sources | {', '.join(data_sources) if data_sources else 'None'} |")
                lines.append("")
                lines.append("---")
                lines.append("")

                print(f"DONE — {result.get('execution_time', 0):.1f}s — Audit: {result.get('audit_status', 'N/A')}")

            except Exception as e:
                error_msg = str(e)
                print(f"FAILED — {error_msg}")
                lines.append(f"### ERROR")
                lines.append("")
                lines.append(f"```")
                lines.append(error_msg)
                lines.append(f"```")
                lines.append("")
                lines.append("---")
                lines.append("")

    total_time = time.time() - total_start

    lines.append("## SUMMARY")
    lines.append("")
    lines.append(f"**Total Test Duration:** {total_time:.1f}s ({total_time/60:.1f} min)")
    lines.append(f"**Total Tests:** {test_num}")
    lines.append(f"**Architecture Version:** Sprint (v5.0) — Parallel Execution + Live Market Data")
    lines.append("")

    output = "\n".join(lines)

    with open(OUTPUT_FILE, "w") as f:
        f.write(output)

    print(f"\n{'='*60}")
    print(f"ALL TESTS COMPLETE — {total_time:.1f}s")
    print(f"Output saved to: {OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_all_tests()
