"""Homework B: learn from a failed test.

    python hw_b_nights.py              # both variants, 5 runs each
    python hw_b_nights.py --runs 3     # fewer runs (saves quota)
    python hw_b_nights.py --vague      # the model is not told the rules for reversed/malformed dates

The model writes nights_between(check_in, check_out). Our tests run the generated code in a
SEPARATE process with a timeout (a bad loop cannot freeze us, a crash cannot crash us).
(a) plain retries: up to 3 attempts, each retry sees its code and the failed tests.
(b) the same + after every failure the model explains the mistake in two sentences; those
    lessons are added to every later prompt (also in the next runs).
(c) compare attempts and tokens, and read the lessons: were they correct?
"""
import json
import re
import subprocess
import sys

from google.genai import errors

from llm import QuotaExhausted, ask

MAX_ATTEMPTS = 3
TIMEOUT_S = 5

TASK = """Write a Python function nights_between(check_in: str, check_out: str) -> int.
- Both dates are strings in the format YYYY-MM-DD, for example '2027-05-12'.
- Return the number of hotel nights between check_in and check_out (the same day gives 0).
- If check_out is before check_in, raise ValueError.
- If a date is malformed (another format, or a date that does not exist such as 2027-02-30), raise ValueError.
Use only the Python standard library. Reply with ONLY the code, in one ```python block."""

# --vague: the SAME function, but the model is NOT told what to do with reversed or malformed dates.
# It can only find out from the failed tests -> now there is something to learn.
TASK_VAGUE = """Write a Python function nights_between(check_in: str, check_out: str) -> int that returns
the number of hotel nights between two dates written as YYYY-MM-DD, for example '2027-05-12'.
Use only the Python standard library. Reply with ONLY the code, in one ```python block."""
if "--vague" in sys.argv:
    TASK = TASK_VAGUE

TESTS = [  # (name, check_in, check_out, expected) - expected is a number or "ValueError"
    ("same day", "2027-05-12", "2027-05-12", 0),
    ("normal stay", "2027-05-12", "2027-05-16", 4),
    ("month end", "2027-01-31", "2027-02-01", 1),
    ("year end", "2026-12-30", "2027-01-02", 3),
    ("leap year", "2028-02-28", "2028-03-01", 2),
    ("not a leap year", "2027-02-28", "2027-03-01", 1),
    ("reversed dates", "2027-05-16", "2027-05-12", "ValueError"),
    ("malformed: DD/MM/YYYY", "12/05/2027", "16/05/2027", "ValueError"),
    ("malformed: no such day", "2027-02-30", "2027-03-02", "ValueError"),
    ("malformed: month 13", "2027-13-01", "2027-13-05", "ValueError"),
]

# This text is added AFTER the model's code: it calls the function on every case and prints the results.
RUNNER = """
import json
results = []
for check_in, check_out in CASES:
    try:
        results.append(nights_between(check_in, check_out))
    except Exception as e:
        results.append(type(e).__name__)
print("RESULTS:" + json.dumps(results, default=str))
"""


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
    return m.group(1) if m else text


def run_tests(code: str) -> list[str]:
    """Run the code in a separate Python process. Returns the failed tests ([] = all passed)."""
    cases = [(check_in, check_out) for _name, check_in, check_out, _expected in TESTS]
    program = code + "\n\nCASES = " + repr(cases) + "\n" + RUNNER
    try:
        done = subprocess.run([sys.executable, "-I", "-c", program], capture_output=True, text=True,
                              timeout=TIMEOUT_S, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return [f"timeout: the code ran for more than {TIMEOUT_S} s"]
    m = re.search(r"RESULTS:(.*)", done.stdout)
    if not m:
        last_line = (done.stderr.strip().splitlines() or ["no output"])[-1]
        return [f"the code did not run: {last_line}"]

    failures = []
    results = json.loads(m.group(1))
    for (name, check_in, check_out, expected), got in zip(TESTS, results):
        if got != expected:
            got_text = f"raised {got}" if isinstance(got, str) else f"returned {got}"
            want_text = "raise ValueError" if expected == "ValueError" else f"return {expected}"
            failures.append(f"{name}: nights_between({check_in!r}, {check_out!r}) {got_text}, should {want_text}")
    return failures


def solve(use_lessons: bool, lessons: list[str]) -> tuple[int, int, bool]:
    """One run. Returns (attempts used, tokens used, solved?)."""
    tokens = 0
    code = ""
    failures = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = TASK
        if use_lessons and lessons:
            prompt += "\n\nLessons from earlier mistakes:\n" + "\n".join(f"- {lesson}" for lesson in lessons)
        if failures:
            prompt += ("\n\nYour previous code:\n```python\n" + code + "\n```\nIt failed these tests:\n"
                       + "\n".join(failures) + "\nFix the code.")
        r = ask(prompt, temperature=1.0)
        tokens += r.in_tokens + r.out_tokens
        code = extract_code(r.text)
        failures = run_tests(code)
        if not failures:
            print(f"   attempt {attempt}: all {len(TESTS)} tests passed")
            return attempt, tokens, True
        print(f"   attempt {attempt}: {len(failures)} failed - {failures[0]}")

        if use_lessons:
            r = ask("This Python code:\n```python\n" + code + "\n```\nfailed these tests:\n" + "\n".join(failures)
                    + "\nExplain the mistake in exactly two sentences, as a general lesson for next time. No code.",
                    temperature=0.0)
            tokens += r.in_tokens + r.out_tokens
            lesson = " ".join(r.text.split())  # one line
            lessons.append(lesson)
            print(f"   lesson: {lesson}")
    return MAX_ATTEMPTS, tokens, False


if __name__ == "__main__":
    runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 5
    table = []
    lessons: list[str] = []
    try:
        for label, use_lessons in [("plain retries", False), ("retries + lessons", True)]:
            print(f"\n== {label}")
            rows = []
            for run in range(1, runs + 1):
                print(f" run {run}")
                try:
                    rows.append(solve(use_lessons, lessons))
                except (errors.APIError, TimeoutError) as e:  # the provider gave up: skip this run, not a crash
                    print(f"   provider error, run skipped: {str(e)[:80]}")
            table.append((label, rows))
    except QuotaExhausted as e:
        sys.exit(f"\n[stopped] {e}")

    print("\n== (c) comparison")
    print("| variant | solved | average attempts | average tokens |")
    print("|---|---|---|---|")
    for label, rows in table:
        if not rows:
            print(f"| {label} | no finished runs | | |")
            continue
        solved = sum(1 for _a, _t, ok in rows if ok)
        attempts = sum(a for a, _t, _ok in rows) / len(rows)
        tokens = sum(t for _a, t, _ok in rows) / len(rows)
        print(f"| {label} | {solved}/{len(rows)} | {attempts:.1f} | {tokens:,.0f} |")

    print("\n== lessons the model wrote (read them: were they correct?)")
    for k, lesson in enumerate(lessons, 1):
        print(f"{k}. {lesson}")
    if not lessons:
        print("(none - every first attempt passed)")