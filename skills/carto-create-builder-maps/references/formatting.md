<!-- Number formats for widgets, popup fields and table widget columns. Presets from workspace-www/src/features/builder/utils/fieldFormatters.ts. -->

# Number formats

Use this guide before setting a number format on a widget, a popup field or a table widget column.

## 1. Same decision, two ways to write it

- Formula, category, histogram, range and time series widgets take a preset id in `formatter` (and `xAxisFormatter` on a histogram).
- Popup fields and table widget columns take a d3 format code in `format`.

Never swap them: a preset id in a `format` field breaks the table or popup, and a d3 code in `formatter` is not a preset.

## 2. Pick by what the number is

| The number is | Widget preset | Popup or table code | Shows |
| --- | --- | --- | --- |
| A large count or total | `DECIMAL_SHORT_COMMA` | `.3~s` | 12.3k |
| An exact integer | `DECIMAL_ZERO` | `,.0f` | 12,345,678 |
| A rate or average | `DECIMAL_DECIMAL_FIXED_2` | `.2f` | 1.23 |
| A share from 0 to 1 | `DECIMAL_PERCENT_FULL_1` | `.1%` | 0.012 → 1.2% |
| A change with sign | `DECIMAL_DELTA` | `+,.3f` | +12,345.432 |
| Dollars | `DECIMAL_CURRENCY` | `$,.2f` | $12,345.43 |
| Already a code or a year | `NONE` | leave `format` out | 2023 |

## 3. Rules

- Percent formats multiply by 100. Use them only on 0 to 1 values. For a column already in 0 to 100, use a number format and put "%" in the title or label.
- `DECIMAL_CURRENCY` and `$` always print dollars. For any other currency, use a number format and put the unit in the title or label: "Revenue (EUR)".
- Don't format identifiers, years or postal codes as numbers: `,.0f` turns 2023 into 2,023.
- Use the same format for the same measure everywhere on the map, so a widget and a popup show the same value the same way.
