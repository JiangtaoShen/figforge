"""Run every test_*.py in this folder, each in its own process.

Each suite owns a QApplication and prints PASS/FAIL lines; process
isolation keeps Qt state from bleeding between suites. Exit code is
non-zero if any suite fails — used by CI.
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = sorted(f for f in os.listdir(HERE)
                 if f.startswith("test_") and f.endswith(".py"))

# isolate autosave/crash-recovery files from the user's real app data (and
# from other suites): each run gets a throwaway autosave directory
ENV = dict(os.environ)
ENV.setdefault("FIGFORGE_AUTOSAVE_DIR",
               tempfile.mkdtemp(prefix="ff_test_autosave_"))
# C-level traceback if a Qt call segfaults (kept on: invaluable for the
# macOS use-after-free crashes that have no Python traceback)
ENV.setdefault("PYTHONFAULTHANDLER", "1")


def main() -> int:
    failed = []
    for script in SCRIPTS:
        print(f"\n=== {script} " + "=" * max(0, 58 - len(script)), flush=True)
        # -u: unbuffered, so a hard crash can't swallow earlier PASS/FAIL lines
        r = subprocess.run([sys.executable, "-u", os.path.join(HERE, script)],
                           env=ENV)
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
