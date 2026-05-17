"""Run full eval baseline against auto model and save results."""
import json, os, time, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.eval import AgentEval

eval = AgentEval(model="auto")
baseline = {}

for suite_name in ["basic", "tool_use", "reasoning", "safety", "code"]:
    print(f"=== Running suite: {suite_name} ===")
    report = eval.run_suite(suite_name)
    baseline[suite_name] = {
        "passed": report.passed,
        "total": report.total,
        "failed": report.failed,
        "pass_rate_pct": round(report.passed / max(report.total, 1) * 100, 1),
        "avg_duration_s": round(report.avg_duration_s, 2),
        "avg_rounds": round(report.avg_rounds, 1),
        "p50_duration_s": round(report.p50_duration_s, 2),
        "p90_duration_s": round(report.p90_duration_s, 2),
        "results": [
            {
                "case_id": r.case_id,
                "passed": r.passed,
                "duration_s": round(r.duration_s, 2),
                "keywords_missed": r.keywords_missed,
                "tools_expected": r.tools_expected,
                "tools_called": r.tools_called,
                "error": r.error,
            }
            for r in report.results
        ],
    }
    print(f"  Result: {report.passed}/{report.total} passed ({baseline[suite_name]['pass_rate_pct']}%)")
    print()

baseline["_meta"] = {
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "model": "auto (ollama qwen3:8b)",
    "config": "post-config-refactor",
}
os.makedirs("data/eval", exist_ok=True)
path = "data/eval/baseline.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(baseline, f, ensure_ascii=False, indent=2)
print(f"Saved baseline to {path}")
