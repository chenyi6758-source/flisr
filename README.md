# flisr

[![tests: 54 passed](https://img.shields.io/badge/tests-54%20passed-brightgreen.svg)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

**English** | [简体中文](#flisr-中文)

**A feeder fault blacks out everything downstream. `flisr` isolates the faulted section, then closes tie switches one at a time — each step checked by an exact power flow — to bring back as much load as possible, critical loads first.**

## Results at a glance

Demo fault (IEEE 33-bus, line 6 between buses 6 and 7, 12 buses blacked out):

```console
$ flisr demo
case33: Baran & Wu (1989), via pandapower.networks.case33bw
case33 restoration: 1.075 / 3.715 MW restored (28.9% of system, 100.0% of outage load 1.075 MW)
fault: line 6 (6-7)
isolated: switches opened 6; de-energized buses [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
loss:           202.68 kW (healthy) ->     93.09 kW (isolated) ->    168.20 kW (restored)
min voltage: 0.9131 p.u. (healthy) -> 0.9382 p.u. (isolated) -> 0.9263 p.u. (restored)
max voltage: 1.0000 p.u.; max loading: 0.0% (limits 0.90-1.05 p.u., <=100%)
operations: 1 tie closure(s); load shed: 0.000 MW at buses []; unrestored: 0.000 MW at buses []
switching sequence:
  1. close tie 35 line 35 (12-22): restores buses [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18] (1.075 MW); min voltage 0.9263 p.u., max loading 0.0%, loss 168.20 kW [ok]
elapsed: 0.3 s
```

Single-fault sweep (every number measured; "% of outage" is the FLISR headline metric — restored load divided by the load that actually lost supply):

IEEE 33-bus (total load 3.715 MW):

| fault line | dead buses | outage load | restored | % of outage | shed | tie closed | min voltage |
|---|---|---|---|---|---|---|---|
| 1 | 32 | 3.715 MW | 0.000 MW | 0.0% | 0.000 MW | — | 1.0000 |
| 2 | 27 | 3.255 MW | 1.455 MW | 44.7% | 1.800 MW | 33 | 0.9053 |
| 3 | 23 | 2.235 MW | 1.425 MW | 63.8% | 0.810 MW | 33 | 0.9059 |
| 6 | 12 | 1.075 MW | 1.075 MW | 100.0% | 0.000 MW | 35 | 0.9263 |
| 10 | 8 | 0.555 MW | 0.555 MW | 100.0% | 0.000 MW | 35 | 0.9277 |
| 12 | 6 | 0.450 MW | 0.450 MW | 100.0% | 0.000 MW | 34 | 0.9167 |
| 18 | 4 | 0.360 MW | 0.360 MW | 100.0% | 0.000 MW | 33 | 0.9027 |
| 22 | 3 | 0.930 MW | 0.090 MW | 9.7% | 0.840 MW | 37 | 0.9159 |
| 25 | 8 | 0.920 MW | 0.920 MW | 100.0% | 0.000 MW | 37 | 0.9294 |
| 30 | 3 | 0.420 MW | 0.060 MW | 14.3% | 0.360 MW | 36 | 0.9143 |

IEEE 69-bus (total load 3.802 MW):

| fault line | dead buses | outage load | restored | % of outage | shed | tie closed | min voltage |
|---|---|---|---|---|---|---|---|
| 1 | 68 | 3.802 MW | 0.000 MW | 0.0% | 0.000 MW | — | 1.0000 |
| 5 | 41 | 2.677 MW | 1.433 MW | 53.5% | 1.244 MW | 69 | 0.9442 |
| 6 | 40 | 2.674 MW | 1.430 MW | 53.5% | 1.244 MW | 69 | 0.9443 |
| 10 | 21 | 0.740 MW | 0.740 MW | 100.0% | 0.000 MW | 69 | 0.9158 |
| 28 | 7 | 0.066 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9092 |
| 36 | 10 | 0.160 MW | 0.160 MW | 100.0% | 0.000 MW | 69 | 0.9077 |
| 47 | 3 | 0.848 MW | 0.079 MW | 9.3% | 0.769 MW | 72 | 0.9057 |
| 50 | 2 | 0.044 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9096 |
| 60 | 5 | 1.562 MW | 0.318 MW | 20.4% | 1.244 MW | 73 | 0.9407 |
| 68 | 1 | 0.028 MW | 0.000 MW | 0.0% | 0.000 MW | — | 0.9094 |

Three findings worth a dispatcher's attention:

1. **The tie you pick matters more than the load you restore.** On IEEE 33, fault line 25: tie 36 restores 0.24 MW after shedding 0.68 MW, tie 37 restores the full 0.92 MW with no shedding at all. The planner trial-closes every candidate and picks the best feasible one — ranking by restorable load alone would have picked the wrong tie.
2. **Load priority changes both the tie and the outcome.** On IEEE 69, fault line 6 with no priorities sheds the 1.244 MW load at bus 61 and restores 1.430 MW (53.5%). Mark bus 61 critical (`--priority 61:10`) and the planner switches to tie 72, sheds four small loads instead (0.631 MW), and restores 2.043 MW (76.4%).
3. **Some outages cannot be restored from inside the feeder, and the tool says so.** A fault at the feeder head (line 1) leaves every tie with both ends in the blackout area; a fault on the 28–35 lateral of IEEE 69 has no tie at all. Both return 0 MW restored with no switching operations, instead of a spurious plan.

## How it works

**Isolate** (`isolate.py`). Open the faulted branch (every line is a sectionalizing switch) or, for a bus fault, every closed line incident to the bus. The de-energized set is every bus that loses its closed-branch path to a slack bus. The faulted branch is recorded as forbidden and is never closed again — the safety invariant is checked in tests.

**Restore** (`restore.py`). The dead buses form one or more components connected through their still-closed internal branches. A candidate tie switch is an open, non-faulted line with exactly one end energized: closing it re-energizes a whole dead component without creating a loop. Every candidate is trial-closed and evaluated with an exact pandapower power flow (`bfsw`, falling back to Newton-Raphson); the best feasible candidate — most priority-weighted load restored, then highest minimum voltage — is accepted, and the search repeats on the new state. If a step violates the voltage band (default 0.90–1.05 p.u.) or the line-loading limit (≤100%), the lowest-priority restored loads are shed one at a time and the step is re-checked; if it still violates with every restorable load shed, the tie is skipped. A step that would restore nothing after shedding is skipped rather than accepted. Radiality (no loops) is verified after every accepted step. De-energized buses are excluded from the power flow via `bus.in_service = False`, so the energized part still solves.

**Report** (`report.py`). Restored load in MW, as a percentage of system load and of outage load, unrestored and shed loads with bus lists, the step-by-step switching sequence with per-step voltage/loading/loss, and before/after (healthy → isolated → restored) voltage and loss. Exportable to JSON.

## Usage

```console
$ flisr demo                                          # IEEE 33, mid-feeder fault
$ flisr restore --case 33 --fault-line 6
$ flisr restore --case 69 --fault-line 6 --priority 61:10
$ flisr restore --case 33 --fault-line 6 --fault-line 18   # two faults
$ flisr restore --case 33 --fault-line 6 --v-min 0.95       # stricter band
$ flisr restore --case 69 --fault-line 6 --json out.json
$ python examples/quickstart.py                       # both IEEE cases
```

Python API:

```python
from flisr import load_case, plan_restoration
from flisr.isolate import Fault
from flisr.report import format_report

net = load_case("case33")
result = plan_restoration(net, [Fault(line=5)], priorities={17: 10.0})
print(format_report(net, result))
print(result.restored_of_outage_pct)  # 100.0 for the demo fault
```

## Validation

| case | base loss: literature | base loss: measured | base min voltage |
|---|---|---|---|
| case33 | 202.69 kW | 202.68 kW | 0.9131 p.u. |
| case69 | 224.99 kW | 224.99 kW | 0.9092 p.u. |

Optimality check on the synthetic 10-bus teaching feeder (two ties, every tie combination enumerated): the greedy planner matches the exhaustive optimum exactly (gap 0.000 MW) for single faults on lines 2, 3 and 5, and for the two-fault case (lines 2 and 9, restored 0.700 MW in two steps). The enumeration also confirms the loop rule: closing both ties at once is infeasible (3 of 4 combinations feasible for fault line 2).

## Honesty notes

- **The voltage band is 0.90–1.05 p.u. by default, not 0.95–1.05.** The healthy IEEE 33-bus case already sits at 0.9131 p.u., so a 0.95 floor rejects every restoration step — verified: with `--v-min 0.95` the demo fault restores 0 MW and all three candidate ties are skipped. 0.90 p.u. is the emergency-restoration floor used in FLISR studies; the band is a parameter (`--v-min` / `--v-max`).
- **The line-loading limit is vacuous on the IEEE cases as shipped.** `pandapower.networks.case33bw` sets `max_i_ka = 99999`, so measured loading is ~0.0% there. The loading check is real — it is exercised end-to-end on the synthetic feeder with realistic 0.5 kA ratings (both ties at 0.02 kA force shedding of the largest load; restored 0.400 MW at 96.3% loading) — but on IEEE 33/69 it never binds.
- **Restoration can raise losses.** Restored load is fed through long, thin tie paths (2.0 Ω ties on IEEE 33): fault line 18 goes from 199.4 kW isolated to 250.0 kW restored. The planner optimises restored load, not losses.
- **The greedy planner is not globally optimal.** It is exact on the small feeder (verified against enumeration) but on the IEEE cases the gap to the global optimum was not measured — the planner picks the best single tie per step with no lookahead. Multi-fault restoration works (IEEE 33 lines 6+18: 0.345 MW, 24.0% of outage) but is a first implementation, not a validated multi-fault method.
- **Scope (v1).** Single fault is the primary case; fault location is an input, not solved here; no distributed generation participates in restoration; loads are constant-power.

## References

- Baran & Wu, "Network reconfiguration in distribution systems for loss reduction and load balancing", *IEEE Trans. Power Delivery*, 1989 — the 33- and 69-bus systems.
- Civanlar, Grainger, Yin & Lee, "Distribution feeder reconfiguration for loss reduction", *IEEE Trans. Power Delivery*, 1988 — branch exchange, the switch-operation basis.
- Karlsson et al., "Ultra-fast FLISR in practice", CIRED 2025 — distributed FLISR in commercial deployment.
- Smith et al., SEL / Huntsville Utilities, 78th Georgia Tech Protective Relaying Conference, May 2025 — staged FLISR deployment on a 46 kV system.
- Hua et al., "Hydrogen storage in distribution self-healing restoration", *Renewable Energy*, vol. 254, 2025 — two-stage restoration planning.
- "Multi-objective restoration based on membrane computing", *Energies*, 19(18):4439, Sep 2026 — IEEE 33-bus validation, load priority as the core objective.
- FLARE, arXiv:2610.23251, NeurIPS 2026 submission — FLISR as an evaluation benchmark for LLM agents (a benchmark, not a tool; the tool layer is what this project fills).

---

# flisr （中文）

**English** | **简体中文**

**馈线故障会让下游大片失电。`flisr` 先隔离故障区段，再逐个合上联络开关恢复供电——每一步都用精确潮流校验，重要负荷优先恢复。**

## 一眼结果

演示故障（IEEE 33 节点，6 号线路、6–7 母线之间故障，12 个母线失电）：恢复 1.075 MW，失电负荷恢复率 100.0%，操作 1 次（合联络开关 35），无切负荷，最低电压 0.9263 p.u.，网损由隔离后的 93.09 kW 变为恢复后的 168.20 kW。完整输出见上文英文部分（`flisr demo` 的真实输出）。

单故障扫描（全部实测；"失电恢复率" = 恢复负荷 / 失电负荷，是 FLISR 的核心指标）：

IEEE 33 节点（总负荷 3.715 MW）：6 号线故障恢复率 100.0%；2 号线 44.7%（切 1.800 MW）；3 号线 63.8%；25 号线 100.0%（选对联络开关是关键：36 号开关恢复 0.24 MW 且要切负荷，37 号开关恢复全部 0.92 MW、无需切负荷）；22 号线仅 9.7%；1 号线（馈线首端故障）0%——所有联络开关两端都在停电区内，单电源馈线内部无法恢复。

IEEE 69 节点（总负荷 3.802 MW）：6 号线故障恢复率 53.5%（切掉 61 号母线 1.244 MW 大负荷）；把 61 号母线标为重要负荷（`--priority 61:10`）后改合 72 号开关，恢复率升至 76.4%（2.043 MW），只切 4 个小负荷；28 号线故障（28–35 分支无联络开关）恢复率 0%。

三点值得注意：

1. **选哪个联络开关比恢复多少负荷更重要。**33 节点 25 号线故障：先按"可恢复负荷"排序会挑错开关——必须逐个试合、用潮流结果选最好的。
2. **负荷优先级同时改变开关选择和恢复结果。**69 节点 6 号线故障：无优先级时切 61 号母线大负荷、恢复 1.430 MW；61 号母线加权 10 后改合另一开关、恢复 2.043 MW。
3. **有些停电本来就恢复不了，工具会如实报 0。**馈线首端故障、无联络开关的分支故障，返回 0 MW、0 次操作，而不是编一个方案。

## 做法

**隔离**（`isolate.py`）：断开故障支路（每条线路就是一个分段开关），母线故障则断开其全部相连线路；失电集合 = 失去与平衡节点闭合路径的全部母线。故障支路记入禁合集合，恢复过程永不重合——测试覆盖此安全铁律。

**恢复**（`restore.py`）：失电母线按内部闭合支路形成若干区域；候选联络开关是"一端带电、一端失电"的常开开关，合上它可整片恢复一个失电区域且不成环。每个候选都试合、跑精确潮流（`bfsw`，失败退回牛顿法），选最优可行者（优先恢复加权负荷最多，其次最低电压最高），再在新状态下重复。某步越限（电压默认 0.90–1.05 p.u.、线路载流 ≤100%）时，按优先级从低到高逐个切除已恢复负荷并重算；全部切完仍越限则跳过该开关；切完恢复为 0 的开关直接跳过、不做无用操作。每步接受后校验不成环。失电母线用 `bus.in_service = False` 排除在潮流之外，带电部分仍可求解。

**报告**（`report.py`）：恢复 MW、占系统负荷与失电负荷的百分比、未恢复与切除负荷及母线清单、逐步开关操作序列（含每步电压/载流/网损）、健康→隔离→恢复三态电压与网损对照，可导出 JSON。

## 用法

```console
$ flisr demo                                          # IEEE 33 节点演示故障
$ flisr restore --case 33 --fault-line 6
$ flisr restore --case 69 --fault-line 6 --priority 61:10
$ flisr restore --case 33 --fault-line 6 --fault-line 18   # 双重故障
$ flisr restore --case 33 --fault-line 6 --v-min 0.95       # 更严的电压下限
$ flisr restore --case 69 --fault-line 6 --json out.json
$ python examples/quickstart.py                       # 两个 IEEE 算例
```

Python 调用：

```python
from flisr import load_case, plan_restoration
from flisr.isolate import Fault
from flisr.report import format_report

net = load_case("case33")
result = plan_restoration(net, [Fault(line=5)], priorities={17: 10.0})
print(format_report(net, result))
print(result.restored_of_outage_pct)  # 演示故障为 100.0
```

## 验证

| 算例 | 基态网损：文献 | 基态网损：实测 | 基态最低电压 |
|---|---|---|---|
| case33 | 202.69 kW | 202.68 kW | 0.9131 p.u. |
| case69 | 224.99 kW | 224.99 kW | 0.9092 p.u. |

小网络最优性对照（10 节点教学馈线，2 个联络开关，全部组合全枚举）：贪心规划与全枚举最优解完全一致（差距 0.000 MW），单故障（2、3、5 号线）与双重故障（2、9 号线，两步恢复 0.700 MW）均如此；全枚举同时确认成环规则——两个联络开关同时合上不可行（2 号线故障：4 种组合中 3 种可行）。

## 诚实说明

- **电压带默认 0.90–1.05 p.u.，不是 0.95–1.05。**IEEE 33 节点健康状态最低电压已是 0.9131 p.u.，0.95 的下限会否决一切恢复操作——已验证：`--v-min 0.95` 时演示故障恢复 0 MW，3 个候选开关全部跳过。0.90 p.u. 是 FLISR 研究中常用的紧急恢复下限；电压带是参数（`--v-min` / `--v-max`）。
- **线路载流限值在 IEEE 算例上不起作用。**`pandapower.networks.case33bw` 的 `max_i_ka = 99999`，实测载流约 0.0%。载流校验本身是真实的——在 0.5 kA 真实额定值的教学馈线上已端到端验证（两联络开关限为 0.02 kA 时被迫先切最大负荷，恢复 0.400 MW、载流 96.3%）——但在 IEEE 33/69 上它永不触发。
- **恢复可能让网损上升。**恢复负荷经长而细的联络路径供电（IEEE 33 的联络线 2.0 Ω）：18 号线故障隔离后 199.4 kW、恢复后 250.0 kW。规划目标是恢复负荷最大，不是网损最小。
- **贪心法不保证全局最优。**小馈线上与全枚举一致，但 IEEE 算例上与全局最优的差距未实测——规划每步只选当前最优的单个开关，无前瞻。多重故障可用（33 节点 6+18 号线：恢复 0.345 MW、失电恢复率 24.0%），但只是第一版实现，未按多重故障方法验证。
- **适用范围（v1）。**单故障为主；故障定位是输入、不由本工具求解；恢复不含分布式电源；负荷为恒功率模型。

## 参考文献

- Baran & Wu, "Network reconfiguration in distribution systems for loss reduction and load balancing", *IEEE Trans. Power Delivery*, 1989——33/69 节点系统。
- Civanlar, Grainger, Yin & Lee, "Distribution feeder reconfiguration for loss reduction", *IEEE Trans. Power Delivery*, 1988——支路交换法，开关操作底座。
- Karlsson et al., "Ultra-fast FLISR in practice", CIRED 2025——分布式 FLISR 商业部署实测。
- Smith et al., SEL / Huntsville Utilities, 78th Georgia Tech Protective Relaying Conference, May 2025——46 kV 系统分阶段 FLISR 部署案例。
- Hua et al., "Hydrogen storage in distribution self-healing restoration", *Renewable Energy*, vol. 254, 2025——双阶段恢复计划。
- "Multi-objective restoration based on membrane computing", *Energies*, 19(18):4439, Sep 2026——IEEE 33 节点验证，负荷优先级是核心目标。
- FLARE, arXiv:2610.23251, NeurIPS 2026 投稿——把 FLISR 作为 LLM 智能体能力的评估基准（是基准、不是工具；本项目填的是工具层空白）。
