# Results

Raw output of the five commands on prices to 2026-09-29 and the source-checked catalog (48 events). Window sums are log abnormal returns; bearish events are sign-flipped. p is a two-sided bootstrap p-value of bull minus bear unless stated. Read [PRIMER.md](PRIMER.md) for what the numbers mean.

## `uransig run`

```

== all events, basket: 22 bull, 21 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift -0.003          +0.017       -0.020  [-0.069, +0.031] +0.512
jump      +0.045          +0.012       +0.033  [+0.003, +0.063] +0.070
drift     +0.040          +0.036       +0.003  [-0.051, +0.061] +0.949
late      -0.084          +0.036       -0.120  [-0.176, -0.063] +0.001
car_0_20  +0.085          +0.048       +0.037  [-0.029, +0.105] +0.366
speed     +0.534          +0.249       +0.285  [-0.148, +1.207] +0.234

== surprises only: 18 bull, 15 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift -0.008          -0.007       -0.001  [-0.062, +0.059] +0.962
jump      +0.058          +0.017       +0.040  [+0.002, +0.077] +0.080
drift     +0.056          +0.062       -0.006  [-0.063, +0.051] +0.839
late      -0.065          +0.020       -0.084  [-0.147, -0.020] +0.026
car_0_20  +0.113          +0.079       +0.035  [-0.037, +0.103] +0.428
speed     +0.509          +0.219       +0.290  [-0.010, +0.975] +0.108

== known release session: 16 bull, 10 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift -0.021          +0.031       -0.052  [-0.112, +0.007] +0.150
jump      +0.048          +0.038       +0.009  [-0.036, +0.050] +0.708
drift     +0.047          +0.059       -0.012  [-0.076, +0.054] +0.755
late      -0.085          -0.012       -0.073  [-0.138, -0.003] +0.084
car_0_20  +0.095          +0.097       -0.002  [-0.083, +0.075] +0.960
speed     +0.502          +0.396       +0.106  [-0.333, +0.632] +0.636

== CCJ only: 22 bull, 21 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift +0.027          +0.013       +0.014  [-0.036, +0.066] +0.657
jump      +0.037          +0.011       +0.026  [-0.002, +0.054] +0.132
drift     +0.020          +0.029       -0.009  [-0.060, +0.044] +0.764
late      -0.075          +0.011       -0.086  [-0.149, -0.025] +0.016
car_0_20  +0.057          +0.041       +0.017  [-0.044, +0.079] +0.643
speed     +0.646          +0.276       +0.370  [-0.170, +2.271] +0.227

== drop DeepSeek and COVID: 20 bull, 20 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift -0.013          +0.018       -0.031  [-0.082, +0.022] +0.348
jump      +0.050          +0.007       +0.043  [+0.010, +0.074] +0.029
drift     +0.016          +0.033       -0.018  [-0.071, +0.034] +0.568
late      -0.086          +0.046       -0.132  [-0.188, -0.073] +0.001
car_0_20  +0.065          +0.041       +0.025  [-0.046, +0.092] +0.549
speed     +0.762          +0.175       +0.588  [+0.058, +2.352] +0.067

== isolated events (no other event in -20..+60): 6 bull, 8 bear
            bull  bear (flipped)  bull - bear            90% CI      p
metric                                                                
pre_drift -0.060          +0.028       -0.088  [-0.158, -0.016] +0.046
jump      +0.037          +0.002       +0.035  [-0.012, +0.083] +0.222
drift     +0.059          +0.025       +0.034  [-0.067, +0.136] +0.598
late      -0.011          -0.036       +0.025  [-0.081, +0.126] +0.698
car_0_20  +0.096          +0.027       +0.069  [-0.042, +0.188] +0.322
speed     +0.387          +0.071       +0.316  [-0.582, +2.469] +0.341

== military / weapons events (unsigned, n=5)
pre_drift   +0.004
jump        +0.003
drift       +0.028
late        +0.024
car_0_20    +0.030

== placebo: 500 random days, std of each window for ONE event
pre_drift   +0.133
jump        +0.041
drift       +0.117
late        +0.181
car_0_20    +0.128
```

## `uransig speed`

```
== partial adjustment, days 0..20
Bullish            total +0.074  kappa 0.335  half-life 1.7 days  90% CI [0.2, 5.7]
Bearish (flipped)  total +0.070  kappa 0.050  half-life 13.5 days  90% CI [1.3, 69.0]
bear slower than bull in 84% of bootstrap draws

== daily equities vs physical trust, n=1245
equities -> trust  same-day +0.544  lags 1-5 sum +0.148 (t +2.6)  share same-day 79%
trust -> equities  same-day +0.815  lags 1-5 sum +0.249 (t +2.8)  share same-day 77%

== Cameco month-end vs spot, n=258
cross-corr -3:-0.00  -2:-0.07  -1:+0.03  +0:+0.22  +1:+0.25  +2:+0.10  +3:+0.04
Cameco -> spot with spot's own lags: same-month +0.131  lags 1-3 sum +0.207 (t +3.0)
spot autocorrelation at 1 month +0.30, Cameco +0.01

== Cameco month-average vs spot, n=258
cross-corr -3:-0.02  -2:-0.02  -1:+0.07  +0:+0.40  +1:+0.15  +2:+0.03  +3:+0.04
Cameco -> spot with spot's own lags: same-month +0.296  lags 1-3 sum +0.026 (t +0.4)
spot autocorrelation at 1 month +0.30, Cameco +0.22
```

## `uransig backtest`

```
      day0                                                   label direction  n_prior  expected  taken  gross    net
2011-03-11                              Fukushima Daiichi accident      bear        0       NaN  False +0.141 +0.000
2011-05-25                   Switzerland decides nuclear phase-out      bear        1       NaN  False +0.102 +0.000
2011-05-31                       Germany decides phase-out by 2022      bear        1       NaN  False +0.170 +0.000
2011-06-13                        Italy referendum rejects nuclear      bear        1       NaN  False +0.017 +0.000
2012-09-14                 Japan targets zero nuclear in the 2030s      bear        4       NaN  False +0.025 +0.000
2012-10-22                              Dominion to close Kewaunee      bear        5    +0.091   True +0.110 +0.106
2013-06-07                       Edison closes San Onofre for good      bear        6    +0.094   True +0.011 +0.007
2013-08-27                         Entergy to close Vermont Yankee      bear        7    +0.082   True +0.059 +0.055
2015-08-11                              Sendai 1 restarts in Japan      bull        0       NaN  False -0.027 +0.000
2015-10-13                                Entergy to close Pilgrim      bear        8    +0.079   True +0.154 +0.150
2016-06-02                 Exelon to close Clinton and Quad Cities      bear        9    +0.088   True +0.027 +0.024
2016-06-21                             PG&E to close Diablo Canyon      bear        9    +0.088   True +0.079 +0.075
2017-01-09                               Indian Point closure deal      bear       11    +0.081   True -0.045 -0.048
2017-01-10                             Kazatomprom cuts output 10%      bull        1       NaN  False +0.035 +0.000
2017-03-29                           Westinghouse files Chapter 11      bear       12    +0.071   True +0.107 +0.104
2017-05-30             Exelon to close TMI-1 absent policy support      bear       13    +0.074   True +0.023 +0.020
2017-07-31                         V.C. Summer new build abandoned      bear       14    +0.070   True +0.026 +0.022
2017-11-09                          Cameco suspends McArthur River      bull        2       NaN  False +0.075 +0.000
2017-12-04               Kazatomprom cuts output 20% for 2018-2020      bull        2       NaN  False -0.078 +0.000
2018-01-16                              Section 232 petition filed      bull        4       NaN  False +0.067 +0.000
2018-07-26                   McArthur River suspended indefinitely      bull        5    +0.014   True -0.008 -0.010
2019-05-08                           Exelon confirms TMI-1 closure      bear       15    +0.067   True -0.048 -0.051
2019-07-12                Section 232: no import quota for uranium      bear       16    +0.060   True +0.127 +0.123
2020-03-23                    Cameco suspends Cigar Lake for COVID      bull        6    +0.011   True +0.329 +0.327
2020-04-07                   Kazatomprom cuts operations for COVID      bull        6    +0.011   True +0.231 +0.229
2022-02-09                     Cameco plans McArthur River restart      bear       17    +0.064   True -0.222 -0.226
2022-08-24                 Japan signals restarts and new reactors      bull        8    +0.078   True +0.140 +0.138
2022-09-01                        California extends Diablo Canyon      bull        8    +0.078   True +0.070 +0.068
2023-04-17                   Germany shuts its last three reactors      bear       18    +0.048   True -0.145 -0.149
2023-07-26                                              Niger coup      bull       10    +0.083   True +0.130 +0.128
2023-12-04                          COP28 pledge to triple nuclear      bull       11    +0.088   True -0.107 -0.109
2024-01-12                     Kazatomprom warns of 2024 shortfall      bull       12    +0.071   True -0.131 -0.133
2024-05-13                         US bans Russian uranium imports      bull       13    +0.056   True -0.067 -0.069
2024-06-20                  Niger revokes Orano's Imouraren permit      bull       14    +0.047   True -0.110 -0.112
2024-08-23                          Kazatomprom cuts 2025 guidance      bull       15    +0.037   True +0.021 +0.019
2024-09-20                         Microsoft deal to restart TMI-1      bull       15    +0.037   True +0.208 +0.206
2024-10-14                                  Google-Kairos SMR deal      bull       16    +0.036   True -0.032 -0.034
2024-10-16                                Amazon-X-energy SMR deal      bull       16    +0.036   True -0.113 -0.115
2024-11-04 FERC rejects Talen-Amazon nuclear co-location expansion      bear       19    +0.038   True -0.049 -0.052
2024-11-15                 Russia restricts enriched uranium to US      bull       19    +0.033   True -0.058 -0.060
2025-01-27               DeepSeek scare hits AI power-demand trade      bear       20    +0.033   True +0.090 +0.087
2025-05-23                US executive orders to quadruple nuclear      bull       20    +0.029   True +0.107 +0.105
2025-08-22                  Kazatomprom cuts 2026 output about 10%      bull       21    +0.033   True +0.187 +0.185

== walk-forward summary
trades     33
hit_rate   +0.606
mean_net   +0.031
t_stat     +1.439
total_net  +1.012
bull: {'trades': 17, 'hit_rate': np.float64(0.5294117647058824), 'mean_net': np.float64(0.04494778400818135), 't_stat': np.float64(1.314318048569485), 'total_net': np.float64(0.7641123281390829)}
bear: {'trades': 16, 'hit_rate': np.float64(0.6875), 'mean_net': np.float64(0.015489758092326309), 't_stat': np.float64(0.61080711681867), 'total_net': np.float64(0.24783612947722095)}
random books with the same 33 trades: mean -0.003, share beating the strategy 7.0%
cost  0 bp/side: 33 trades, mean +0.033, t +1.53
cost 25 bp/side: 33 trades, mean +0.028, t +1.30
cost 50 bp/side: 33 trades, mean +0.023, t +1.06
```

## `uransig insider`

```
/Users/trma/Documents/Finance Tinkering/uranium-signatures/src/uransig/insider.py:70: RuntimeWarning: Mean of empty slice
  sd10 = np.nanstd(np.nanmean(resid, axis=0), ddof=1) * np.sqrt(WINDOW[1] - WINDOW[0] + 1)
      day0                                                   label direction knowable instrument   car  car_t  vol_z  reaction  flag
2011-03-11                              Fukushima Daiichi accident      bear       no     basket +0.07  +1.14  +0.84     +0.21 False
2011-05-25                   Switzerland decides nuclear phase-out      bear      yes     basket +0.02  +0.26  +0.38     -0.01 False
2011-05-31                       Germany decides phase-out by 2022      bear      yes     basket -0.08  -1.01  +0.18     +0.03 False
2011-06-13                        Italy referendum rejects nuclear      bear       no     basket +0.08  +0.99  +0.29     +0.02 False
2012-09-14                 Japan targets zero nuclear in the 2030s      bear      yes     basket +0.03  +0.51  -1.23     -0.00 False
2012-10-22                              Dominion to close Kewaunee      bear      yes     basket +0.02  +0.32  -1.11     -0.03 False
2012-10-22                              Dominion to close Kewaunee      bear      yes          D +0.00  +0.14  -0.65     +0.00 False
2013-06-07                       Edison closes San Onofre for good      bear      yes     basket -0.09  -1.76  +0.27     +0.03 False
2013-06-07                       Edison closes San Onofre for good      bear      yes        EIX -0.00  -0.22  +0.69     +0.01 False
2013-08-27                         Entergy to close Vermont Yankee      bear      yes     basket +0.01  +0.31  -0.48     +0.02 False
2013-08-27                         Entergy to close Vermont Yankee      bear      yes        ETR +0.00  +0.21  +0.57     +0.01 False
2015-08-11                              Sendai 1 restarts in Japan      bull       no     basket +0.14  +2.32  +0.09     -0.02 False
2015-10-13                                Entergy to close Pilgrim      bear      yes     basket -0.10  -1.44  +0.20     -0.02 False
2015-10-13                                Entergy to close Pilgrim      bear      yes        ETR -0.04  -2.01  -0.34     +0.00 False
2016-06-02                 Exelon to close Clinton and Quad Cities      bear      yes     basket +0.06  +0.92  -0.65     -0.05 False
2016-06-02                 Exelon to close Clinton and Quad Cities      bear      yes        EXC -0.01  -0.32  -1.13     +0.00 False
2016-06-21                             PG&E to close Diablo Canyon      bear      yes     basket -0.01  -0.09  +0.18     +0.03 False
2016-06-21                             PG&E to close Diablo Canyon      bear      yes        PCG -0.01  -0.31  -0.45     +0.00 False
2017-01-09                               Indian Point closure deal      bear      yes     basket -0.11  -1.92  +1.24     -0.12 False
2017-01-09                               Indian Point closure deal      bear      yes        ETR +0.00  +0.05  -0.34     +0.01 False
2017-01-10                             Kazatomprom cuts output 10%      bull      yes     basket +0.13  +2.21  +1.23     +0.14 False
2017-03-29                           Westinghouse files Chapter 11      bear      yes     basket +0.02  +0.32  +0.50     +0.01 False
2017-05-30             Exelon to close TMI-1 absent policy support      bear      yes     basket +0.04  +0.55  +0.11     +0.02 False
2017-05-30             Exelon to close TMI-1 absent policy support      bear      yes        EXC +0.02  +0.71  +0.88     +0.01 False
2017-07-31                         V.C. Summer new build abandoned      bear      yes     basket -0.06  -0.82  +0.38     -0.01 False
2017-11-09                          Cameco suspends McArthur River      bull      yes     basket -0.02  -0.29  +0.24     +0.13 False
2017-11-09                          Cameco suspends McArthur River      bull      yes        CCJ -0.02  -0.19  +0.11     +0.04 False
2017-12-04               Kazatomprom cuts output 20% for 2018-2020      bull      yes     basket +0.00  +0.01  +0.90     +0.12 False
2018-01-16                              Section 232 petition filed      bull      yes     basket -0.08  -1.02  +0.45     -0.04 False
2018-01-16                              Section 232 petition filed      bull      yes       UUUU +0.10  +0.89  -0.11     +0.07 False
2018-07-26                   McArthur River suspended indefinitely      bull      yes     basket -0.04  -0.52  +0.05     +0.03 False
2018-07-26                   McArthur River suspended indefinitely      bull      yes        CCJ +0.01  +0.21  -0.02     +0.01 False
2019-05-08                           Exelon confirms TMI-1 closure      bear      yes     basket +0.03  +0.56  -0.22     +0.03 False
2019-05-08                           Exelon confirms TMI-1 closure      bear      yes        EXC -0.02  -1.62  -0.08     +0.01 False
2019-07-12                Section 232: no import quota for uranium      bear      yes     basket +0.02  +0.29  -0.73     +0.01 False
2019-07-12                Section 232: no import quota for uranium      bear      yes       UUUU +0.03  +0.23  +0.20     +0.47 False
2020-03-23                    Cameco suspends Cigar Lake for COVID      bull      yes     basket -0.03  -0.58  +1.27     +0.03 False
2020-03-23                    Cameco suspends Cigar Lake for COVID      bull      yes        CCJ +0.02  +0.42  +1.29     +0.01 False
2020-04-07                   Kazatomprom cuts operations for COVID      bull      yes     basket +0.16  +3.63  +1.38     -0.03 False
2022-02-09                     Cameco plans McArthur River restart      bear      yes     basket +0.06  +0.54  +0.01     -0.08 False
2022-02-09                     Cameco plans McArthur River restart      bear      yes        CCJ -0.07  -0.71  +0.13     +0.11 False
2022-08-24                 Japan signals restarts and new reactors      bull      yes     basket -0.13  -1.35  -0.85     +0.10 False
2022-09-01                        California extends Diablo Canyon      bull       no     basket +0.25  +2.59  +0.28     -0.03 False
2023-04-17                   Germany shuts its last three reactors      bear       no     basket +0.08  +0.96  -1.05     +0.01 False
2023-07-26                                              Niger coup      bull       no     basket -0.01  -0.07  -0.75     -0.03 False
2023-12-04                          COP28 pledge to triple nuclear      bull       no     basket -0.00  -0.01  +0.73     +0.02 False
2024-01-12                     Kazatomprom warns of 2024 shortfall      bull      yes     basket +0.04  +0.73  +0.85     +0.08 False
2024-05-13                         US bans Russian uranium imports      bull       no     basket -0.02  -0.32  +0.91     -0.01 False
2024-06-20                  Niger revokes Orano's Imouraren permit      bull      yes     basket -0.07  -1.05  -0.00     -0.03 False
2024-08-23                          Kazatomprom cuts 2025 guidance      bull      yes     basket -0.03  -0.43  -0.38     +0.06 False
2024-09-20                         Microsoft deal to restart TMI-1      bull      yes     basket +0.03  +0.37  -0.25     +0.09 False
2024-09-20                         Microsoft deal to restart TMI-1      bull      yes        CEG +0.10  +1.37  +0.36     +0.19 False
2024-10-14                                  Google-Kairos SMR deal      bull      yes     basket +0.01  +0.10  -0.08     +0.03 False
2024-10-16                                Amazon-X-energy SMR deal      bull      yes     basket +0.04  +0.48  -0.17     +0.10 False
2024-11-04 FERC rejects Talen-Amazon nuclear co-location expansion      bear      yes     basket +0.06  +0.77  +0.10     +0.04 False
2024-11-15                 Russia restricts enriched uranium to US      bull      yes     basket -0.08  -0.99  +0.44     +0.07 False
2024-11-15                 Russia restricts enriched uranium to US      bull      yes        LEU +0.32  +3.09  +4.78     +0.05  True
2025-01-27               DeepSeek scare hits AI power-demand trade      bear       no     basket -0.02  -0.22  +0.64     +0.11 False
2025-05-23                US executive orders to quadruple nuclear      bull      yes     basket +0.00  +0.03  +0.39     +0.12 False
2025-05-23                US executive orders to quadruple nuclear      bull      yes       OKLO +0.31  +1.06  +0.99     +0.25 False
2025-08-22                  Kazatomprom cuts 2026 output about 10%      bull      yes     basket -0.09  -1.06  -0.06     +0.05 False

== flag rates (car_t >= 3 and vol_z >= 2)
basket  events 0/43  random days 0.50% of 400  expected false flags among events 0.21
direct  events 1/18  random days 0.27% of 1499  expected false flags among events 0.05

== detection limits (median over events): run-up and volume needed for a flag
basket  run-up >= 21.5% over 10 days and volume >= 3.1x normal for 10 days
direct  run-up >= 13.0% over 10 days and volume >= 2.4x normal for 10 days

== basket, knowable vs not (signed CAR -10..-1)
knowable=yes n=34  mean run-up -0.007  mean t -0.04  mean vol_z +0.13  share t>1.64 6%
knowable=no  n= 9  mean run-up +0.064  mean t +0.82  mean vol_z +0.22  share t>1.64 22%
one-sided permutation p (knowable run-up > unknowable): 0.990
random days: share t>1.64 7%

== direct stocks: mean run-up +0.042, mean t +0.17, mean vol_z +0.38 (random days: t +0.02, vol_z +0.13)
```

## `uransig events`

```
      day0 session                                                   label direction    timing  pre_drift   jump  drift   late  car_0_20
2011-03-11     pre                              Fukushima Daiichi accident      bear  surprise     +0.214 +0.207 +0.141 +0.131    +0.347
2011-05-25     pre                   Switzerland decides nuclear phase-out      bear  surprise     +0.038 -0.007 +0.102 +0.037    +0.095
2011-05-31     pre                       Germany decides phase-out by 2022      bear  surprise     -0.041 +0.027 +0.170 +0.013    +0.197
2011-06-13     pre                        Italy referendum rejects nuclear      bear scheduled     +0.033 +0.016 +0.017 +0.010    +0.033
2012-09-14     pre                 Japan targets zero nuclear in the 2030s      bear  surprise     -0.004 -0.002 +0.025 +0.023    +0.023
2012-10-22     pre                              Dominion to close Kewaunee      bear  surprise     +0.089 -0.027 +0.110 -0.189    +0.083
2013-06-07 unknown                       Edison closes San Onofre for good      bear  surprise     -0.086 +0.029 +0.011 +0.021    +0.040
2013-08-27 unknown                         Entergy to close Vermont Yankee      bear  surprise     +0.058 +0.016 +0.059 -0.015    +0.075
2013-12-10   intra                     Last Megatons-to-Megawatts delivery      none scheduled     +0.057 +0.026 +0.017 +0.283    +0.043
2015-08-11     pre                              Sendai 1 restarts in Japan      bull scheduled     -0.009 -0.024 -0.027 -0.143    -0.050
2015-10-13 unknown                                Entergy to close Pilgrim      bear  surprise     -0.032 -0.018 +0.154 -0.185    +0.136
2016-06-02 unknown                 Exelon to close Clinton and Quad Cities      bear  surprise     +0.080 -0.048 +0.027 +0.167    -0.021
2016-06-21 unknown                             PG&E to close Diablo Canyon      bear  surprise     -0.057 +0.032 +0.079 +0.168    +0.111
2017-01-09 unknown                               Indian Point closure deal      bear  surprise     -0.144 -0.116 -0.045 +0.124    -0.161
2017-01-10     pre                             Kazatomprom cuts output 10%      bull  surprise     +0.147 +0.143 +0.035 -0.158    +0.178
2017-03-29 unknown                           Westinghouse files Chapter 11      bear scheduled     +0.097 +0.010 +0.107 +0.162    +0.117
2017-05-30 unknown             Exelon to close TMI-1 absent policy support      bear  surprise     +0.004 +0.023 +0.023 -0.069    +0.046
2017-07-31 unknown                         V.C. Summer new build abandoned      bear  surprise     -0.121 -0.006 +0.026 +0.120    +0.020
2017-11-09    post                          Cameco suspends McArthur River      bull  surprise     -0.046 +0.129 +0.075 -0.164    +0.204
2017-12-04     pre               Kazatomprom cuts output 20% for 2018-2020      bull  surprise     +0.124 +0.123 -0.078 -0.108    +0.044
2018-01-16     pre                              Section 232 petition filed      bull  surprise     -0.193 -0.037 +0.067 -0.095    +0.030
2018-05-08   intra                             US leaves Iran nuclear deal      none scheduled     -0.007 -0.028 +0.123 -0.058    +0.095
2018-07-26    post                   McArthur River suspended indefinitely      bull  surprise     -0.050 +0.029 -0.008 +0.118    +0.022
2019-05-08 unknown                           Exelon confirms TMI-1 closure      bear scheduled     +0.081 +0.026 -0.048 +0.131    -0.022
2019-07-12   intra                Section 232: no import quota for uranium      bear scheduled     +0.018 +0.009 +0.127 -0.068    +0.136
2019-08-02     pre                                         INF treaty ends      none scheduled     -0.110 +0.013 -0.009 +0.001    +0.004
2020-03-23 unknown                    Cameco suspends Cigar Lake for COVID      bull  surprise     +0.033 +0.027 +0.329 -0.059    +0.356
2020-04-07     pre                   Kazatomprom cuts operations for COVID      bull  surprise     +0.149 -0.027 +0.231 -0.069    +0.204
2022-02-09 unknown                     Cameco plans McArthur River restart      bear scheduled     +0.162 -0.082 -0.222 +0.246    -0.304
2022-02-24     pre                                  Russia invades Ukraine      none  surprise     +0.046 +0.041 +0.088 -0.153    +0.129
2022-08-24     pre                 Japan signals restarts and new reactors      bull  surprise     -0.147 +0.100 +0.140 -0.187    +0.240
2022-09-01    post                        California extends Diablo Canyon      bull scheduled     +0.134 -0.030 +0.070 -0.269    +0.040
2023-02-21     pre                               Russia suspends New START      none  surprise     +0.035 -0.039 -0.081 +0.045    -0.120
2023-04-17 weekend                   Germany shuts its last three reactors      bear scheduled     +0.066 +0.013 -0.145 -0.028    -0.132
2023-07-26     pre                                              Niger coup      bull  surprise     -0.031 -0.026 +0.130 +0.096    +0.104
2023-12-04 weekend                          COP28 pledge to triple nuclear      bull scheduled     +0.000 +0.023 -0.107 -0.024    -0.084
2024-01-12     pre                     Kazatomprom warns of 2024 shortfall      bull  surprise     -0.031 +0.084 -0.131 -0.083    -0.047
2024-05-13 unknown                         US bans Russian uranium imports      bull scheduled     -0.045 -0.013 -0.067 -0.254    -0.080
2024-06-20 unknown                  Niger revokes Orano's Imouraren permit      bull  surprise     -0.118 -0.029 -0.110 -0.198    -0.139
2024-08-23     pre                          Kazatomprom cuts 2025 guidance      bull  surprise     -0.147 +0.061 +0.021 +0.089    +0.083
2024-09-20     pre                         Microsoft deal to restart TMI-1      bull  surprise     -0.012 +0.090 +0.208 -0.132    +0.299
2024-10-14 unknown                                  Google-Kairos SMR deal      bull  surprise     +0.136 +0.028 -0.032 +0.024    -0.003
2024-10-16 unknown                                Amazon-X-energy SMR deal      bull  surprise     +0.190 +0.098 -0.113 +0.001    -0.015
2024-11-04    post FERC rejects Talen-Amazon nuclear co-location expansion      bear  surprise     -0.090 +0.039 -0.049 +0.115    -0.010
2024-11-15     pre                 Russia restricts enriched uranium to US      bull  surprise     -0.103 +0.074 -0.058 -0.135    +0.016
2025-01-27     pre               DeepSeek scare hits AI power-demand trade      bear  surprise     -0.018 +0.109 +0.090 -0.167    +0.200
2025-05-23 unknown                US executive orders to quadruple nuclear      bull  surprise     +0.065 +0.123 +0.107 -0.010    +0.231
2025-08-22     pre                  Kazatomprom cuts 2026 output about 10%      bull  surprise     -0.119 +0.048 +0.187 -0.093    +0.236
```
