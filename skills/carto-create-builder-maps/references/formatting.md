<!-- Number formats for widgets, popup fields and table widget columns. Presets from workspace-www/src/features/builder/utils/fieldFormatters.ts. -->

# Number formats

Use this guide before setting a format on a widget, a popup field or a table widget column.

## 1. Two ways to write the same choice

- Formula, category, histogram, range and time series widgets take a preset id in `formatter` (and `xAxisFormatter` on a histogram).
- Popup fields and table widget columns take a code in `format`. Builder first matches the code against the presets' codes in the table below and, if it matches, behaves like that preset. Otherwise a number column reads it as a d3 code and a date column as a date pattern.

A preset id in `format` matches nothing and the value shows unformatted; a code in `formatter` is not a preset id. Don't swap them.

## 2. Pick by what the value is

| The value is | Widget preset | Popup or table code | Shows |
| --- | --- | --- | --- |
| A large count or total | `DECIMAL_SHORT_COMMA` | `.3~s` | 12.3k |
| An exact integer | `DECIMAL_ZERO` | `,.0f` | 12,345,678 |
| A rate or average | `DECIMAL_DECIMAL_FIXED_2` | `.2f` | 1.23 |
| A share from 0 to 1 | `DECIMAL_PERCENT_FULL_1` | `.1%` | 0.012 → 1.2% |
| A percentage already from 0 to 100 | `DECIMAL_PRECENT_REGULAR` (spelled so) | `~%` | 12.345 → 12.35% |
| A change with sign | `DECIMAL_DELTA` | `+,.3f` | +12,345.432 |
| Dollars | `DECIMAL_CURRENCY` | `$,.2f` | $12,345.43 |
| True or false | `BOOLEAN_Y_N` or `BOOLEAN_NUM` | `yn` or `01` | yes / no, 1 / 0 |
| A code, id or year | `NONE` | leave `format` out | 2023 |

Variants when you need a different precision: `DECIMAL_SHORT` (`.1s`, 10k), `DECIMAL_PERCENT_FULL_2` (`.2%`), `DECIMAL_DECIMAL_FIXED_3` (`.3f`), `DECIMAL_THREE` (`,.3f`), `DECIMAL_INT` (`.4~r`, rounds to 4 significant digits).

Dates in popups and tables take a date pattern on a date or timestamp column: `LL` (October 20, 2026), `L` (10/20/2026), `LLL` (with time). Builder's own picker doesn't offer them, so use them only when the user asks for a date format.

## 3. Rules

- `.1%` and `.2%` multiply by 100: use them only on 0 to 1 values. For values already from 0 to 100, use the 0 to 100 row: in popups and tables `~%` adds the sign without multiplying.
- `DECIMAL_CURRENCY` and `$` always print dollars. For any other currency, use a number format and put the unit in the title or label: "Revenue (EUR)".
- Don't format ids, years or postal codes as numbers: `,.0f` turns 2023 into 2,023.
- Use the same format for the same measure everywhere on the map, so a widget and a popup show the value the same way.
