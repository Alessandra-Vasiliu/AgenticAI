"""Homework A: the voucher puzzle - make 24 from four vouchers.

    python hw_a_vouchers.py                 # (a) ask directly 5 times, (b) one 3-step search, (c) comparison
    python hw_a_vouchers.py 4 9 10 13       # choose the four numbers
    python hw_a_vouchers.py --runs 3        # run the search 3 times (one search is ~20-30 model calls!)

(a) The model answers directly; exact code checks every answer.
(b) A 3-step search: the model PROPOSES the next operations, CODE computes the results,
    the model rates (VALUE) every new state as sure / likely / impossible, and we keep the best 3.
(c) Compare model calls and tokens, and find out whether the failures come from propose or value.
"""
import re
import sys
from fractions import Fraction
from typing import Literal

from google.genai import errors
from pydantic import BaseModel, Field

from exp2_budget import evaluate  # the exact, safe arithmetic from Experiment 2
from llm import QuotaExhausted, ask

NUMBERS = [4, 9, 10, 13]
TARGET = 24
BEAM = 3           # how many states we keep after each step
MAX_PROPOSALS = 5  # how many moves we accept from one propose call
SCORE = {"sure": 3, "likely": 2, "impossible": 0}


# --- Exact checks (code, never the model) ------------------------------------
def check_expression(expr: str, numbers: list[int]) -> str:
    """'' if expr uses every number exactly once and equals 24, otherwise what is wrong."""
    used = sorted(Fraction(x) for x in re.findall(r"\d+(?:\.\d+)?", expr))
    if used != sorted(Fraction(n) for n in numbers):
        return "does not use every number exactly once"
    value = evaluate(expr)
    if value is None:
        return "not a valid expression"
    if value != TARGET:
        return f"equals {float(value):g}, not {TARGET}"
    return ""


def solvable(values: list[Fraction]) -> bool:
    """Brute force: can these numbers still make 24? Used only to find out WHO made a mistake."""
    if len(values) == 1:
        return values[0] == TARGET
    for i in range(len(values)):
        for j in range(len(values)):
            if i == j:
                continue
            rest = [values[k] for k in range(len(values)) if k != i and k != j]
            a, b = values[i], values[j]
            results = [a + b, a - b, a * b]
            if b != 0:
                results.append(a / b)
            for r in results:
                if solvable(rest + [r]):
                    return True
    return False


# --- (a) Ask directly ----------------------------------------------------------
def direct_prompt(numbers: list[int]) -> str:
    return (f"Use the numbers {', '.join(map(str, numbers))}, each exactly once, with + - * / and "
            f"parentheses, to make exactly {TARGET}. "
            "End your reply with exactly one line: Answer: <expression>")


def run_direct(numbers: list[int], n: int = 5) -> dict:
    stats = {"correct": 0, "calls": 0, "tokens": 0}
    for _ in range(n):
        try:
            r = ask(direct_prompt(numbers), temperature=0.7)
        except (errors.APIError, TimeoutError) as e:
            print(f"   provider error: {str(e)[:80]}")
            continue
        stats["calls"] += 1
        stats["tokens"] += r.in_tokens + r.out_tokens
        text = r.text.replace("**", "").replace("×", "*").replace("÷", "/")
        answers = re.findall(r"Answer:\s*(.+)", text)
        if not answers:
            print("   no 'Answer:' line")
            continue
        expr = answers[-1].split("=")[0].strip().strip("`")  # drop a trailing '= 24'
        problem = check_expression(expr, numbers)
        if problem == "":
            stats["correct"] += 1
        print(f"   {expr:<30} -> {'OK' if problem == '' else problem}")
    return stats


# --- (b) Search: propose -> code computes -> value -> keep the best 3 ---------
class Move(BaseModel):
    left: str = Field(description="One of the remaining numbers, written exactly as shown")
    op: Literal["+", "-", "*", "/"]
    right: str = Field(description="Another remaining number, written exactly as shown")


class Proposals(BaseModel):
    moves: list[Move]


class Rating(BaseModel):
    reason: str = Field(description="One short sentence, written BEFORE the verdict")
    verdict: Literal["sure", "likely", "impossible"]


# A state is a list of (value, expression), e.g. [(Fraction(13), '13'), (Fraction(36), '(4 * 9)')]
def show(state) -> str:
    return ", ".join(str(value) for value, _expr in state)  # Fraction(5, 2) is shown as 5/2


def values_of(state) -> list[Fraction]:
    return [value for value, _expr in state]


def apply_move(state, move: Move):
    """CODE does the arithmetic. Returns the new state, or None if the move is not possible."""
    try:
        a = Fraction(move.left)
        b = Fraction(move.right)
    except (ValueError, ZeroDivisionError):
        return None
    values = values_of(state)
    if a not in values:
        return None
    i = values.index(a)
    left = state[i]
    rest = state[:i] + state[i + 1:]
    rest_values = values_of(rest)
    if b not in rest_values:
        return None
    j = rest_values.index(b)
    right = rest[j]
    rest = rest[:j] + rest[j + 1:]

    if move.op == "+":
        result = left[0] + right[0]
    elif move.op == "-":
        result = left[0] - right[0]
    elif move.op == "*":
        result = left[0] * right[0]
    else:
        if right[0] == 0:
            return None
        result = left[0] / right[0]
    return rest + [(result, f"({left[1]} {move.op} {right[1]})")]


def propose(state, stats) -> list:
    prompt = (f"Remaining numbers: {show(state)}. Goal: make exactly {TARGET} at the end, using every number once. "
              f"Propose up to {MAX_PROPOSALS} different NEXT steps. Each step takes TWO of the remaining numbers "
              "and one operation (+ - * /). Do not compute the result: just choose the numbers and the operation.")
    r = ask(prompt, schema=Proposals, temperature=0.7)
    stats["calls"] += 1
    stats["tokens"] += r.in_tokens + r.out_tokens
    if r.parsed is None:
        return []
    children = []
    for move in r.parsed.moves[:MAX_PROPOSALS]:
        child = apply_move(state, move)
        if child is not None:
            children.append(child)
    return children


def value(state, stats) -> int:
    if len(state) == 1:  # one number left: code knows the answer, no model call
        return SCORE["sure"] if state[0][0] == TARGET else SCORE["impossible"]
    prompt = (f"Remaining numbers: {show(state)}. Can these numbers, each used exactly once with + - * / and "
              f"parentheses, make exactly {TARGET}? Answer sure (you can see a way), likely, or impossible.")
    r = ask(prompt, schema=Rating, temperature=0.0)
    stats["calls"] += 1
    stats["tokens"] += r.in_tokens + r.out_tokens
    if r.parsed is None:
        return SCORE["impossible"]
    return SCORE[r.parsed.verdict]


def run_search(numbers: list[int]) -> tuple[str | None, dict, str]:
    """Returns (expression or None, stats, who failed first: '' / 'propose ...' / 'value ...')."""
    stats = {"calls": 0, "tokens": 0}
    blame = ""
    frontier = [[(Fraction(n), str(n)) for n in numbers]]
    for depth in range(1, len(numbers)):  # 4 numbers -> 3 steps
        # PROPOSE: new states from every kept state (code computes them)
        candidates = []
        seen = set()
        for state in frontier:
            children = propose(state, stats)
            if blame == "" and solvable(values_of(state)) and not any(solvable(values_of(c)) for c in children):
                blame = f"propose (step {depth}): from [{show(state)}] no proposed move could still reach {TARGET}"
            for child in children:
                key = tuple(sorted(values_of(child)))
                if key not in seen:  # the same numbers in another order = the same state
                    seen.add(key)
                    candidates.append(child)

        # VALUE: rate every new state, keep the best BEAM
        scored = []
        for child in candidates:
            scored.append((value(child, stats), child))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        frontier = [child for score, child in scored[:BEAM]]  # the best 3, even if the model is pessimistic

        print(f"   step {depth}: {len(candidates)} new states, kept: "
              + (" | ".join(f"[{show(s)}]" for s in frontier) or "nothing"))
        if blame == "" and any(solvable(values_of(c)) for c in candidates) \
                and not any(solvable(values_of(c)) for c in frontier):
            blame = f"value (step {depth}): a state that could still reach {TARGET} was rated too low and dropped"
        if not frontier:
            break

    for state in frontier:
        if len(state) == 1 and state[0][0] == TARGET:
            expr = state[0][1][1:-1]  # drop the outer parentheses
            if check_expression(expr, numbers) == "":  # exact check, again by code
                return expr, stats, ""
    return None, stats, blame or "unclear"


# --- (c) Compare ---------------------------------------------------------------
if __name__ == "__main__":
    argv, nums, runs = sys.argv[1:], [], 1
    while argv:
        a = argv.pop(0)
        if a == "--runs":
            runs = int(argv.pop(0))
        else:
            nums.append(int(a))
    numbers = nums if len(nums) == 4 else NUMBERS
    print(f"Vouchers: {numbers}  (can code make {TARGET}? {solvable([Fraction(n) for n in numbers])})")

    try:
        print("\n== (a) ask directly, 5 times")
        d = run_direct(numbers)

        print(f"\n== (b) search, {runs} run(s)")
        s = {"correct": 0, "calls": 0, "tokens": 0, "finished": 0}
        failures = []
        for run in range(1, runs + 1):
            print(f" run {run}")
            try:
                expr, stats, blame = run_search(numbers)
            except (errors.APIError, TimeoutError) as e:  # the provider gave up: a failed run, not a crash
                print(f"   provider error, run skipped: {str(e)[:80]}")
                failures.append("provider error (not the model's fault)")
                continue
            s["finished"] += 1
            s["calls"] += stats["calls"]
            s["tokens"] += stats["tokens"]
            if expr:
                s["correct"] += 1
                print(f"   solved: {expr} = {TARGET}   ({stats['calls']} calls, {stats['tokens']:,} tokens)")
            else:
                failures.append(blame)
                print(f"   failed - first mistake: {blame}   ({stats['calls']} calls)")
    except QuotaExhausted as e:
        sys.exit(f"\n[stopped] {e}")

    print("\n== (c) comparison")
    print("| method | correct | model calls per try | tokens per try |")
    print("|---|---|---|---|")
    print(f"| direct | {d['correct']}/5 | 1 | {d['tokens'] / 5:,.0f} |")
    finished = max(s["finished"], 1)  # averages over the runs that finished (not the provider errors)
    print(f"| search | {s['correct']}/{runs} | {s['calls'] / finished:.0f} | {s['tokens'] / finished:,.0f} |")
    if failures:
        print("Search failures: " + "; ".join(failures))
