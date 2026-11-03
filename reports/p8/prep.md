# Capability audit — preparation (validation, dataset, tiny check, fits; final test not read)

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
