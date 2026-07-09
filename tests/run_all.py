"""Run every test_*.py in this folder, each in its own process.

Each suite owns a QApplication and prints PASS/FAIL lines; process
isolation keeps Qt state from bleeding between suites. Exit code is
non-zero if any suite fails — used by CI.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = sorted(f for f in os.listdir(HERE)
                 if f.startswith("test_") and f.endswith(".py"))


def main() -> int:
    failed = []
    for script in SCRIPTS:
        print(f"\n=== {script} " + "=" * max(0, 58 - len(script)), flush=True)
        # -u: unbuffered, so a hard crash can't swallow earlier PASS/FAIL lines
        r = subprocess.run([sys.executable, "-u", os.path.join(HERE, script)])
        if r.returncode != 0:
            failed.append(script)
    print("\n" + "=" * 66)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print(f"All {len(SCRIPTS)} suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
