# Graphium

**Experimental data visualization and statistical analysis, built with Python 3.**

Graphium is a Streamlit application for turning spreadsheet data into research figures. It combines data import, statistical calculations, editable annotations, and figure export in a browser interface. Plotting uses Matplotlib and Seaborn; numerical and statistical analysis uses NumPy, pandas, SciPy, and statsmodels. No external API key is required.

**Repository:** [enigmaticsloth/Graphium](https://github.com/enigmaticsloth/Graphium)

## Features

- **Seven chart types:** bar, line, box, violin, scatter, pie/donut, and heatmap.
- **Grouped bar charts:** recognize timepoint headers, show individual observations, and choose SEM or SD error bars.
- **Built-in statistics:** automatic test selection or explicit Welch, Student, and paired t-tests between selected groups.
- **Multiple comparisons:** Benjamini–Hochberg FDR, Bonferroni, or no correction.
- **Editable figure settings:** axis limits, canvas width and height, axis labels, tick styling, colors, and legend placement.
- **Editable group names:** rename categories and conditions without changing the underlying observations or comparison targets.
- **Annotation controls:** show or hide all statistical annotations or specific comparisons; add manual symbols and text.
- **Exports:** PNG/TIFF at 300 DPI, plus SVG/PDF vector formats.
- **Three interface themes:** Carbon, Graphite, and Paper. Exported figures use a white background.

## Quick start

Python **3.11** is recommended and is the version used for local verification. Install Git and Python before running these commands.

```bash
git clone https://github.com/enigmaticsloth/Graphium.git
cd Graphium
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows PowerShell, create and activate the virtual environment with:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the address printed by Streamlit, normally `http://localhost:8501`. Enable **Use example data** in the sidebar to try the application with synthetic observations.

To use a different port:

```bash
python -m streamlit run app.py --server.port 8080
```

## Importing data

| Format | Extension | Reader |
| --- | --- | --- |
| Excel workbook | `.xlsx` | pandas and openpyxl |
| Legacy Excel workbook | `.xls` | pandas and xlrd |
| Comma-separated values | `.csv` | pandas |
| Tab-separated values | `.tsv` | pandas |

Choose an Excel worksheet from **Sheet** after upload. Data are processed by the running Python application. When you run it on your own computer, that application runs locally.

### One column per group

For bar, box, or violin plots, put replicate observations in columns and use the first row for group names. Example synthetic data:

```csv
Ctrl,Treatment A,Treatment B
9,14,21
10,16,24
8,15,23
11,18,26
```

Select the columns under **Data & layout → Value columns**. Flat bar charts can use separate bars with labels or a cluster with a legend.

### Grouped conditions and timepoints

Headers such as the following are recognized as categories `24h` / `48h` and conditions `ctrl` / `SB4`:

```csv
ctrl 24h,SB4 24h,Ctrl 48h,SB4 48h
27,25,55,63
33,33,58,68
32,38,60,79
30,40,64,81
```

Timepoint grouping works with or without blank separator columns. Supported suffixes include hours, days, and minutes. Condition matching ignores letter case and matches names rather than column positions.

Blank columns also separate general data blocks. A text label inside a block can supply its category name; otherwise, the default is `Block 1`, `Block 2`, and so on. Use **Data & layout → Edit display names** to edit:

- **Category name:** the x-axis category label.
- **Condition name:** the name shown in the legend and comparison controls.

For example, change `SB4` to `SB`. Display-name edits also appear in exports and statistical tables while preserving data assignments, selected comparisons, and manual-label targets.

For line and scatter plots, assign numeric X and Y columns. Scatter plots support optional grouping, linear regression, and a Pearson correlation display. Heatmaps use numeric columns, with optional row normalization and clustering.

## Statistical analysis

Statistics are available for **bar, box, and violin plots**. Open **Figure settings → Statistics** and keep **Auto-run statistics** enabled to calculate results when settings change.

### Automatic mode

Select **Test method → Automatic** to use the normality and variance checks implemented in the statistics engine.

| Data | Automatic analysis |
| --- | --- |
| Two groups following the parametric path | Student's or Welch's unpaired t-test, depending on the variance check |
| Two groups following the nonparametric path | Mann–Whitney U test |
| Three or more groups following the parametric path | One-way ANOVA plus pairwise unpaired t-tests |
| Three or more groups following the nonparametric path | Kruskal–Wallis test plus pairwise Mann–Whitney tests |

Normality checks use Shapiro–Wilk for smaller samples and D’Agostino–Pearson for samples of 50 or more. Groups with fewer than three observations cannot receive a normality test in this workflow. Automatic mode uses independent groups; choose paired t-tests explicitly for matched measurements.

For three or more groups, pairwise comparisons are calculated even when the overall test is not significant. The table reports the overall test, pairwise p-values, adjusted p-values, significance labels, and effect sizes.

### Selected t-tests

1. Select **Test method → t-test**.
2. Choose **Welch (unpaired)**, **Student (equal variance)**, or **Paired (matched rows)**.
3. Select one or more pairs under **t-test comparisons**.
4. Choose **fdr**, **bonferroni**, or **none** under **Multiple comparison correction**.

All selected t-tests are two-sided. Clearing the comparison selection runs no t-tests. Their results include the t statistic, sample counts, raw and adjusted p-values, significance, and effect size.

For paired tests, put corresponding subjects or samples in the **same source row**. Rows missing either measurement are excluded together. At least two complete pairs are required. Unpaired tests exclude missing observations independently and require at least two values in each group.

Correction applies across the comparisons included in the analysis. In selected t-test mode, that means only the selected pairs. For grouped bars, each category is analyzed and corrected separately; comparisons across different categories are not offered by the current interface.

### Statistical stars and manual labels

Under **Figure settings → Statistical stars**:

- Check **Hide all statistical stars** to hide automatic stars, `ns` labels, and comparison brackets.
- Use **Hide stars for these comparisons** to hide specific comparison annotations.
- Choose **above_bar** or **bracket** for the annotation style.
- Enable **Show non-significant (ns) on chart** to include nonsignificant comparisons.

Hiding annotations changes the figure, not the statistical calculations or correction family. Above-bar annotations share a horizontal row; separate comparisons on the same bar remain separate symbol groups.

| Label | p-value used for annotation |
| --- | --- |
| `****` | p ≤ 0.0001 |
| `***` | 0.0001 < p ≤ 0.001 |
| `**` | 0.001 < p ≤ 0.01 |
| `*` | 0.01 < p ≤ 0.05 |
| `ns` | p > 0.05 |

When a correction is applied, annotations use the adjusted p-value.

Under **Manual labels (#, †, text)**, click **Add label**, choose a target, and enter a symbol or text. Font size, vertical spacing, horizontal offset, visibility, and deletion are editable. Manual labels are independent of automatic annotations.

## Figure settings and export

### Axis limits

Open **Axis range** to set X/Y minimum and maximum values independently. Leave a field empty for automatic scaling. Category charts use plotted category positions for X limits; heatmaps use row and column positions. Pie charts have no axis-limit controls.

A manual Y maximum is respected when annotations are enabled. Content outside a manually restricted plotting area can be clipped.

### Canvas dimensions

Open **Figure size** and enter **Figure width (in)** and **Figure height (in)**. The dimensions apply to the full exported canvas for every chart type. The preview scales to the available screen width while preserving its aspect ratio.

For example, an **8 × 5 inch** figure exports as **2400 × 1500 pixels** in PNG or TIFF at 300 DPI. SVG and PDF preserve the figure's physical dimensions with vector graphics; they are not fixed-resolution raster images.

### Download and session state

Use the **PNG**, **TIFF**, **SVG**, or **PDF** buttons below the preview. Exports include the current names, styles, ranges, dimensions, and visible annotations.

Display-name edits and manual labels are stored per file and sheet in the current Streamlit session. The application does not save a project file; export figures before ending the session.

## Development

Run the test suite from the project root:

```bash
python -m unittest discover -s tests -v
```

Tests cover grouped-sheet parsing, editable names, annotation placement, axis ranges, exact export dimensions, t-test calculations, missing paired observations, multiple-comparison correction, and Streamlit interactions.

```text
Graphium/
├── app.py                  # Streamlit application
├── data_parser.py          # Data blocks, timepoints, and row alignment
├── stat_engine.py          # Automatic analysis and selected t-tests
├── plot_engine.py          # Chart rendering and figure export
├── annotation_engine.py    # Annotation spacing and collision handling
├── ui_components.py        # Themes, display names, and editing controls
├── tests/                  # Calculation, rendering, and interface tests
├── docs/introduction.md    # Project introductions in Chinese and English
├── requirements.txt        # Runtime dependencies
└── .streamlit/config.toml  # Local development configuration
```

The main dependencies are Streamlit, pandas, NumPy, Matplotlib, Seaborn, SciPy, statsmodels, openpyxl, and xlrd. Version constraints are in [requirements.txt](requirements.txt). Streamlit is constrained below 1.41 for compatibility with the current interface.

[graphium_spec.md](graphium_spec.md) contains historical design notes and planned features; this README describes the current application.

For bug reports, include the selected chart, relevant settings, and a minimal synthetic data example. Keep private experimental datasets, credentials, and generated output out of commits. For calculation changes, include a test of the statistical result as well as the interface behavior.

## License

This project is licensed under the [MIT License](LICENSE).
