# Monthly totals changed after upgrading to 2.4.0

Opened by: Hanna Lindqvist (finance operations)
Label: bug

We upgraded tally from 2.3.0 to 2.4.0 last week. Since then the March report for our ledger no
longer agrees with our books. We ran the same command with both releases on the same file
(attached as `ledger.csv`), from a checkout of each release tag:

    python -m tally report --month 2026-03 ledger.csv

With 2.3.0:

    Totals for 2026-03
    FACILITIES      9737797.03
    OPS-EAST        9797853.14
    OPS-WEST        9520134.15
    R-AND-D         9845592.45
    SALES-EU        9357861.70
    SALES-NA        9822616.26
    SUPPORT         9357144.38
    TRAVEL          9621229.77
    TOTAL          77060228.88

With 2.4.0:

    Totals for 2026-03
    FACILITIES    9,733,146.58
    OPS-EAST      9,810,599.90
    OPS-WEST      9,506,813.45
    R-AND-D       9,843,916.57
    SALES-EU      9,348,230.47
    SALES-NA      9,839,299.40
    SUPPORT       9,345,391.04
    TRAVEL        9,622,364.07
    TOTAL        77,049,761.48

The 2.3.0 figures are the ones our accountants signed off. Nothing changed on our side: same file,
same command, same machine. We did not try the releases in between.
