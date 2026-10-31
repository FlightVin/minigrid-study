# State

**Current milestone:** Post-M4 audit and interpretation revision complete (F11; REPORT C1-C9). Waiting for owner
approval of follow-up R1 (no training before approval).

**Established**
- Manuscript SHA-256 `38326ef0...f92b4`; no substantive conflict with project.md.
- Host: Apple M5, 10 cores, 24 GiB. Backend: MPS (1,404 actions/s vs 331 on 4 CPU threads).
- M0: canaries 7/7. Tests now: 258 pass, 3 skipped (smoke opt-in), including accounting and M4-analysis tests.
- M1: dataset dev-v2; BC rule early = 4k, extended = 16k updates (FINDINGS F1). K=3 access << K=1 at
  equal suffix competence.
- M2: default PPO (lr 3e-4, ent 0.01) collapses the BC policy (F2). Screen selected actor lr 3e-5,
  entropy 0, early-stopped critic pre-fit (F3). It holds but does not yet improve p in 50k actions.

- M2b/M3: with R2, ordinary PPO improves in 8/8 forks (corrected from 7/8 in F8 C1; mean P1 0.26 -> 0.37; F5, F6).
  No screened intervention separates from arm 00 on development data.
- M3 four-arm (F7): all six contrasts average within 0.02 of 0; arm 00 replicate SD 0.027.
- Final protocol: freeze + Amendments 1-2: alpha* 0.25, lambda* 0.01, endpoints 251,904 and 501,760, seeds 10-14,
  conf_final 64 x 8, conf_bank 64 x 4, diagnostics on conf_select, Holm over 6, TOST ±0.05.
- Audit (F8): no correctness defect; metrics recompute exactly; corrections C1-C5 recorded.
- M4 (F10): all 6 primary tests practically equivalent (equal-weight aggregate only); audit exact; 20/20 forks.
- Post-M4 (F11): condition-level effects exist: preservation K=3/early BC +0.045 at E500 (post hoc; Holm-24 0.0056;
  sign-flip 0.0625); K=1/early BC -0.048 at E250 (closes by E500). Bank gap mostly progress composition.
  Selection headroom ~0.01 hindsight, ~0 out of sample.
- Campaign (F9): learning continues to 500k (+0.065 mean); no contrast separates; same-fork path SD 0.048;
  the M3 K=3 combined benefit did not reproduce. (Its "arrival competence < planner-bank c" is superseded by F11:
  mostly progress composition.)

**Uncertain**
- Whether the K=3/early-BC preservation benefit replicates (post hoc; 5 seeds) -> proposal R1.
- K=3 arrival-vs-entry competence difference (~0.056): time vs layout not separated.
- Whether PPO step size is the bottleneck (hypothesis only).

**Owner limits:** 4 cores, 6 GiB, 1 job. No numeric hard action cap after 2026-10-31 (owner); 109M was the M4
submission stop line. Battery watch: stop execution below 20% (5-minute checks). Two-hourly self-reviews.

**Resources used:** 93.14M actions = 89.57M runner-measured (incl. 1.31M derived planner replay) + 0.12M measured
outside the runner + 3.45M estimated outside the runner (conservative). Batch wall 9.12 h.

**Blockers:** none.

**Next action**
- Owner decision on R1 (REPORT C9). If approved: freeze R1 protocol, generate rep roles, gate, run.
