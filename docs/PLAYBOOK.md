# Build Playbook — Weather-Aware Truck Routing

How to build, commit, review and present this project so it scores high on every rubric line.
Pair this with [PRD.md](./PRD.md) (the *what*). This file is the *how*.

---

## 0. The 5 rules that win this assessment

1. **Logic first, pixels second.** Risk engine + ranking are 40% of the grade. Write them as pure,
   tested functions before touching the map.
2. **Deploy on day 1.** A "hello world" deployed early removes the scariest last-minute risk.
3. **Never fetch on slider move.** Load 49 hours once; the slider only swaps frames. This is the
   single biggest "smoothness" signal.
4. **Small PRs, real history.** Reviewers *will* open your commit log. Show an engineer who plans.
5. **Write down every assumption.** Ambiguity handled explicitly reads as seniority.

---

## 1. Schedule (4 days, ~13h, 3h buffer under the 16h cap)

| Day | Date | Focus | Hours | Exit criteria |
|---|---|---|---|---|
| 1 | Tue Oct 20 | Repo, CI, skeleton deploy, routing spike, routes API | 3.5 | 3 routes return from deployed backend |
| 2 | Wed Oct 21 | Sampling + ETAs, weather client, risk engine, ranking | 3.5 | `/api/trips/plan` returns recommended route, tests green |
| 3 | Thu Oct 22 | Map, route cards, checkpoints, heatmap + slider | 4 | Full flow works in browser |
| 4 | Fri Oct 23 | Perf pass, error states, README, Loom, **submit** | 2 | Links sent to Spotter |

Track real hours in a note. If you mention "~13h of the 16h budget" in the README, it signals discipline.

---

## 2. One-time GitHub setup (15 min)

```bash
# from the project root
git init -b main
gh repo create spotter-truck-routing --public --source=. --remote=origin

# labels
gh label create backend   --color 1d76db
gh label create frontend  --color 5319e7
gh label create logic     --color d93f0b --description "Risk/ranking/ETA correctness"
gh label create perf      --color fbca04
gh label create infra     --color 0e8a16
gh label create docs      --color c5def5
gh label create spike     --color bfdadc

# milestones (match PRD §12)
for m in "M1 Skeleton" "M2 Routes" "M3 Risk Engine" "M4 Map UI" "M5 Heatmap" "M6 Ship"; do
  gh api repos/:owner/:repo/milestones -f title="$m"
done
```

Optional but impressive: create a GitHub **Project board** (Todo / In progress / Done) and attach issues.

Repo settings: enable **Squash merge only**, enable "Automatically delete head branches".

---

## 3. Issue backlog (create all on Day 1)

Each issue = one PR. Copy titles as-is; the body uses `.github/ISSUE_TEMPLATE/task.md`.

| # | Title | Labels | Milestone | Acceptance criteria |
|---|---|---|---|---|
| 1 | chore: scaffold monorepo (Django + Vite React TS) | infra | M1 | `backend/` and `frontend/` run locally; `.env.example` for both |
| 2 | ci: GitHub Actions for lint, typecheck, tests, build | infra | M1 | Workflow green on PR; badge in README |
| 3 | chore: deploy skeleton (Render + Vercel) | infra | M1 | Deployed frontend calls deployed `/api/health` |
| 4 | spike: validate routing provider for 3 truck alternatives | spike, backend | M2 | Decision + limits noted in README "Decisions" section |
| 5 | feat(api): geocode endpoint with autocomplete | backend | M2 | `GET /api/geocode?q=` returns ≤5 results; 400 on empty q |
| 6 | feat(routing): fetch 3 route options with via-point fallback | backend | M2 | Always 3 routes or a clear error; provider behind interface |
| 7 | feat(domain): checkpoint sampling with ETA interpolation | backend, logic | M2 | 10/25/50 mi intervals; origin+dest included; ETA from step durations; unit tests |
| 8 | feat(weather): batched + cached Open-Meteo client | backend | M3 | One HTTP call per ≤100 points; cache hit on repeat; units mph / in |
| 9 | feat(domain): risk classification with load rules | backend, logic | M3 | All thresholds + boundaries tested (24.9/25/34.9/35/…/55) |
| 10 | feat(domain): route ranking and recommendation reason | backend, logic | M3 | Lexicographic sort per PRD §6; tie-break tests; reason string |
| 11 | feat(api): POST /api/trips/plan end-to-end | backend | M3 | Validated input; response matches PRD §7; integration test with mocked providers |
| 12 | feat(ui): trip form with autocomplete, datetime, load, interval | frontend | M4 | Validation messages; disabled submit while loading |
| 13 | feat(map): render routes, checkpoints, popups, route cards | frontend | M4 | Recommended highlighted; click card ↔ focus route; risk colors legend |
| 14 | feat(api): corridor heatmap endpoint (49 hourly frames) | backend, perf | M5 | ≤300 grid points; compact arrays; < 3s cold, < 300ms cached |
| 15 | feat(map): heatmap layer with 0–48h slider | frontend, perf | M5 | No network on slide; 60fps scrub; truck marker moves along recommended route |
| 16 | feat(ui): loading, empty and error states | frontend | M6 | Every failure has a human message + retry |
| 17 | docs: README, assumptions, architecture diagram | docs | M6 | Setup in < 5 commands; assumptions list; screenshots/GIF |

Create them fast:
```bash
gh issue create -t "feat(domain): risk classification with load rules" \
  -l backend,logic -m "M3 Risk Engine" -b "See PRD §5. AC: all thresholds and boundaries tested."
```

---

## 4. Branch → Commit → PR workflow

### Branch naming
```
<type>/<issue#>-<short-slug>
feat/9-risk-engine
fix/21-eta-timezone
chore/1-scaffold
```

### Commit messages — Conventional Commits
```
<type>(<scope>): <imperative summary, ≤ 72 chars>

<optional body: WHY, not what>

Refs #<issue>
```
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `perf`, `style`.
Scopes: `api`, `routing`, `weather`, `domain`, `ui`, `map`, `heatmap`, `ci`, `deploy`.

**Rules:** one logical change per commit; tests in the same commit as the code they test (or the
commit right before, TDD style); never commit `.env` or API keys; no "wip" / "fix stuff" commits on
`main` (squash merge cleans branch noise).

### Example commit sequence for issue #9 (risk engine)
```
test(domain): add boundary cases for wind, rain and snow thresholds
feat(domain): classify checkpoint weather into risk levels
feat(domain): apply load-weight rules to wind risk
refactor(domain): return risk drivers alongside level
```

### Example sequence for issue #15 (heatmap slider)
```
feat(heatmap): render corridor risk with deck.gl HeatmapLayer
feat(heatmap): add 0-48h slider driving frame index
perf(heatmap): memoize frame data so slider never refetches
feat(map): animate truck marker along recommended route by hour
```

### PR rules
- PR title = the squash commit message (Conventional Commit format), e.g. `feat(domain): risk classification with load rules (#9)`
- Body follows `.github/pull_request_template.md`; **include a screenshot/GIF for any UI PR**
- `Closes #9` in the body so issues auto-close
- Keep PRs < ~400 changed lines; split otherwise
- **Self-review before merging**: open "Files changed", leave 1–2 comments on non-obvious decisions
  (reviewers love seeing you reason about your own code)
- Merge only when CI is green

### Daily loop
```bash
git switch main && git pull
git switch -c feat/9-risk-engine
# ...code + tests, small commits...
git push -u origin feat/9-risk-engine
gh pr create --fill --label backend,logic --milestone "M3 Risk Engine"
gh pr checks --watch
gh pr merge --squash --delete-branch
```

---

## 5. Definition of Done (every PR)

- [ ] Acceptance criteria from the issue are met
- [ ] Unit tests for new logic; all tests pass locally and in CI
- [ ] Lint + typecheck clean (`ruff`, `eslint`, `tsc --noEmit`)
- [ ] No secrets; new env vars added to `.env.example`
- [ ] UI change has screenshot/GIF in PR
- [ ] Assumption added to README if one was made

---

## 6. Must-have tests (the 40% logic score lives here)

**Risk engine (`test_risk.py`)** — parametrize every boundary:
| Input | Expected |
|---|---|
| wind 24.9 / 25 / 34.9 / 35 / 44.9 / 45 / 54.9 / 55 | LOW / MOD / MOD / HIGH / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| rain 0.09 / 0.10 / 0.25 / 0.50 / 1.00 / 1.01 | LOW / MOD / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| snow 0.49 / 0.5 / 1.0 / 2.0 / 3.0 / 3.01 | LOW / MOD / HIGH / SEVERE / SEVERE / NO_TRAVEL |
| wind 50, load 30,000 vs 30,001 | SEVERE vs NO_TRAVEL |
| wind 40, load 40,000 vs 40,001 | HIGH vs SEVERE |
| wind 10, rain 0.6, snow 0 | SEVERE (max of conditions) |

**Ranking (`test_ranking.py`)**: fewer severe miles beats faster route; tie on severe → high miles
decides; full tie → shorter duration wins; any no-travel miles lose to severe-only route.

**Sampling (`test_sampling.py`)**: interval 25 on a 100-mi line → checkpoints at 0,25,50,75,100;
last partial segment included; ETA interpolation monotonic; UTC-safe across DST.

**API (`test_plan_api.py`)**: providers mocked; 400 on bad input; response schema matches PRD §7.

---

## 7. README skeleton (docs = 5%, but it's the first thing they open)

```
# Weather-Aware Truck Routing   [CI badge] [Live demo link] [Loom link]
GIF of the slider scrubbing the heatmap

## What it does (3 bullets)
## Live demo / Loom
## Architecture (diagram: React -> Django -> ORS / Open-Meteo)
## How risk & recommendation work (table + ranking tuple)
## Assumptions & decisions (copy PRD §9 + routing spike result)
## Performance notes (batching, caching, precomputed frames)
## Run locally (≤5 commands)
## Tests
## What I'd do next (HOS breaks, gusts option, Redis, E2E tests)
```

---

## 8. Loom script (7–8 min target)

| Time | Show | Say |
|---|---|---|
| 0:00 | Live app | "Hi, I'm Hosama. This app picks the safest truck route by forecasting weather at the time the truck reaches each checkpoint." |
| 0:30 | Fill form (pick a route with real weather, e.g. through the Rockies) | Inputs, 25-mi interval, heavy load 42,000 lb |
| 1:30 | Results | 3 routes, recommended badge, reason string, miles by level |
| 2:30 | Click checkpoints | ETA-based weather, why this checkpoint is Severe (load rule) |
| 3:30 | Heatmap slider | Scrub 0→48h; point out zero network calls in DevTools; truck marker moving |
| 4:30 | Code: `domain/risk.py` + tests | Pure functions, boundary tests, load rules |
| 5:30 | Code: `ranking.py`, `services.py` | Ranking tuple, assumption about No Travel, batching + cache |
| 6:30 | GitHub | Issues, PRs, CI, commit history |
| 7:15 | Wrap-up | Trade-offs + what I'd do next |

Tips: warm up the backend before recording (cold starts); record at 1080p; close notifications;
have the trip pre-chosen so weather is interesting.

---

## 9. Interview prep — questions you'll likely get

| Question | Strong answer (in your words) |
|---|---|
| Why sample weather at ETA instead of now? | Risk depends on where the truck *will be* when. Storms move; a clear road now can be severe in 6h. |
| How do you attribute miles to a risk level? | Each segment takes the worse of its two checkpoints — conservative, safety-first. Smaller interval = more precise, more API calls. |
| Why rank No Travel above Severe? | Spec lists Severe first but No Travel is strictly worse; I documented it as an assumption. |
| Sustained wind or gusts? | Sustained for classification to match the table; gusts shown. Easy toggle if the business prefers gusts. |
| How is the slider smooth? | One request returns 49 hourly frames as compact arrays; GPU layer via deck.gl; slider changes an index, memoized data, no refetch. |
| What if the routing API gives < 3 routes? | Via-point fallback that offsets the midpoint perpendicular to the route; provider behind an interface so it's swappable. |
| How do you avoid weather rate limits? | Batch multi-location calls, round coordinates, cache by (cell, hour) with TTL. |
| How would you scale this? | Redis cache, Celery for heatmap precompute, own OSRM/Valhalla instance with truck profile, vector-tile weather. |
| What's missing for production? | HOS breaks, truck restrictions (bridges/hazmat), real-time re-routing, alerts, auth, observability. |
| Hardest bug? | Have a real one ready (timezones/ETA interpolation is a likely candidate). Tell it as: symptom → cause → fix → test added. |
| Did you use AI? | Be honest. Say what it helped with and show you understand and can change every line. |

Practise saying the **ranking tuple** and the **load rules** from memory. That's the core of the
domain and the most likely live-change request ("Can you make gusts count?" / "Add ice?").

**Be ready for a live change.** Design so these are 5-minute edits:
- New condition (ice/visibility) → add a threshold table entry in `risk.py`
- Change interval options → one constant
- Swap routing provider → new class implementing `RoutingProvider`

---

## 10. Final submission checklist

- [ ] Live URL works in an incognito window
- [ ] Backend warm; health endpoint OK
- [ ] README has live link, Loom link, CI badge, assumptions
- [ ] All issues closed or labelled "future"; no open PRs
- [ ] No secrets in git history (`git log -p | grep -i key`)
- [ ] Loom 5–10 min, public link, sound checked
- [ ] Hours logged ≤ 16
- [ ] Submit via the Teamtailor question: GitHub link + hosted link + Loom link, plus a 3-line summary

**Submission message template**
> Hi Ena, please find my assessment below.
> GitHub: <link> · Live app: <link> · Loom: <link>
> Built in ~13h with Django + React. The routing, weather-at-ETA risk engine and recommendation
> logic are fully unit-tested, and the 0–48h heatmap scrubs with no network calls. Assumptions are
> listed in the README. Thank you!
