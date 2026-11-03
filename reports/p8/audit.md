# Actor capability audit — results (Amendment 10)

## Validation

| Group | Rows | Unique obs | Unique labelled configs | Rebuilt mismatches | Obs conflicts | Config conflicts across time | Door reads not visible |
|---|---|---|---|---|---|---|---|
| train | 150050 | 150050 | 78621 | 0 | 0 | 0 | 0 |
| val | 35053 | 35053 | 18386 | 0 | 0 | 0 | 0 |
| test | 20855 | 20253 | 8088 | 0 | 0 | 0 | 0 |

check_label (real environment):

- all: 6/1000 with violations
- stratum:all_unlocked: 0/200 with violations
- stratum:backtracked: 0/200 with violations
- stratum:key_lost: 1/200 with violations
- stratum:on_track: 0/200 with violations
- stratum:wrong_key: 5/200 with violations
- type:drop: 0/120 with violations
- type:forward: 2/572 with violations
- type:pickup: 0/57 with violations
- type:toggle: 0/9 with violations
- type:turn: 4/433 with violations

Expert prefix controller (validation panel): crossed 32/32, mean time to boundary 41.2; non-crossing stops: []

## Dataset

```
{
 "train": {
  "rows": 150050,
  "labelled_rows": 143815,
  "unique_labelled": 78621,
  "layouts": 1415,
  "layouts_with_labelled": 1415,
  "status_rows": {
   "labelled": 143815,
   "time_exceeded": 4308,
   "unresolved": 1927,
   "at_goal": 0
  },
  "unlabelled_certified_impossible_module": 876,
  "unlabelled_certified_impossible_boundary": 2855,
  "unlabelled_not_certified": 5359,
  "stratum_unique": {
   "on_track": 63679,
   "wrong_key": 8360,
   "key_lost": 1539,
   "backtracked": 4069,
   "all_unlocked": 974
  },
  "stratum_unique_share": {
   "on_track": 0.8099489958153674,
   "wrong_key": 0.10633291359814807,
   "key_lost": 0.01957492273056817,
   "backtracked": 0.05175462026684982,
   "all_unlocked": 0.012388547589066535
  },
  "label_size": {
   "1": 54618,
   "2": 21456,
   "3": 1964,
   "4": 583
  },
  "mean_multiplicity": 1.8292186565930222
 },
 "val": {
  "rows": 35053,
  "labelled_rows": 33669,
  "unique_labelled": 18386,
  "layouts": 331,
  "layouts_with_labelled": 331,
  "status_rows": {
   "labelled": 33669,
   "time_exceeded": 852,
   "unresolved": 532,
   "at_goal": 0
  },
  "unlabelled_certified_impossible_module": 217,
  "unlabelled_certified_impossible_boundary": 612,
  "unlabelled_not_certified": 1167,
  "stratum_unique": {
   "on_track": 15016,
   "wrong_key": 1782,
   "key_lost": 376,
   "backtracked": 978,
   "all_unlocked": 234
  },
  "stratum_unique_share": {
   "on_track": 0.816708365060372,
   "wrong_key": 0.09692157076036115,
   "key_lost": 0.02045034265201784,
   "backtracked": 0.05319264657891874,
   "all_unlocked": 0.01272707494833025
  },
  "label_size": {
   "1": 12800,
   "2": 5030,
   "3": 431,
   "4": 125
  },
  "mean_multiplicity": 1.8312302839116719
 },
 "test": {
  "rows": 20855,
  "labelled_rows": 19673,
  "unique_labelled": 8088,
  "layouts": 64,
  "layouts_with_labelled": 64,
  "status_rows": {
   "labelled": 19673,
   "time_exceeded": 677,
   "unresolved": 505,
   "at_goal": 0
  },
  "unlabelled_certified_impossible_module": 120,
  "unlabelled_certified_impossible_boundary": 421,
  "unlabelled_not_certified": 1062,
  "stratum_unique": {
   "on_track": 6598,
   "wrong_key": 760,
   "key_lost": 224,
   "backtracked": 405,
   "all_unlocked": 101
  },
  "stratum_unique_share": {
   "on_track": 0.8157764589515332,
   "wrong_key": 0.09396636993076163,
   "key_lost": 0.027695351137487636,
   "backtracked": 0.05007418397626113,
   "all_unlocked": 0.012487636003956479
  },
  "label_size": {
   "1": 5425,
   "2": 2417,
   "3": 200,
   "4": 46
  },
  "mean_multiplicity": 2.4323689416419385
 }
}
```

Subsets: {'0': {'target': 19655, 'states': 19726, 'layouts': 358}, '1': {'target': 39000, 'states': 39068, 'layouts': 712}, '2': {'target': 78621, 'states': 78621, 'layouts': 1415}}
Tiny: {'states': 512, 'audited_pool': 994, 'stratum': {'on_track': 94, 'wrong_key': 99, 'key_lost': 104, 'backtracked': 102, 'all_unlocked': 113}}
Cross-group shared configurations: {'train-val': 0, 'train-test': 0, 'val-test': 0}
Layout provenance: {'train': {'overlap_with_roles': {'rl_train': 1415}}, 'val': {'overlap_with_roles': {'rl_train': 331}}, 'test': {'overlap_with_roles': {'r7_conf': 64}}}

## Tiny-set check

| lr | argmax-in-set | mass | set loss | grad norm | checks | passes |
|---|---|---|---|---|---|---|
| 3e-4 | 1.0000 | 0.9999 | 0.0001 | 0.00195 | {'loss_reduction_mean': True, 'preprocessing_same_logits': True, 'labels_nonempty_no_done': True} | True |
| 1e-3 | 1.0000 | 1.0000 | 0.0000 | 0.000134 | {'loss_reduction_mean': True, 'preprocessing_same_logits': True, 'labels_nonempty_no_done': True} | True |

## Fits (selected checkpoint by validation; final test not read)

| Condition | n train | train probe (selected) | validation (selected) | train probe (final) | validation (final) | val mass | val set loss | probe set loss |
|---|---|---|---|---|---|---|---|---|
| warm128-n0 | 19726 | 1.000 [1.0, 1.0, 1.0] | 0.915 [0.913, 0.916, 0.915] | 1.000 | 0.914 | 0.910 | 0.476 | 0.001 |
| warm128-n1 | 39068 | 1.000 [1.0, 1.0, 1.0] | 0.961 [0.958, 0.964, 0.96] | 1.000 | 0.960 | 0.957 | 0.217 | 0.001 |
| warm128-n2 | 78621 | 1.000 [1.0, 1.0, 1.0] | 0.983 [0.982, 0.985, 0.982] | 1.000 | 0.982 | 0.981 | 0.099 | 0.000 |
| scratch128-n2 | 78621 | 1.000 [1.0, 1.0, 1.0] | 0.986 [0.986, 0.985, 0.986] | 1.000 | 0.985 | 0.984 | 0.072 | 0.000 |
| scratch1024-n2 | 78621 | 1.000 [1.0, 1.0, 1.0] | 0.988 [0.989, 0.988, 0.988] | 1.000 | 0.987 | 0.987 | 0.073 | 0.000 |

Selected updates and compute: warm128-n0-s0 u30000 400s, warm128-n0-s1 u22000 416s, warm128-n0-s2 u29500 445s, warm128-n1-s0 u26500 451s, warm128-n1-s1 u30000 448s, warm128-n1-s2 u27000 442s, warm128-n2-s0 u22500 442s, warm128-n2-s1 u30000 464s, warm128-n2-s2 u29500 448s, scratch128-n2-s0 u27000 451s, scratch128-n2-s1 u28500 432s, scratch128-n2-s2 u29500 429s, scratch1024-n2-s0 u30000 758s, scratch1024-n2-s1 u28500 780s, scratch1024-n2-s2 u24000 743s

## Final test states (fresh r7_conf layouts; unique configurations)

| Condition | argmax-in-set [95% layout bootstrap] | per seed | mass [95%] | set loss per seed | recovery bank argmax per seed | recovery mass per seed |
|---|---|---|---|---|---|---|
| warm128-n0 | 0.905 [0.894, 0.916] | [0.903, 0.905, 0.907] | 0.901 [0.889, 0.911] | [0.595, 0.477, 0.663] | [0.846, 0.879, 0.879] | [0.844, 0.868, 0.875] |
| warm128-n1 | 0.951 [0.943, 0.958] | [0.949, 0.956, 0.949] | 0.948 [0.939, 0.955] | [0.347, 0.26, 0.231] | [0.938, 0.96, 0.915] | [0.935, 0.951, 0.911] |
| warm128-n2 | 0.975 [0.969, 0.980] | [0.972, 0.977, 0.977] | 0.974 [0.968, 0.979] | [0.18, 0.133, 0.146] | [0.973, 0.975, 0.954] | [0.971, 0.97, 0.957] |
| scratch128-n2 | 0.979 [0.973, 0.984] | [0.98, 0.98, 0.978] | 0.977 [0.971, 0.982] | [0.117, 0.112, 0.15] | [0.981, 0.979, 0.979] | [0.979, 0.978, 0.982] |
| scratch1024-n2 | 0.980 [0.974, 0.985] | [0.981, 0.981, 0.979] | 0.979 [0.973, 0.985] | [0.155, 0.139, 0.111] | [0.963, 0.99, 0.967] | [0.965, 0.99, 0.967] |

By stratum (test argmax-in-set, seed mean; n unique states):

| Condition | on_track | wrong_key | key_lost | backtracked | all_unlocked |
|---|---|---|---|---|---|
| warm128-n0 | 0.920 (6598) | 0.823 (760) | 0.818 (224) | 0.838 (405) | 0.997 (101) |
| warm128-n1 | 0.960 (6598) | 0.916 (760) | 0.921 (224) | 0.877 (405) | 0.997 (101) |
| warm128-n2 | 0.982 (6598) | 0.964 (760) | 0.963 (224) | 0.896 (405) | 1.000 (101) |
| scratch128-n2 | 0.985 (6598) | 0.972 (760) | 0.985 (224) | 0.891 (405) | 1.000 (101) |
| scratch1024-n2 | 0.987 (6598) | 0.975 (760) | 0.984 (224) | 0.880 (405) | 0.997 (101) |

By label action type (a state counts in every type in its label set):

| Condition | turn | forward | pickup | drop | toggle |
|---|---|---|---|---|---|
| warm128-n0 | 0.906 (5007) | 0.940 (3411) | 0.881 (314) | 0.775 (442) | 0.952 (187) |
| warm128-n1 | 0.950 (5007) | 0.968 (3411) | 0.962 (314) | 0.903 (442) | 0.977 (187) |
| warm128-n2 | 0.974 (5007) | 0.985 (3411) | 0.985 (314) | 0.961 (442) | 0.986 (187) |
| scratch128-n2 | 0.979 (5007) | 0.984 (3411) | 0.989 (314) | 0.975 (442) | 0.989 (187) |
| scratch1024-n2 | 0.978 (5007) | 0.988 (3411) | 0.996 (314) | 0.976 (442) | 0.982 (187) |

Recovery bank by stratum (argmax-in-set, seed mean):

- warm128-n0: on_track 0.903, wrong_key 0.816, key_lost 0.757, backtracked 0.865, all_unlocked 1.000
- warm128-n1: on_track 0.972, wrong_key 0.924, key_lost 0.875, backtracked 0.917, all_unlocked 1.000
- warm128-n2: on_track 0.972, wrong_key 0.965, key_lost 0.941, backtracked 0.958, all_unlocked 1.000
- scratch128-n2: on_track 0.990, wrong_key 0.990, key_lost 0.986, backtracked 0.934, all_unlocked 1.000
- scratch1024-n2: on_track 0.972, wrong_key 0.969, key_lost 0.990, backtracked 0.934, all_unlocked 1.000

Paired comparisons (test argmax-in-set; per-layout differences of seed means):

- scratch1024-n2 - scratch128-n2: +0.001 [-0.001, +0.003]; per seed [0.001, 0.001, 0.001]
- warm128-n2 - scratch128-n2: -0.004 [-0.007, -0.002]; per seed [-0.008, -0.003, -0.0]
- warm128-n2 - warm128-n0: +0.070 [+0.062, +0.078]; per seed [0.068, 0.072, 0.071]

## Rollouts (final panel, 64 layouts, deterministic argmax, prefix only)

| Controller | Reached | tau mean | failures by stratum | failures by stage | locked toggles | wrong-key pickups | premature drops | no-ops | pose repeat |
|---|---|---|---|---|---|---|---|---|---|
| bc-s116 | 0/64 | — | {'on_track': 57, 'wrong_key': 7} | {'prefix_m0': 47, 'prefix_m1': 15, 'prefix_m2': 2} | 46.8 | 2.95 | 0.00 | 92.1 | 0.92 |
| bc-s117 | 1/64 | 39.0 | {'on_track': 60, 'backtracked': 2, 'wrong_key': 1} | {'prefix_m0': 54, 'prefix_m1': 8, 'prefix_m2': 1} | 37.0 | 1.02 | 0.00 | 82.8 | 0.94 |
| bc-s118 | 0/64 | — | {'on_track': 62, 'wrong_key': 2} | {'prefix_m0': 52, 'prefix_m1': 11, 'prefix_m2': 1} | 31.5 | 0.92 | 0.00 | 126.2 | 0.95 |
| expert | 64/64 | 40.6 | {} | {} | 0.0 | 0.00 | 0.00 | 0.0 | 0.23 |
| scratch1024-n2-s0 | 58/64 | 40.4 | {'on_track': 5, 'wrong_key': 1} | {'prefix_m2': 6} | 0.0 | 0.89 | 0.00 | 0.0 | 0.28 |
| scratch1024-n2-s1 | 50/64 | 40.6 | {'on_track': 11, 'wrong_key': 3} | {'prefix_m1': 2, 'prefix_m2': 12} | 0.0 | 5.44 | 0.00 | 0.0 | 0.35 |
| scratch1024-n2-s2 | 57/64 | 42.6 | {'wrong_key': 3, 'on_track': 4} | {'prefix_m1': 2, 'prefix_m2': 5} | 0.0 | 1.78 | 0.00 | 2.0 | 0.29 |
| scratch128-n2-s0 | 48/64 | 40.9 | {'wrong_key': 2, 'on_track': 11, 'backtracked': 2, 'key_lost': 1} | {'prefix_m1': 7, 'prefix_m2': 9} | 0.0 | 1.00 | 0.02 | 3.7 | 0.38 |
| scratch128-n2-s1 | 45/64 | 41.1 | {'key_lost': 3, 'wrong_key': 5, 'on_track': 11} | {'prefix_m1': 5, 'prefix_m2': 14} | 0.0 | 1.78 | 1.00 | 0.0 | 0.40 |
| scratch128-n2-s2 | 43/64 | 41.6 | {'wrong_key': 4, 'on_track': 17} | {'prefix_m1': 6, 'prefix_m2': 15} | 0.0 | 3.66 | 1.22 | 3.6 | 0.43 |
| warm128-n0-s0 | 6/64 | 44.3 | {'on_track': 35, 'wrong_key': 20, 'key_lost': 3} | {'prefix_m0': 6, 'prefix_m1': 35, 'prefix_m2': 17} | 0.0 | 3.91 | 2.86 | 25.0 | 0.80 |
| warm128-n0-s1 | 19/64 | 46.0 | {'on_track': 29, 'wrong_key': 16} | {'prefix_m0': 4, 'prefix_m1': 23, 'prefix_m2': 18} | 0.0 | 6.50 | 0.00 | 24.8 | 0.68 |
| warm128-n0-s2 | 13/64 | 42.6 | {'on_track': 26, 'wrong_key': 22, 'key_lost': 3} | {'prefix_m0': 6, 'prefix_m1': 28, 'prefix_m2': 17} | 1.7 | 1.77 | 4.61 | 17.1 | 0.73 |
| warm128-n1-s0 | 24/64 | 42.6 | {'on_track': 26, 'wrong_key': 13, 'backtracked': 1} | {'prefix_m0': 1, 'prefix_m1': 15, 'prefix_m2': 24} | 0.0 | 1.73 | 3.62 | 18.5 | 0.61 |
| warm128-n1-s1 | 29/64 | 42.1 | {'on_track': 27, 'wrong_key': 7, 'backtracked': 1} | {'prefix_m0': 2, 'prefix_m1': 20, 'prefix_m2': 13} | 0.0 | 3.83 | 0.84 | 11.3 | 0.57 |
| warm128-n1-s2 | 23/64 | 47.1 | {'on_track': 30, 'wrong_key': 10, 'key_lost': 1} | {'prefix_m0': 1, 'prefix_m1': 21, 'prefix_m2': 19} | 0.0 | 7.25 | 4.67 | 9.2 | 0.64 |
| warm128-n2-s0 | 43/64 | 41.0 | {'on_track': 13, 'wrong_key': 7, 'key_lost': 1} | {'prefix_m1': 8, 'prefix_m2': 13} | 0.0 | 1.73 | 0.02 | 14.7 | 0.43 |
| warm128-n2-s1 | 51/64 | 41.1 | {'on_track': 12, 'key_lost': 1} | {'prefix_m1': 8, 'prefix_m2': 5} | 0.0 | 0.00 | 0.02 | 1.8 | 0.35 |
| warm128-n2-s2 | 47/64 | 41.0 | {'wrong_key': 5, 'on_track': 12} | {'prefix_m0': 1, 'prefix_m1': 3, 'prefix_m2': 13} | 0.0 | 1.77 | 0.88 | 5.4 | 0.39 |

Conditions (boundary reach; seed means per layout; 95% layout bootstrap):

- warm128-n0: 0.198 [0.130, 0.271]; per seed [0.094, 0.297, 0.203]
- warm128-n1: 0.396 [0.307, 0.490]; per seed [0.375, 0.453, 0.359]
- warm128-n2: 0.734 [0.656, 0.807]; per seed [0.672, 0.797, 0.734]
- scratch128-n2: 0.708 [0.620, 0.792]; per seed [0.75, 0.703, 0.672]
- scratch1024-n2: 0.859 [0.797, 0.917]; per seed [0.906, 0.781, 0.891]
- bc_warm_start: 0.005 [0.000, 0.016]; per seed [0.0, 0.016, 0.0]
- expert: 1.000 [1.000, 1.000]; per seed [1.0]

Paired rollout comparisons:

- scratch1024-n2 - scratch128-n2: +0.151 [+0.083, +0.224]
- warm128-n2 - scratch128-n2: +0.026 [-0.052, +0.109]
- warm128-n2 - warm128-n0: +0.536 [+0.448, +0.625]
- warm128-n2 - bc_warm_start: +0.729 [+0.651, +0.802]

Determinism check (second attempt identical): {'warm128-n2-s0': [8, 8], 'bc-s116': [8, 8]}
