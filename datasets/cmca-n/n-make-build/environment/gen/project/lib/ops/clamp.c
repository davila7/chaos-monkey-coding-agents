#include "qs/ops.h"

/* clamp(x, lo, hi): lo when x is below lo, hi when x is above hi, x otherwise. */
double qs_op_clamp(const double *a)
{
    if (a[0] < a[1])
        return a[1];
    if (a[0] > a[2])
        return a[2];
    return a[0];
}
