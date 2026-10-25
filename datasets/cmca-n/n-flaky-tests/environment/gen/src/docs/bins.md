# Bins and putaway

## 1. Bin codes

1.1 A bin code is an aisle letter, a two-digit bay and a one-digit level,
joined by hyphens: `C-07-2` is aisle C, bay 7, level 2. Bays start at `01`
and levels at `1` (the floor). Anything else raises `BinError`.

1.2 `parse_code` gives `(aisle, bay, level)` with aisle A as 0.

## 2. The layout

2.1 A layout is a list of bin records: `code`, `dims_mm` (inner length, width
and height in millimetres), `max_kg` (load limit in whole kilograms) and
`zones` (default `["ambient"]`).

2.2 A layout may list a bin more than once, for example once per zone it
belongs to. Records of one code are one bin: their zones are merged. Records
of one code with different sizes or load limits raise `BinError`.

2.3 An item with a `zone` may only go to bins of that zone. An item without a
zone may go to any bin.

## 3. Choosing a bin

3.1 The walking cost from the origin `putaway.origin` to a bin is

    4 x |aisle difference| + 2 x |bay difference| + 3 x (level - 1)

The origin's own level does not count.

3.2 A pallet of `qty` units fits a bin when its weight is within the load
limit, the item fits the bin in some orientation (sorted item dimensions each
at most the sorted bin dimensions), and `qty` times the item volume is at
most `putaway.max_fill` times the bin volume.

3.3 `choose_bin(item, layout, settings, qty, occupied)` returns the code of the
bin with the lowest walking cost among the bins that are allowed for the item
(2.3), not in `occupied`, and fit the pallet (3.2). When several bins have the
lowest cost, the bin with the smallest code wins, comparing codes as strings:
`A-04-1` before `B-02-1`. When no bin qualifies it raises `NoBinError`.

3.4 The result depends only on the layout's bins, the item, the quantity, the
occupied bins and the settings. The order in which the layout lists its bins
does not matter.

## 4. Putaway

4.1 `putaway(lines, catalog, layout, settings, occupied)` plans a receipt.
`lines` is a list of `(sku, qty)`. A line becomes pallets of `case_qty` units,
the last one holding what is left. Pallets are placed in receipt order, each
with `choose_bin`; a bin that receives a pallet is occupied for the pallets
after it.

4.2 The plan is a list of `(sku, qty, bin)`, one per pallet, in placement
order.
