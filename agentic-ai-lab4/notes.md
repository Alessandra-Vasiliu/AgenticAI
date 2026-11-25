# Lab 4 - Notes (lab experiments + homework)

Model: gemini-3.5-flash-lite (free tier). Some runs hit `429` (rate limit, the code waits and retries)
and `503` (Google servers overloaded). A `503` is not a model mistake, so I count it separately.

---

# Lab experiments

## Experiment 1: What does the model know? (`python exp1_knowledge.py`)

| probe | answer |
|---|---|
| today's date | refused: "no access to real-time information" |
| cheapest flight Iasi -> Rome | refused, suggested Google Flights / Skyscanner / Kayak |
| concerts in Rome, May 2027 | refused: "my knowledge cutoff is January 2025" |
| Borghese Gallery on Mondays | answered **confidently**: closed on Mondays, 9:00-19:00, tickets in advance |

- For things that change often (date, prices, events) the model refuses. Good.
- For the Borghese Gallery it answered from memory but called it "the current information". It may be
  right, but it may also be out of date, and nothing in the answer shows that it comes from memory.
- The model thinks it is around January 2025. This is why it wrote "12 May 2024" in Experiment 5.
- For the agent: dates, prices and opening hours must come from tools, not from the model.

## Experiment 2: The budget question (`python exp2_budget.py`, then `--code`)

Correct answer: 516 + 340 + 20 + 90 = 966 EUR, so yes, 34 EUR under the budget.

| prompt | correct out of 5 | average output tokens | vote result (bonus 1) |
|---|---|---|---|
| short | 0/5 | 9 | ('yes', 163) with 1/5 votes -> wrong |
| better (room to reason) | 5/5 | 279 | ('yes', 34) with 5/5 votes -> correct |
| bonus 2: the model writes the expression, code computes | 5/5 | ~133 | - |

- Short prompt: the model has to write the result without working it out, so it guesses (136-167 EUR)
  and is wrong every time.
- Better prompt: it writes every cost, then adds them, and is right every time, for ~30x more tokens.
- Voting cannot fix the short prompt: the 5 answers were all different and all wrong, so the "majority"
  is wrong too. Voting only helps when most answers are already right.
- Bonus 2: the model only writes the arithmetic and `evaluate()` computes it exactly (966). Just as
  correct as "better", with about half the tokens.

## Experiment 3: Ask before you plan (`--vague`, then `--simulate`)

**Step A (`--vague`):** no question asked, about **10 assumptions**: where I start from (it flew from Las
Vegas, Bilbao, Naples), the destination (3 options: USA, Spain, Italy), the budget (from "budget-friendly"
to Michelin restaurants), how many people, interests (nature / food / relaxation), a packed pace with early
starts, fitness (long hikes, 1,500 steps), a rental car, the exact dates, and even the units (Fahrenheit).
It admitted it did not know my starting point or budget, but instead of asking it wrote three long plans.

**Step B (`--simulate`, Ana):** 4 questions, one at a time:

| planner asked | Ana answered | brief |
|---|---|---|
| Where are you traveling from? | Iasi, with a friend | origin: Iasi, travelers: 2 |
| Where would you like to go? | no idea, somewhere in Italy | destination: Italy |
| Total budget in EUR? | 1000 EUR | budget_eur: 1000 |
| Main interests? | street food, old history, no early mornings | interests + avoid: early mornings |

`[Brief after 4 questions] missing: nothing`

- **Checkpoint 1: the code stopped the interview**, not the model: `missing_required()` returned an
  empty list, so the harness decided the brief was complete.
- Weak point: `dates` stayed "4 days in May" (from the first message), so it never asked for the exact
  dates (Ana's are 12-16 May). The harness only checks that a field is not empty, not that it is precise
  enough. A stricter check (exact dates required) would need more questions.
- It also saved what to avoid (early mornings) without being asked; `pace` stayed null because Ana never
  said anything about it.

## Experiment 4: A day that actually works (`python exp4_day.py`)

- `check()` and `best()` are implemented: all 11 tests in `test_exp4_day.py` pass (no API calls).
- Run on 26 November with `gemini-3.5-flash-lite` (on 25 November both models returned `503`).

| variant | valid out of 5 | average output tokens |
|---|---|---|
| plain | 0/5 | 211 |
| hint in the prompt, JSON only | 0/5 | 211 |
| hint + a field to plan in (`plan` before `items`) | **4/5** | 1,735 |

`chosen: 09:00 Borghese Gallery | 12:00 Lunch | 14:00 Colosseum | 16:30 Pantheon | 18:00 Trastevere food walk`

- Almost every failure was the same: "Colosseum (or Borghese Gallery): cannot start at 11:30". The model
  puts the next item 30 minutes after the previous one (move time), but these two can only start on the
  hour / at fixed times. It remembers one rule and forgets the other.
- The hint alone changed nothing (0/5, and the same 211 tokens): with "JSON only" the model has no place
  to actually do the planning the hint asks for.
- With a `plan` field written BEFORE `items`, the model works it out first and 4/5 schedules are valid,
  but it costs about 8x more output tokens.
- The verifier is what makes this safe: the code checks every schedule, so an invalid one is never used.
  `best()` then keeps only valid schedules and picks the one with the latest first item (here all valid
  ones started at 09:00).

## Experiment 5

Same runs as homework C below (table, checkpoint questions, `sum_eur`).

---

# Homework

## C. Run the tools yourself

### (a) `execute()`
- A step is **ready** when every `@s` reference in its arguments already has a result.
- `parallel=False`: the ready steps run one by one. `parallel=True`: all ready steps run at the same time
  (`ThreadPoolExecutor.map`), then the code looks again for new ready steps.
- If nothing is ready (a reference to a step that does not exist), the first pending step runs as it is,
  so the plan never hangs.
- `pytest test_exp4_day.py test_exp5_tools.py -v` -> **16 passed**.

### (b) Full table, `python exp5_tools.py --runs 3`

| question | mode | correct | LLM calls | input tokens | tool seconds | total seconds |
|---|---|---|---|---|---|---|
| 1 | loop | 3/3 | 2 | 1,150 | 4.0 | 6.1 |
| 1 | plan | 2/3 (one 503) | 2 | 368 | 4.0 | 6.6 |
| 1 | parallel | 2/3 (one 503) | 2 | 368 | 1.0 | 10.0 |
| 2 | loop | 3/3 | 2 | 967 | 3.0 | 4.6 |
| 2 | plan | 3/3 | 2 | 216 | 3.0 | 13.3 |
| 2 | parallel | 3/3 | 2 | 216 | 1.0 | 5.8 |
| 3 | loop | 3/3 | 3 | 1,749 | 4.0 | 18.2 |
| 3 | plan | **0/3** | 2 | 302 | 3.0 | 5.8 |
| 3 | parallel | **0/3** | 2 | 302 | 2.0 | 11.6 |
| 4 | loop | 3/3 | 3 | 1,566 | 3.0 | 5.1 |
| 4 | plan | 3/3 | 2 | 338 | 3.0 | 5.0 |
| 4 | parallel | 3/3 | 2 | 338 | 2.0 | 12.3 |

**Consistent differences (the same in every run):**
- Question 3 (Lisbon): `loop` 3/3, `plan` and `parallel` 0/3.
- `loop` uses 3-5x more input tokens (1,150 vs 368 on Q1, 1,749 vs 302 on Q3), because every step sends
  the whole conversation again.
- `parallel` has the smallest tool time (1.0 s vs 4.0 s on Q1, 1.0 s vs 3.0 s on Q2).

**Noise:**
- Total seconds. For example `parallel` on Q1 took 10.0 s, more than `plan` (6.6 s). The total time is
  dominated by the model calls and by the 429/503 waits, not by the tools.
- The two failures on Q1 were `503` errors from the provider, not wrong answers.

**Checkpoint questions:**
1. *Tool time vs total time:* parallel tools save seconds on the tools (4.0 -> 1.0 s), but the total
   time is mostly the model and the provider (rate limits, overload), so the saving is often hidden.
2. *Dependency order:* on Q4 the flight price needs the result of `nearest_airport` (`@s1`), so even in
   parallel mode it waits: tool time is 2.0 s (two rounds), not 1.0 s.
3. *Surprising results:* on Q3 the tool answered "No direct flight Iasi-Lisbon, connect via Bucharest".
   The loop read this and asked for the two flights via Bucharest. The plan was written before any tool
   ran, so it could not change, and the answer said the prices were missing.
4. *The year:* the answers say "12 May **2024**". The model does not know today's date and assumes a
   year from its training (same as Experiment 1).

### (c) Question 3 in loop mode, with and without `sum_eur`

| | without `--sum` | with `--sum` |
|---|---|---|
| correct | 1/1 | 1/1 |
| LLM calls | 3 | 4 |
| input tokens | 1,749 | 3,046 |
| who adds 39 + 167 + 222 | the model, in its answer | `sum_eur([39, 167, 222])` -> 428.0 |

- In my runs the loop never made a mistake: it found all the facts (it asked for Iasi->Bucharest and
  Bucharest->Lisbon after the first tool result), so there was no missing fact.
- The only risky part is the final addition, which the model does in its head. A mistake there would be
  a calculation mistake, not a missing fact. With `sum_eur` the code adds exactly, for one more LLM call
  and about 1,300 more input tokens.
- **Why `sum_eur` is hard to give to the plan modes:** the plan is written before any tool runs, but the
  numbers to add only exist after the tools run. `@s1` puts the whole result into the argument (the JSON
  text `{"route": ..., "price_eur": 39}`), not just the number 39. Also, on Q3 the planner does not know
  in advance that it will need the connection via Bucharest.

---

## A. The voucher puzzle (4, 9, 10, 13 -> 24)

`python hw_a_vouchers.py --runs 3`

| method | correct | model calls per try | tokens per try |
|---|---|---|---|
| direct | 5/5 | 1 | 387 |
| search (propose -> code -> value, keep best 3) | 0/3 | 27 | 3,251 |

- Direct: the model found `(13 - 9) * (10 - 4)` every time.
- Search: 27x more calls and about 8x more tokens, and it never solved the puzzle.
- **The failures came from `propose`, every time:**
  - run 1: already at step 1, none of the 5 proposed moves could still reach 24;
  - runs 2 and 3: `value` correctly kept the state [9, 13, 6], which can still make 24 ((13 - 9) * 6),
    but none of the 5 proposed next moves led there.
- In an earlier run (before I changed the code to always keep the best 3 states) the failure came from
  `value`: it rated all 5 states after step 1 as "impossible".
- The code did all the arithmetic (results like 13/4 and 65/2), so no failure came from a calculation.
- Conclusion: on an easy puzzle the direct answer is cheaper and better. The search depends on the
  proposals: if the good move is not among the 5 proposed, a good `value` cannot save it.

---

## B. Learn from a failed test (`nights_between`)

Generated code runs in a separate process (`subprocess`, timeout 5 s), against 10 tests: same day,
normal stay, month end, year end, leap year, not a leap year, reversed dates, three malformed dates.

**1. Clear prompt (the rules for reversed and malformed dates are written in the prompt):**

| variant | solved | average attempts | average tokens |
|---|---|---|---|
| plain retries | 5/5 | 1.0 | 294 |
| retries + lessons | 5/5 | 1.0 | 293 |

Every first attempt passed, so there was nothing to learn and no lessons were written.

**2. Vague prompt (`--vague`: only "return the number of nights"):**

| variant | solved | average attempts | average tokens |
|---|---|---|---|
| plain retries | 5/5 | 2.0 | 486 |
| retries + lessons | 5/5 | 1.4 | 498 |

- Plain retries: every run failed "reversed dates" first (returned -4 instead of raising ValueError)
  and fixed it on attempt 2. The next run started from zero again.
- With lessons: runs 1 and 2 needed 2 attempts, runs 3, 4 and 5 passed on the first attempt, because
  the lessons were in the prompt. Fewer attempts for almost the same tokens.

**Were the lessons correct?**
1. *"... you must explicitly check that the start date precedes the end date and raise an exception
   otherwise."* Mostly correct, but too strict: "precedes" means strictly before. In run 2 the model
   followed it and rejected the same day (raised ValueError instead of returning 0).
2. *"The code strictly enforced a strict 'earlier than' condition, which incorrectly rejected identical
   dates ..."* Correct: it fixed the mistake caused by lesson 1.

Conclusion: lessons help when the prompt is vague, but a lesson that is only almost right can create a
new bug, so the lessons also need to be checked.
