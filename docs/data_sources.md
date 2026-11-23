# Data-source labels

Every chart and table states where its numbers came from. The labels are worked out from the data at run time, so they change by themselves when a series' origin changes. Code: `src/provenance.py`. Settings: `config/providers.json`.

## Where the labels appear

| Place | Label |
|---|---|
| Under every chart | `Source: …` built from the series plotted. Lines calculated on the page (ratios, averages) are attributed to the page's inputs, never to a guessed provider. |
| Workbook tables | `Source: …` beside the sheet and as-of date |
| Indicator tables | `Source` column (live provider) plus `Link` |
| Signal boards and checklists | `FRED: ID` in a rule's source is replaced by the provider the data actually came from |
| Methodology & sources | `Data source` column |

## How each label is decided

| Data | Label comes from | Example |
|---|---|---|
| Downloaded series (FRED and any future site) | The URL stored with the observations. Known domains map to names in `providers.json`. Unknown sites show their host name. | `FRED (HOUST1F (producer: Census Bureau/HUD))` |
| Sponsor workbook values | How the saved cell was produced, traced back through its formulas when the workbook is imported. A Bloomberg function upstream (`BDH`, `BDP`, `BDS`, `BQL`…), or a cell inside a Bloomberg array, means Bloomberg, with ticker and field. A typed number means manual input. A formula with neither means a workbook calculation. | `Bloomberg (HOMECOMP Index PX_LAST) via PCM - Monthly Market & Risk Monitor`, `PCM - Monthly Market & Risk Monitor (manual input)` |

Many workbook series are mixed: history pasted in by hand, plus the latest value from a Bloomberg formula (for example S&P Relative). The label lists both. When the sponsors replace pasted history with a Bloomberg formula, the next import relabels the series as Bloomberg. No code change is needed.

## Moving a series from FRED to Bloomberg

When the sponsors add a Bloomberg series to the workbook that measures the same thing as an independent download (for example the 10-year Treasury yield, `USGG10YR Index` vs FRED `DGS10`):

1. Map the new workbook range in `config/excel_mapping.json`, as for any workbook chart.
2. Declare the pair in `config/providers.json`. Check first that the two have the same units and frequency:

   ```json
   "equivalents": {
     "DGS10": {"section": "Market Data", "series": "<mapped series id>"}
   }
   ```

Every page that uses `DGS10` then uses the workbook series wherever its provider ranks higher in `preference` (`["Bloomberg", "FRED"]`), and labels it Bloomberg. A manual-input workbook series never outranks a download. Without a declared pair, workbook and downloaded series are never swapped.

## Adding another site

Add the provider and its domains under `providers` in `config/providers.json`. Downloads from those domains are then labelled with that name. Until then they still show the site's host name.

## Limits

- Tracing samples a few cells per series and follows up to 8 formula levels. Defined names, whole-column references and links to other workbooks are not followed.
- A tracing problem never blocks an import; that series is labelled `PCM - Monthly Market & Risk Monitor`.
- Snapshots imported before labels existed show `PCM - Monthly Market & Risk Monitor`. A snapshot format version makes the next run re-import the unchanged workbook once, which adds the labels.
