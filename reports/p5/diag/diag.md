# Failure diagnostics (d5_trace 64 K=3 layouts x 2; A4 arm 00 seeds 70-73)

| policy | P1 | q | finishable q | unresolved | impossible | r | r given feasible | ref 1 | ref 2 | pre-boundary share of failures |
|---|---|---|---|---|---|---|---|---|---|---|
| s70_probe | 0.148 | 0.227 | 0.188 | 0.000 | 0.039 | 0.655 | 0.792 | 0.680 | 0.188 | 0.908 |
| s70_final | 0.578 | 0.781 | 0.719 | 0.000 | 0.062 | 0.740 | 0.804 | 0.766 | 0.719 | 0.519 |
| s71_probe | 0.164 | 0.344 | 0.289 | 0.000 | 0.055 | 0.477 | 0.568 | 0.602 | 0.289 | 0.785 |
| s71_final | 0.461 | 0.680 | 0.648 | 0.000 | 0.031 | 0.678 | 0.711 | 0.789 | 0.648 | 0.594 |
| s72_probe | 0.039 | 0.070 | 0.062 | 0.000 | 0.008 | 0.556 | 0.625 | 0.633 | 0.062 | 0.967 |
| s72_final | 0.273 | 0.484 | 0.438 | 0.000 | 0.047 | 0.565 | 0.625 | 0.742 | 0.438 | 0.710 |
| s73_probe | 0.117 | 0.195 | 0.148 | 0.000 | 0.047 | 0.600 | 0.789 | 0.570 | 0.148 | 0.912 |
| s73_final | 0.477 | 0.742 | 0.680 | 0.000 | 0.062 | 0.642 | 0.701 | 0.734 | 0.680 | 0.493 |

Taxonomy (shares of attempts):

| policy | arrived_failed_feasible | arrived_failed_impossible | arrived_failed_unresolved | before_boundary_m0 | before_boundary_m1 | before_boundary_m2 | before_boundary_m3 | success |
|---|---|---|---|---|---|---|---|---|
| s70_probe | 0.039 | 0.039 | 0.000 | 0.195 | 0.414 | 0.164 | 0.000 | 0.148 |
| s70_final | 0.141 | 0.062 | 0.000 | 0.016 | 0.109 | 0.094 | 0.000 | 0.578 |
| s71_probe | 0.125 | 0.055 | 0.000 | 0.078 | 0.445 | 0.133 | 0.000 | 0.164 |
| s71_final | 0.188 | 0.031 | 0.000 | 0.000 | 0.234 | 0.086 | 0.000 | 0.461 |
| s72_probe | 0.023 | 0.008 | 0.000 | 0.273 | 0.500 | 0.141 | 0.016 | 0.039 |
| s72_final | 0.164 | 0.047 | 0.000 | 0.008 | 0.406 | 0.102 | 0.000 | 0.273 |
| s73_probe | 0.031 | 0.047 | 0.000 | 0.227 | 0.422 | 0.148 | 0.008 | 0.117 |
| s73_final | 0.203 | 0.062 | 0.000 | 0.016 | 0.148 | 0.094 | 0.000 | 0.477 |

Progress (reach module / open door; median steps in module):

- s70_probe: reach [1.0, 0.789, 0.391], open [0.805, 0.391, 0.227], steps [24.0, 17.5, 16.0]; arrival tau median 78.0, remaining median 64.0; errors(fail) {'n': 109, 'wrong_key_pickups_per_attempt': 0.6880733944954128, 'share_with_wrong_key': 0.23853211009174313, 'locked_toggles_per_attempt': 19.798165137614678, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 64.37614678899082, 'pose_repeat_frac': 0.7371020114003015, 'max_cell_visits_median': 57.0}
- s70_final: reach [1.0, 0.984, 0.859], open [0.984, 0.875, 0.781], steps [18.5, 20.0, 14.0]; arrival tau median 67.5, remaining median 77.0; errors(fail) {'n': 54, 'wrong_key_pickups_per_attempt': 1.4074074074074074, 'share_with_wrong_key': 0.2962962962962963, 'locked_toggles_per_attempt': 17.09259259259259, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 45.574074074074076, 'pose_repeat_frac': 0.6073903992997236, 'max_cell_visits_median': 45.5}
- s71_probe: reach [1.0, 0.914, 0.477], open [0.922, 0.477, 0.344], steps [19.5, 23.0, 16.0]; arrival tau median 71.0, remaining median 73.0; errors(fail) {'n': 107, 'wrong_key_pickups_per_attempt': 1.439252336448598, 'share_with_wrong_key': 0.3177570093457944, 'locked_toggles_per_attempt': 23.55140186915888, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 42.691588785046726, 'pose_repeat_frac': 0.6784281916213971, 'max_cell_visits_median': 60.0}
- s71_final: reach [1.0, 1.0, 0.758], open [1.0, 0.766, 0.68], steps [17.0, 18.0, 13.0]; arrival tau median 58.0, remaining median 86.0; errors(fail) {'n': 69, 'wrong_key_pickups_per_attempt': 0.5072463768115942, 'share_with_wrong_key': 0.2608695652173913, 'locked_toggles_per_attempt': 23.202898550724637, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 60.507246376811594, 'pose_repeat_frac': 0.6651973524329939, 'max_cell_visits_median': 71.0}
- s72_probe: reach [1.0, 0.703, 0.211], open [0.727, 0.227, 0.086], steps [33.0, 24.0, 15.0]; arrival tau median 102.0, remaining median 46.0; errors(fail) {'n': 123, 'wrong_key_pickups_per_attempt': 0.8699186991869918, 'share_with_wrong_key': 0.1951219512195122, 'locked_toggles_per_attempt': 18.634146341463413, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 50.6910569105691, 'pose_repeat_frac': 0.7676971756692077, 'max_cell_visits_median': 61.0}
- s72_final: reach [1.0, 0.992, 0.578], open [0.992, 0.586, 0.484], steps [24.0, 26.0, 15.0]; arrival tau median 83.0, remaining median 63.0; errors(fail) {'n': 93, 'wrong_key_pickups_per_attempt': 0.5483870967741935, 'share_with_wrong_key': 0.26881720430107525, 'locked_toggles_per_attempt': 8.924731182795698, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 46.505376344086024, 'pose_repeat_frac': 0.6505112064334688, 'max_cell_visits_median': 46.0}
- s73_probe: reach [1.0, 0.766, 0.336], open [0.773, 0.352, 0.203], steps [26.0, 27.0, 16.0]; arrival tau median 80.0, remaining median 62.0; errors(fail) {'n': 113, 'wrong_key_pickups_per_attempt': 0.584070796460177, 'share_with_wrong_key': 0.18584070796460178, 'locked_toggles_per_attempt': 38.63716814159292, 'door_closes_per_attempt': 0.0, 'noop_actions_per_attempt': 60.69911504424779, 'pose_repeat_frac': 0.7570742763341207, 'max_cell_visits_median': 67.0}
- s73_final: reach [1.0, 0.984, 0.82], open [0.984, 0.836, 0.742], steps [20.0, 24.0, 14.0]; arrival tau median 76.0, remaining median 71.0; errors(fail) {'n': 67, 'wrong_key_pickups_per_attempt': 2.343283582089552, 'share_with_wrong_key': 0.417910447761194, 'locked_toggles_per_attempt': 11.313432835820896, 'door_closes_per_attempt': 0.014925373134328358, 'noop_actions_per_attempt': 37.61194029850746, 'pose_repeat_frac': 0.6210762300549544, 'max_cell_visits_median': 44.0}

Opportunity rule: mean(1 - q) = 0.328 (>= 0.25), mean(ref1 - P1) = +0.311 (>= 0.05): **met**.
Correctness checks: {'arrival_with_locked_door': 0, 'impossible_but_plan_fits': 0, 'feasible_replay_failed': 0, 'missing_trace': 0}
Actions: {'planner_prefix': 2588, 'normal': 134271, 'certification': 10019, 'ref1': 52946}
