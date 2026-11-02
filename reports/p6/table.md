# Controller diagnostics on frozen policies (d6_ctrl 64 K=3 layouts x 2 attempts; exploratory)

Problems: none

## Cohort A4 (a4_s70, a4_s71, a4_s72, a4_s73)

| condition | P1 = S/n | Δ vs base [95% t over layouts] | Bonferroni | crossed bootstrap | policies > 0 | q = A/n | r = S_A/A | F/A | exposure | helper fraction | ineffective prefix / ep | locked toggles / ep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 0.432 (221/512) | — | — | — | — | 0.643 (329/512) | 0.672 (221/329) | 0.933 (307/329) | 0.000 | 0.000 | 23.6 | 11.4 |
| key_mid | 0.482 (247/512) | +0.051 [-0.013, +0.115] | [-0.041, +0.143] | [-0.027, +0.127] | 4/4 | 0.736 (377/512) | 0.655 (247/377) | 0.942 (355/377) | 0.979 | 0.046 | 14.5 | 5.5 |
| door_mid | 0.404 (207/512) | -0.027 [-0.064, +0.009] | [-0.080, +0.025] | [-0.096, +0.031] | 1/4 | 0.621 (318/512) | 0.651 (207/318) | 0.950 (302/318) | 0.785 | 0.053 | 25.0 | 12.8 |
| both_mid | 0.555 (284/512) | +0.123 [+0.062, +0.184] | [+0.035, +0.211] | [+0.047, +0.199] | 4/4 | 0.812 (416/512) | 0.683 (284/416) | 0.957 (398/416) | 0.979 | 0.124 | 12.9 | 6.1 |
| key_all | 0.531 (272/512) | +0.100 [+0.030, +0.169] | [-0.001, +0.200] | [-0.004, +0.193] | 4/4 | 0.803 (411/512) | 0.662 (272/411) | 0.971 (399/411) | 1.000 | 0.131 | 10.5 | 3.3 |
| door_all | 0.459 (235/512) | +0.027 [-0.012, +0.066] | [-0.029, +0.084] | [-0.043, +0.098] | 2/4 | 0.672 (344/512) | 0.683 (235/344) | 0.968 (333/344) | 0.986 | 0.164 | 24.2 | 13.6 |
| both_all | 0.701 (359/512) | +0.270 [+0.202, +0.337] | [+0.172, +0.367] | [+0.168, +0.379] | 4/4 | 1.000 (512/512) | 0.701 (359/512) | 1.000 (512/512) | 1.000 | 0.449 | 0.0 | 0.0 |
| mask_prefix | 0.461 (236/512) | +0.029 [-0.010, +0.068] | [-0.027, +0.085] | [-0.041, +0.102] | 3/4 | 0.691 (354/512) | 0.667 (236/354) | 0.949 (336/354) | 0.000 | 0.000 | 0.0 | 0.0 |

Interactions (both − key − door + base), cohort mean [95% t; crossed bootstrap]:
- mid: +0.100 [+0.053, +0.147; +0.029, +0.176]
- all: +0.143 [+0.067, +0.219; +0.016, +0.270]

Per-policy Δ P1 vs base (mean over layouts [95% t]):

| policy | base P1 | key_mid | door_mid | both_mid | key_all | door_all | both_all | mask_prefix | int. mid | int. all |
|---|---|---|---|---|---|---|---|---|---|---|
| a4_s70 | 0.516 | +0.023 [-0.080, +0.126] | -0.016 [-0.078, +0.047] | +0.141 [+0.045, +0.236] | +0.125 [+0.001, +0.249] | -0.016 [-0.086, +0.055] | +0.258 [+0.153, +0.362] | +0.016 [-0.068, +0.099] | +0.133 | +0.148 |
| a4_s71 | 0.492 | +0.055 [-0.043, +0.152] | -0.016 [-0.074, +0.043] | +0.094 [-0.010, +0.198] | +0.008 [-0.115, +0.131] | +0.078 [-0.003, +0.159] | +0.211 [+0.098, +0.324] | +0.016 [-0.061, +0.093] | +0.055 | +0.125 |
| a4_s72 | 0.391 | +0.055 [-0.077, +0.187] | -0.102 [-0.182, -0.021] | +0.102 [-0.030, +0.234] | +0.133 [+0.003, +0.263] | -0.031 [-0.108, +0.045] | +0.383 [+0.250, +0.516] | -0.023 [-0.108, +0.061] | +0.148 | +0.281 |
| a4_s73 | 0.328 | +0.070 [-0.010, +0.150] | +0.023 [-0.045, +0.092] | +0.156 [+0.068, +0.245] | +0.133 [+0.019, +0.247] | +0.078 [-0.003, +0.159] | +0.227 [+0.113, +0.340] | +0.109 [+0.028, +0.191] | +0.062 | +0.016 |

Assistance (pooled over the cohort; evaluated / assisted ok / unresolved / certified impossible / not needed; helper actions):

- key_mid: ka1: 502/501/0/1/0 (2836); key lost after KA in 243 eps; backtrack after DA in 0 eps
- door_mid: da1: 409/402/2/5/0 (3379); key lost after KA in 0 eps; backtrack after DA in 8 eps
- both_mid: ka1: 502/501/0/1/0 (2836); da1: 501/500/0/1/0 (4376); key lost after KA in 0 eps; backtrack after DA in 7 eps
- key_all: ka0: 512/512/0/0/0 (2376); ka1: 512/512/0/0/0 (2866); ka2: 446/445/0/1/0 (2333); key lost after KA in 326 eps; backtrack after DA in 0 eps
- door_all: da0: 506/505/0/1/0 (3981); da1: 407/402/3/2/0 (3411); da2: 349/344/0/5/0 (2599); key lost after KA in 0 eps; backtrack after DA in 9 eps
- both_all: ka0: 512/512/0/0/0 (2376); ka1: 512/512/0/0/0 (2968); ka2: 512/512/0/0/0 (2936); da0: 512/512/0/0/0 (4160); da1: 512/512/0/0/0 (4512); da2: 512/512/0/0/0 (4192); key lost after KA in 0 eps; backtrack after DA in 0 eps

Mask: mean removed mass per masked step 0.076; share of masked steps whose action changed 0.088; base ineffective share of learner prefix steps 0.235.

Rescue of base failures (pre-boundary / post-arrival) and loss of base successes:

- key_mid: pre 66/183, post 15/108; lost 55/221
- door_mid: pre 16/183, post 17/108; lost 47/221
- both_mid: pre 85/183, post 30/108; lost 52/221
- key_all: pre 91/183, post 33/108; lost 73/221
- door_all: pre 32/183, post 26/108; lost 44/221
- both_all: pre 136/183, post 44/108; lost 42/221
- mask_prefix: pre 35/183, post 28/108; lost 48/221

Timing (pooled): arrival time median / remaining median; module durations (median, entered):

- base: tau 70.000 / remaining 76.000; m0 22.000 (512); m1 28.000 (502); m2 18.000 (391); end stages {'prefix_m0': 8, 'prefix_m1': 111, 'prefix_m2': 61, 'suffix_no_target': 54, 'carrying': 275}
- key_mid: tau 65.000 / remaining 80.000; m0 22.000 (512); m1 20.000 (502); m2 18.000 (428); end stages {'prefix_m0': 8, 'prefix_m1': 70, 'prefix_m2': 55, 'suffix_no_target': 64, 'carrying': 313}
- door_mid: tau 64.000 / remaining 82.000; m0 22.000 (512); m1 20.000 (502); m2 20.000 (402); end stages {'prefix_m0': 8, 'prefix_m1': 102, 'prefix_m2': 78, 'suffix_no_target': 64, 'carrying': 254}
- both_mid: tau 58.000 / remaining 87.000; m0 22.000 (512); m1 14.000 (502); m2 20.000 (500); end stages {'prefix_m0': 8, 'prefix_m1': 4, 'prefix_m2': 79, 'suffix_no_target': 71, 'carrying': 345}
- key_all: tau 53.000 / remaining 92.000; m0 15.000 (512); m1 20.000 (512); m2 15.000 (446); end stages {'prefix_m0': 0, 'prefix_m1': 63, 'prefix_m2': 38, 'suffix_no_target': 73, 'carrying': 338}
- door_all: tau 57.000 / remaining 89.000; m0 17.000 (512); m1 20.000 (505); m2 18.000 (402); end stages {'prefix_m0': 7, 'prefix_m1': 103, 'prefix_m2': 56, 'suffix_no_target': 68, 'carrying': 276}
- both_all: tau 41.000 / remaining 104.000; m0 12.500 (512); m1 14.000 (512); m2 14.000 (512); end stages {'prefix_m0': 0, 'prefix_m1': 0, 'prefix_m2': 0, 'suffix_no_target': 95, 'carrying': 417}
- mask_prefix: tau 66.000 / remaining 78.000; m0 21.000 (512); m1 27.000 (508); m2 18.000 (399); end stages {'prefix_m0': 4, 'prefix_m1': 103, 'prefix_m2': 49, 'suffix_no_target': 63, 'carrying': 291}

## Cohort P5 (p5_s90, p5_s91, p5_s92, p5_s93)

| condition | P1 = S/n | Δ vs base [95% t over layouts] | Bonferroni | crossed bootstrap | policies > 0 | q = A/n | r = S_A/A | F/A | exposure | helper fraction | ineffective prefix / ep | locked toggles / ep |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 0.232 (119/512) | — | — | — | — | 0.432 (221/512) | 0.538 (119/221) | 0.928 (205/221) | 0.000 | 0.000 | 36.2 | 14.2 |
| key_mid | 0.291 (149/512) | +0.059 [+0.007, +0.110] | [-0.015, +0.132] | [-0.008, +0.127] | 4/4 | 0.574 (294/512) | 0.507 (149/294) | 0.915 (269/294) | 0.902 | 0.039 | 25.1 | 9.2 |
| door_mid | 0.252 (129/512) | +0.020 [-0.004, +0.043] | [-0.014, +0.053] | [-0.025, +0.066] | 2/4 | 0.451 (231/512) | 0.558 (129/231) | 0.944 (218/231) | 0.576 | 0.037 | 36.1 | 14.8 |
| both_mid | 0.383 (196/512) | +0.150 [+0.095, +0.206] | [+0.071, +0.230] | [+0.080, +0.223] | 4/4 | 0.693 (355/512) | 0.552 (196/355) | 0.963 (342/355) | 0.902 | 0.104 | 20.1 | 7.8 |
| key_all | 0.391 (200/512) | +0.158 [+0.099, +0.218] | [+0.073, +0.244] | [+0.078, +0.236] | 4/4 | 0.738 (378/512) | 0.529 (200/378) | 0.979 (370/378) | 1.000 | 0.119 | 16.5 | 7.5 |
| door_all | 0.279 (143/512) | +0.047 [+0.009, +0.085] | [-0.008, +0.101] | [-0.012, +0.111] | 3/4 | 0.492 (252/512) | 0.567 (143/252) | 0.952 (240/252) | 0.918 | 0.121 | 38.0 | 16.7 |
| both_all | 0.570 (292/512) | +0.338 [+0.275, +0.401] | [+0.247, +0.429] | [+0.248, +0.430] | 4/4 | 1.000 (512/512) | 0.570 (292/512) | 1.000 (512/512) | 1.000 | 0.408 | 0.0 | 0.0 |
| mask_prefix | 0.256 (131/512) | +0.023 [-0.012, +0.059] | [-0.028, +0.075] | [-0.033, +0.078] | 2/4 | 0.498 (255/512) | 0.514 (131/255) | 0.890 (227/255) | 0.000 | 0.000 | 0.0 | 0.0 |

Interactions (both − key − door + base), cohort mean [95% t; crossed bootstrap]:
- mid: +0.072 [+0.027, +0.118; +0.014, +0.133]
- all: +0.133 [+0.067, +0.199; +0.033, +0.230]

Per-policy Δ P1 vs base (mean over layouts [95% t]):

| policy | base P1 | key_mid | door_mid | both_mid | key_all | door_all | both_all | mask_prefix | int. mid | int. all |
|---|---|---|---|---|---|---|---|---|---|---|
| p5_s90 | 0.250 | +0.047 [-0.044, +0.138] | -0.008 [-0.065, +0.049] | +0.117 [+0.026, +0.208] | +0.180 [+0.074, +0.285] | +0.086 [+0.001, +0.171] | +0.383 [+0.289, +0.477] | -0.008 [-0.093, +0.077] | +0.078 | +0.117 |
| p5_s91 | 0.125 | +0.109 [+0.025, +0.194] | -0.016 [-0.047, +0.016] | +0.195 [+0.102, +0.289] | +0.203 [+0.115, +0.291] | -0.016 [-0.065, +0.034] | +0.367 [+0.258, +0.477] | +0.055 [-0.016, +0.125] | +0.102 | +0.180 |
| p5_s92 | 0.352 | +0.031 [-0.052, +0.114] | +0.055 [-0.009, +0.118] | +0.156 [+0.068, +0.245] | +0.125 [+0.018, +0.232] | +0.070 [-0.006, +0.147] | +0.242 [+0.140, +0.344] | +0.047 [-0.019, +0.113] | +0.070 | +0.047 |
| p5_s93 | 0.203 | +0.047 [-0.029, +0.123] | +0.047 [-0.006, +0.100] | +0.133 [+0.040, +0.225] | +0.125 [+0.018, +0.232] | +0.047 [-0.026, +0.120] | +0.359 [+0.254, +0.465] | +0.000 [-0.089, +0.089] | +0.039 | +0.188 |

Assistance (pooled over the cohort; evaluated / assisted ok / unresolved / certified impossible / not needed; helper actions):

- key_mid: ka1: 465/462/0/3/0 (2601); key lost after KA in 241 eps; backtrack after DA in 0 eps
- door_mid: da1: 302/295/3/4/0 (2491); key lost after KA in 0 eps; backtrack after DA in 0 eps
- both_mid: ka1: 465/462/0/3/0 (2601); da1: 462/459/0/3/0 (4025); key lost after KA in 2 eps; backtrack after DA in 1 eps
- key_all: ka0: 512/512/0/0/0 (2376); ka1: 510/510/0/0/0 (2899); ka2: 431/430/0/1/0 (2252); key lost after KA in 355 eps; backtrack after DA in 0 eps
- door_all: da0: 472/470/0/2/0 (3650); da1: 306/300/5/1/0 (2488); da2: 257/252/1/4/0 (1922); key lost after KA in 0 eps; backtrack after DA in 0 eps
- both_all: ka0: 512/512/0/0/0 (2376); ka1: 512/512/0/0/0 (2968); ka2: 512/512/0/0/0 (2936); da0: 512/512/0/0/0 (4160); da1: 512/512/0/0/0 (4512); da2: 512/512/0/0/0 (4192); key lost after KA in 0 eps; backtrack after DA in 0 eps

Mask: mean removed mass per masked step 0.106; share of masked steps whose action changed 0.119; base ineffective share of learner prefix steps 0.308.

Rescue of base failures (pre-boundary / post-arrival) and loss of base successes:

- key_mid: pre 52/291, post 11/102; lost 33/119
- door_mid: pre 15/291, post 15/102; lost 20/119
- both_mid: pre 80/291, post 24/102; lost 27/119
- key_all: pre 99/291, post 28/102; lost 46/119
- door_all: pre 33/291, post 24/102; lost 33/119
- both_all: pre 152/291, post 43/102; lost 22/119
- mask_prefix: pre 39/291, post 18/102; lost 45/119

Timing (pooled): arrival time median / remaining median; module durations (median, entered):

- base: tau 79.000 / remaining 67.000; m0 33.000 (512); m1 39.000 (467); m2 19.000 (266); end stages {'prefix_m0': 42, 'prefix_m1': 197, 'prefix_m2': 51, 'suffix_no_target': 68, 'carrying': 153}
- key_mid: tau 76.000 / remaining 70.000; m0 33.000 (512); m1 22.000 (467); m2 18.000 (373); end stages {'prefix_m0': 42, 'prefix_m1': 87, 'prefix_m2': 89, 'suffix_no_target': 88, 'carrying': 206}
- door_mid: tau 70.000 / remaining 76.000; m0 33.000 (512); m1 26.000 (467); m2 19.000 (295); end stages {'prefix_m0': 42, 'prefix_m1': 175, 'prefix_m2': 63, 'suffix_no_target': 66, 'carrying': 165}
- both_mid: tau 66.000 / remaining 80.000; m0 33.000 (512); m1 14.000 (467); m2 20.000 (459); end stages {'prefix_m0': 42, 'prefix_m1': 11, 'prefix_m2': 103, 'suffix_no_target': 113, 'carrying': 242}
- key_all: tau 56.000 / remaining 88.000; m0 17.000 (512); m1 22.000 (510); m2 15.000 (432); end stages {'prefix_m0': 1, 'prefix_m1': 74, 'prefix_m2': 58, 'suffix_no_target': 111, 'carrying': 267}
- door_all: tau 64.000 / remaining 82.000; m0 24.000 (512); m1 24.000 (470); m2 18.000 (300); end stages {'prefix_m0': 42, 'prefix_m1': 170, 'prefix_m2': 48, 'suffix_no_target': 69, 'carrying': 183}
- both_all: tau 41.000 / remaining 104.000; m0 12.500 (512); m1 14.000 (512); m2 14.000 (512); end stages {'prefix_m0': 0, 'prefix_m1': 0, 'prefix_m2': 0, 'suffix_no_target': 135, 'carrying': 377}
- mask_prefix: tau 73.000 / remaining 72.000; m0 28.000 (512); m1 33.000 (493); m2 17.000 (306); end stages {'prefix_m0': 17, 'prefix_m1': 180, 'prefix_m2': 60, 'suffix_no_target': 79, 'carrying': 176}

