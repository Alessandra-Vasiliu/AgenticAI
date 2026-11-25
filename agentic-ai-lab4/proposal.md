# Lab 4 - Part 0 and Part 6 (trip planner)

## Part 0

**1. What must the agent know before it can plan?**
- from the traveller: where from, where to, dates, how many people, budget, interests
- from the world: flight and hotel prices, opening hours, weather, today's date
- from a calculation: number of nights, total cost, if it fits the budget

**2. The tasks, in order**
1. ask the traveller what is missing
2. get prices and weather for the cities (these are independent, they can run at the same time)
3. add up the total cost (needs step 2)
4. choose the destination (needs step 3)
5. make the day schedule (needs step 4)

**3. What must be exactly right, and how can code check it?**
- the total cost -> code adds the prices
- the number of nights -> code computes it from the dates
- the day schedule -> a verifier like `check()` from Exp 4

**4. Where can I trust the model?**
- yes: general ideas (what to see, what fits the interests), writing the answer
- no: today's date, prices, opening hours, weather, and its own math

**5. Where must a human decide?**
- choosing between destinations, going over the budget, booking and paying

**6. Cost of one plan**
- around 15-20 model calls and 1-2 minutes (more if there are 429/503 errors)

---

## Part 6

| Task | Info comes from | How I build it | How it is checked | Cost |
|---|---|---|---|---|
| What the traveller wants | the traveller | interviewer, one question at a time (Exp 3: 4 questions vs ~10 assumptions without it) | code: `missing_required()` | ~5 calls |
| Total cost of a trip | tools + calculation | tools give the prices, code adds them (Exp 2: model alone 0/5, code computes 5/5) | exact sum in code | almost 0 |
| A valid day schedule | rules + model | model with a `plan` field, a few tries (Exp 4: 0/5 without, 4/5 with) | code: `check()`, then `best()` | ~1,700 tokens per try |
| Prices for 5 cities | tools | plan + parallel (Exp 5: tools 1 s instead of 4 s, fewer tokens) | prices must come from tools; if something is unexpected, use the loop (Exp 5 Q3: loop 3/3, plan 0/3) | 2 calls |

**Sketch**

```
traveller -> [interviewer] -> code checks the brief is complete
                                   |
                             [orchestrator]
                              /          \
                   [prices worker]   [weather worker]    (in parallel)
                              \          /
                    code adds the total, checks the budget
                                   |
                   HUMAN chooses the destination
                                   |
                          [schedule worker]
                                   |
                     code checks the schedule (check)
                                   |
                     final plan -> HUMAN approves booking
```

**Where it can still go wrong:** when a tool gives something unexpected (no direct flight, closed museum),
the plan cannot change by itself. I would notice because the code checks fail (missing price, invalid
schedule, over budget).

**Another idea - study planner, question 1:**
- from the student: courses, exam dates, free hours per day
- from the world: the official exam calendar and deadlines
- from a calculation: days left until each exam, if all study hours fit
