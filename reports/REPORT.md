# MiniGrid study: demonstration-state starts and BC preservation after BC

Status 2026-10-30: M0-M3 complete on development data. Protocol frozen
(`research/PROTOCOL_FREEZE.md`). M4 confirmation not started. **No confirmatory result exists yet.**
All numbers below come from development layouts and serve design decisions only.

## Question
RQ1: when do demonstration-state starts (arm 10), forward-KL preservation toward the BC policy (arm 01),
or both (arm 11) improve PPO after BC, compared with ordinary PPO (arm 00)? Task: MiniGrid prerequisite
rooms (K = 1 or 3) before a common suffix; access q, competence c on a fixed suffix bank, success P1.

## Development results (exploratory)
| Step | Result | Source |
|---|---|---|
| BC curves | K=3 reduces access (q 0.45 vs 0.98) at equal suffix competence (~0.66); early 4k / extended 16k | F1 |
| PPO stability | Default PPO destroyed the BC policy; lr 3e-5, entropy 0, pre-fit critic chosen | F2, F3, `m2_ppo_screen.csv` |
| Rollout size | 16 envs x 128 needed for ordinary PPO to learn | F5, `m2b_rollout_*.csv` |
| M3 screen | 8 forks: arm 00 P1 0.26 -> 0.37; alpha* 0.25, lambda* 0.01 by prespecified rule | F6, `m3_screen_branches.csv`, `m3_probes.csv` |
| M3 four-arm | All contrasts within 0.02 of 0 on average (fork SD 0.04-0.06); run-to-run SD 0.027 | F7, `m3_contrasts.csv`, `m3_branches.csv` |

Interpretation limit: 8 development forks from 2 seeds. They neither show nor exclude effects of 0.05.

## Frozen confirmation design (M4)
20 forks (5 new seeds x K x BC checkpoint), 4 arms, 250k continuation actions, conf_final 32 x 16.
Smallest effect of interest 0.05 P1; verdicts per PROTOCOL_FREEZE section 8.

## Resources
28.69M of 80M environment actions (35.9%); 3.25 h of batch wall time. Ledger: `tools/ledger.py`.

## Known limitations
- PPO is step-size-limited (lr 3e-5); results may not transfer to more aggressive settings.
- MPS training is not bitwise reproducible; inference relies on paired forks and seed replication.
- The 250k endpoint is set by budget; arm 00 is still improving there.
