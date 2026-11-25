# Lab 4 notes

Model: gemini-3.5-flash-lite. Some runs had 429 (too many requests, it waits) and 503 (Google servers
busy). 503 is not a mistake of the model.

---

## Exp 1 - what does the model know

- today's date: refused
- flight price: refused, told me to check Skyscanner etc.
- concerts in May 2027: refused, said its knowledge stops in January 2025
- Borghese Gallery: answered from memory, but said it is "current information"

So: dates, prices, opening hours should come from tools. The model also does not know the year
(in Exp 5 it wrote "12 May 2024").

## Exp 2 - budget question (correct: yes, 34 EUR left)

| prompt | correct | avg output tokens | vote |
|---|---|---|---|
| short | 0/5 | 9 | 163 (1/5) -> wrong |
| better | 5/5 | 279 | 34 (5/5) -> correct |
| --code (model writes expression, code computes) | 5/5 | ~133 | - |

- short: no room to calculate, it guesses
- better: correct, but many more tokens
- voting does not help if all answers are wrong
- --code: correct and cheaper than "better"

## Exp 3 - ask before you plan

- --vague: no questions, about 10 assumptions (start city, destination, budget, people, interests...).
  It made 3 different plans (USA, Spain, Italy).
- --simulate: 4 questions, one at a time, then `missing: nothing`.
- Checkpoint 1: the **code** stopped the interview (`missing_required()` was empty), not the model.
- Problem: dates stayed "4 days in May", it never asked the exact dates.

## Exp 4 - a day that works

| variant | valid | avg output tokens |
|---|---|---|
| plain | 0/5 | 211 |
| hint in prompt | 0/5 | 211 |
| hint + plan field | 4/5 | 1,735 |

- most errors: "Colosseum cannot start at 11:30" (it adds the 30 min move but forgets it must start
  on the hour)
- the hint alone did nothing; with a `plan` field it works much better, but costs more tokens
- all 11 tests pass

## Exp 5

See homework C.

---

## Homework C

(a) `execute()` done, tests: 16 passed.

(b) `python exp5_tools.py --runs 3`

| q | mode | correct | LLM calls | input tokens | tool s | total s |
|---|---|---|---|---|---|---|
| 1 | loop | 3/3 | 2 | 1,150 | 4.0 | 6.1 |
| 1 | plan | 2/3 (503) | 2 | 368 | 4.0 | 6.6 |
| 1 | parallel | 2/3 (503) | 2 | 368 | 1.0 | 10.0 |
| 2 | loop | 3/3 | 2 | 967 | 3.0 | 4.6 |
| 2 | plan | 3/3 | 2 | 216 | 3.0 | 13.3 |
| 2 | parallel | 3/3 | 2 | 216 | 1.0 | 5.8 |
| 3 | loop | 3/3 | 3 | 1,749 | 4.0 | 18.2 |
| 3 | plan | 0/3 | 2 | 302 | 3.0 | 5.8 |
| 3 | parallel | 0/3 | 2 | 302 | 2.0 | 11.6 |
| 4 | loop | 3/3 | 3 | 1,566 | 3.0 | 5.1 |
| 4 | plan | 3/3 | 2 | 338 | 3.0 | 5.0 |
| 4 | parallel | 3/3 | 2 | 338 | 2.0 | 12.3 |

Same every time: Q3 loop 3/3 but plan/parallel 0/3; loop uses more tokens; parallel has less tool time.
Noise: total seconds (because of 429/503 waits).

Checkpoint questions:
1. tool time vs total time: parallel makes tools faster (4 s -> 1 s) but total time is mostly the model
2. dependencies: Q4 needs the airport first, so parallel still takes 2 rounds (2 s)
3. surprising result: Q3 has no direct flight to Lisbon; the loop sees it and asks for flights via
   Bucharest, the plan cannot change, so it says prices are missing
4. year: the model wrote 2024

(c) Q3 in loop mode: correct (39 + 167 + 222 = 428). No missing facts. The model adds the numbers
itself, so the risk is a calculation mistake. With `--sum` it called `sum_eur` and the code added
them: still correct, 1 more call, 3,046 tokens instead of 1,749.
`sum_eur` is hard for plan modes because the plan is written before the tools run, so the numbers are
not known yet, and `@s1` gives the whole JSON, not just the price.

## Homework A - 24 from 4, 9, 10, 13

| method | correct | calls | tokens |
|---|---|---|---|
| direct | 5/5 | 1 | 387 |
| search | 0/3 | 27 | 3,251 |

- direct always found (13 - 9) * (10 - 4)
- search failed 3 times, every time because of `propose` (the good move was not proposed),
  e.g. from [9, 13, 6] it did not propose 13 - 9
- in one earlier run it failed because of `value` (it said "impossible" for all states)
- for an easy puzzle, direct is better and much cheaper

## Homework B - nights_between

Clear prompt: plain 5/5 and lessons 5/5, all on the first attempt, no lessons needed.

Vague prompt (`--vague`):

| variant | solved | avg attempts | avg tokens |
|---|---|---|---|
| plain retries | 5/5 | 2.0 | 486 |
| retries + lessons | 5/5 | 1.4 | 498 |

- plain: always failed "reversed dates" first, then fixed it
- lessons: runs 3, 4, 5 passed on the first try
- lesson 1 was almost right but too strict (it then rejected the same day), lesson 2 fixed it
- so lessons help, but they can be wrong too
