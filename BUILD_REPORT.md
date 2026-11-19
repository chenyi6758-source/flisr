# flisr — BUILD_REPORT

Built 2026-11-19. Spec: the week's original-project brief (FLISR) plus the
research note `original-project-2026-11-19-research.md` (scope, validation
plan and honesty boundaries are binding). Environment:
`~/workspace/heatrate-venv/bin/python` (Python 3.12.3, pandapower 3.5.6,
numpy, scipy, pytest 9.2.0, ruff 0.17.4). Local build + verification only
— no GitHub repository was created and nothing was pushed (that step is
the parent agent's).

## Measured results (all numbers from actual runs)

### Base cases (validation vs literature)

| case | buses / lines / ties | total load | base loss: literature | base loss: measured | base min voltage |
|---|---|---|---|---|---|
| case33 | 33 / 37 / 5 | 3.715 MW | 202.69 kW | **202.68 kW** | 0.9131 p.u. |
| case69 | 69 / 73 / 5 | 3.802 MW | 224.99 kW | **224.99 kW** | 0.9092 p.u. |
| small (synthetic) | 10 / 11 / 2 | 1.300 MW | — (not a literature system) | 1.79 kW | 0.9975 p.u. |

### Single-fault sweep, IEEE 33-bus

| fault line | dead buses | outage load | restored | % of outage | shed | tie | final min V | loss healthy/isolated/restored |
|---|---|---|---|---|---|---|---|---|
| 1 | 32 | 3.715 MW | 0.000 MW | 0.0% | 0.000 MW | — | 1.0000 | 202.7 / 0.0 / 0.0 kW |
| 2 | 27 | 3.255 MW | 1.455 MW | 44.7% | 1.800 MW | 33 | 0.9053 | 202.7 / 1.3 / 118.4 kW |
| 3 | 23 | 2.235 MW | 1.425 MW | 63.8% | 0.810 MW | 33 | 0.9059 | 202.7 / 16.2 / 132.8 kW |
| 6 | 12 | 1.075 MW | 1.075 MW | 100.0% | 0.000 MW | 35 | 0.9263 | 202.7 / 93.1 / 168.2 kW |
| 10 | 8 | 0.555 MW | 0.555 MW | 100.0% | 0.000 MW | 35 | 0.9277 | 202.7 / 130.0 / 155.1 kW |
| 12 | 6 | 0.450 MW | 0.450 MW | 100.0% | 0.000 MW | 34 | 0.9167 | 202.7 / 140.7 / 197.3 kW |
| 18 | 4 | 0.360 MW | 0.360 MW | 100.0% | 0.000 MW | 33 | 0.9027 | 202.7 / 199.4 / 250.0 kW |
| 22 | 3 | 0.930 MW | 0.090 MW | 9.7% | 0.840 MW | 37 | 0.9159 | 202.7 / 163.3 / 177.4 kW |
| 25 | 8 | 0.920 MW | 0.920 MW | 100.0% | 0.000 MW | 37 | 0.9294 | 202.7 / 76.6 / 183.3 kW |
| 30 | 3 | 0.420 MW | 0.060 MW | 14.3% | 0.360 MW | 36 | 0.9143 | 202.7 / 141.3 / 152.6 kW |

### Single-fault sweep, IEEE 69-bus

| fault line | dead buses | outage load | restored | % of outage | shed | tie | final min V | loss healthy/isolated/restored |
|---|---|---|---|---|---|---|---|---|
| 1 | 68 | 3.802 MW | 0.000 MW | 0.0% | 0.000 MW | — | 1.0000 | 225.0 / 0.0 / 0.0 kW |
| 5 | 41 | 2.677 MW | 1.433 MW | 53.5% | 1.244 MW | 69 | 0.9442 | 225.0 / 2.5 / 63.7 kW |
| 6 | 40 | 2.674 MW | 1.430 MW | 53.5% | 1.244 MW | 69 | 0.9443 | 225.0 / 2.5 / 63.5 kW |
| 10 | 21 | 0.740 MW | 0.740 MW | 100.0% | 0.000 MW | 69 | 0.9158 | 225.0 / 177.5 / 195.4 kW |
| 28 | 7 | 0.066 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9092 | 225.0 / 224.9 / 224.9 kW |
| 36 | 10 | 0.160 MW | 0.160 MW | 100.0% | 0.000 MW | 69 | 0.9077 | 225.0 / 224.9 / 236.8 kW |
| 47 | 3 | 0.848 MW | 0.079 MW | 9.3% | 0.769 MW | 72 | 0.9057 | 225.0 / 222.5 / 239.4 kW |
| 50 | 2 | 0.044 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9096 | 225.0 / 222.7 / 222.7 kW |
| 60 | 5 | 1.562 MW | 0.318 MW | 20.4% | 1.244 MW | 73 | 0.9407 | 225.0 / 25.9 / 61.9 kW |
| 68 | 1 | 0.028 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9094 | 225.0 / 222.8 / 222.8 kW |

### Priority, multi-fault, and constraint checks (measured)

- **Priority, IEEE 69 line 6.** No priorities: tie 69, sheds bus 61
  (1.244 MW), restores 1.430 MW (53.5%). Bus 61 weight 10: tie 72,
  sheds buses 11, 12, 21, 64 (0.631 MW), restores **2.043 MW (76.4%)**,
  min voltage 0.9080 p.u. The critical load stays on and a different
  tie is chosen.
- **Priority shedding, synthetic feeder, single tie, v_min = 0.995.**
  No priorities: sheds buses 3, 4, restores 0.250 MW. Bus 3 weight 10:
  sheds buses 4, 5, 6, restores 0.200 MW (bus 3 on).
- **Loading limit, synthetic feeder.** Both ties rated 0.02 kA:
  sheds bus 3, restores 0.400 MW at 96.3% loading. At 0.01 kA:
  sheds buses 3, 4, 5, restores 0.100 MW at 48.1% loading.
- **Strict voltage band.** IEEE 33 demo fault with `--v-min 0.95`:
  0 MW restored, 0 steps, all 3 candidate ties skipped (post-isolation
  minimum voltage is already 0.9382 p.u.). This measurement is why the
  default band is 0.90–1.05 p.u.
- **Multi-fault.** IEEE 33 lines 6+18: 16 buses dead (outage 1.435 MW),
  restores 0.345 MW (24.0%), tie 36, sheds 0.730 MW; both faulted
  branches stay open. Synthetic feeder lines 2+9: restores 0.700 MW
  (100.0%) in two steps, ties 11 then 10.
- **Unrestorable cases (honest zeros).** IEEE 33 line 1 and IEEE 69
  line 1 (feeder-head faults: every tie has both ends in the outage
  area); IEEE 69 lines 28, 50, 68 (laterals with no tie). All return
  0 MW restored, 0 operations.
- **Enumeration optimality gap (synthetic feeder, 2 ties, 4
  combinations).** Greedy matches the exhaustive optimum exactly
  (gap 0.000 MW) for single faults on lines 2, 3, 5 and for the
  two-fault case (lines 2+9, 0.700 MW). Fault line 2: 3 of 4
  combinations feasible — closing both ties loops the outage area and
  is rejected by the radiality check.

### Tests

54 passed in ~49 s (`pytest -q`): networks (6), topology (5),
isolation (6), power flow (8), restoration (13), enumeration (5),
report (3), CLI (8). `ruff check` and `ruff format --check` pass;
`python -m compileall src` passes. Quickstart runs in ~8 s (mostly
pandapower import); one restoration run takes 0.1–0.8 s.

## Problems encountered and fixed

1. **First-feasible tie selection picked the wrong tie.** The first
   implementation tried candidates in rank order (restorable load,
   then line index) and accepted the first feasible one. On IEEE 33
   fault line 25 that restored 0.24 MW after shedding 0.68 MW, while
   another tie into the same outage area restored the full 0.92 MW
   with no shedding. Fixed by trial-closing *every* candidate and
   accepting the best feasible one (most priority-weighted load
   restored, then highest minimum voltage). The demo fault then also
   improved: tie 35 (min voltage 0.9263) instead of tie 33 (0.9212).
2. **The 0.95 p.u. voltage floor is unworkable on IEEE 33.** The
   healthy base case sits at 0.9131 p.u., so a 0.95 floor rejects
   every restoration step (measured: 0 MW restored). The brief's
   0.95–1.05 band was adapted to a 0.90–1.05 p.u. default — the
   emergency-restoration floor used in FLISR studies — with the band
   exposed as `--v-min` / `--v-max` so 0.95 can still be requested.
   Documented in the README and in `restore.py`.
3. **Line loading is vacuous on the IEEE cases as shipped.**
   `case33bw` sets `max_i_ka = 99999`, so measured loading is ~0.0%
   and the ≤100% check can never bind there. The check is exercised
   end-to-end on the synthetic feeder with realistic 0.5 kA ratings
   instead; the README states this plainly rather than implying the
   IEEE runs tested loading.
4. **A tie that restores nothing after shedding was accepted.** With a
   very strict band (v_min = 0.997) the planner closed a tie and shed
   every restored load, reporting a 0 MW "restoration". Fixed: a step
   that shed load and restored 0 MW is now skipped with the reason
   "all restorable load would have to be shed".
5. **Bus-fault isolation opens more lines than first assumed.** A
   fault at IEEE 33 bus 6 opens three incident lines (5, 6 and 25),
   not two — bus 6 also feeds bus 26. The test expectation was wrong,
   not the code; fixed the test.
6. **Ruff findings (10).** Four auto-fixed (docstring blank lines,
   unused import); six fixed by hand (long lines in `cli.py`,
   `network.py`, `report.py`, `test_isolate.py`; imperative-mood
   docstring in `topology.py`; two-line module summary in
   `__init__.py`).

## Design adaptations vs the brief

- **Best-feasible candidate per step** instead of first-feasible in
  rank order (see problem 1). Ranking is still by restorable load;
  the tie-break is now measured (restored load after shedding, then
  minimum voltage) instead of line index.
- **Voltage band 0.90–1.05 p.u. by default** instead of 0.95–1.05
  (see problem 2). The 0.95 band is available via `--v-min 0.95`.
- **Pure-Python topology helpers** instead of networkx: the closed-
  branch graph, energized sets and the no-loop check are small BFS /
  union-find routines, so the package needs no graph library.
- **Outage-relative metric added.** The report and JSON carry both
  `restored_pct` (of system load) and `restored_of_outage_pct` (of the
  load that actually lost supply); the latter is the FLISR headline
  number.

## Open issues / follow-ups (not blockers)

- Post-build fix by the parent agent (2026-11-19, before publishing):
  a step's `restored_buses` listed buses whose load was shed in the
  same step (e.g. case69 line 6 listed bus 61 as both restored and
  shed). Fixed in `restore.py` to exclude shed buses; re-verified
  with `pytest -q` (54 passed) and the quickstart — all measured
  numbers unchanged.

- CI (GitHub Actions) has not been run — no repository exists yet.
  The workflow installs `.[test]` plus ruff and runs pytest and the
  quickstart on Python 3.11/3.12.
- The greedy planner's gap to the global optimum on the IEEE cases
  was not measured (enumeration is infeasible at C(37,5) scale, as
  in dnrflow). The gap is exactly 0 on the synthetic feeder; on IEEE
  33/69 it is unknown and stated as such in the README.
- Phase 2 (per the research note): multi-fault as a validated method
  (currently a first implementation), DG participation in
  restoration, and fault location (currently an input).
