"""Verify baseline cost feature."""
from core.token_tracker import tracker

tracker.set_baseline(5.71)
snap = tracker.snapshot(limit=5)
print(f"Total cost with baseline: RMB{snap['total']['cost']:.4f}")
print(f"Baseline: RMB{tracker._baseline_cost}")
print(f"Record count: {snap['total']['calls']}")
print(f"Recent records: {len(snap['recent'])}")
print()

# Reset baseline back to 0
tracker.set_baseline(0.0)
snap2 = tracker.snapshot(limit=5)
print(f"After reset baseline: RMB{snap2['total']['cost']:.4f}")
print("OK")
