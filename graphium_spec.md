# Graphium — Technical Specification

> Historical design notes. Some planned features and interface details below differ
> from the current application. See [README.md](README.md) for supported features,
> installation instructions, and the current statistics workflow.

*From Latin graphium (γραφεῖον): a stylus for inscription on waxen tablets.*

A web-based application for experimental data visualization and statistical figure generation.

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────┐
│           Streamlit Web UI (Dark Theme)           │
│  ┌────────────┐ ┌──────────┐ ┌─────────────────┐ │
│  │  Sidebar:   │ │  Chart   │ │  Settings Panel │ │
│  │  Data Import│ │  Preview │ │  + Stats Config │ │
│  └─────┬──────┘ └────┬─────┘ └───────┬─────────┘ │
└────────┼──────────────┼───────────────┼───────────┘
         │              │               │
┌────────▼──────────────▼───────────────▼───────────┐
│               Core Engine (Python)                 │
│  ┌───────────┐ ┌────────────┐ ┌──────────────────┐│
│  │  pandas   │ │ StatEngine │ │   PlotEngine     ││
│  │  + openpyxl│ │ (scipy +   │ │  (matplotlib +   ││
│  │           │ │ statsmodels)│ │   seaborn)       ││
│  └───────────┘ └────────────┘ └──────────────────┘│
└────────────────────────────────────────────────────┘
```

**Tech stack:**

- Web UI: Streamlit (dark theme, Monet "Nymphéas" color palette)
- Data: pandas + openpyxl
- Stats: scipy.stats + statsmodels
- Plotting: matplotlib + seaborn
- Deployment: Open-source web app, sharable via `streamlit run`

---

## 2. Chart Types

### 2.1 Line Chart
- Mean ± SEM/SD connected by lines
- Individual data points overlaid (jittered scatter)
- Multiple groups with distinct markers (●○■□▲△)
- Configurable X-axis intervals
- Smart legend placement (quadrant scanning)

### 2.2 Bar Chart
- **Simple**: single group comparison
- **Grouped**: multiple groups side-by-side, configurable gap (default: zero-gap)
- Individual data points overlaid (hollow circles with black edge)
- Error bars: SEM or SD (user selectable)
- Statistical annotations: above_bar or bracket style

### 2.3 Pie Chart
- Percentage labels
- Exploded slices for emphasis
- Donut variant

### 2.4 Box Plot
- Median line, Q1-Q3 box, whiskers
- Individual data points overlaid
- Notched variant (optional)
- Bracket annotations with auto-stacking

### 2.5 Violin Plot
- Kernel density estimation
- Median line display
- Individual data points overlaid
- Bracket annotations with auto-stacking

### 2.6 Scatter Plot
- X-Y data with optional regression line
- Pearson/Spearman correlation coefficient display
- Color-coded groups

### 2.7 Heatmap
- Multiple color maps: RdBu_r, viridis, coolwarm, YlOrRd, Blues
- Row/column clustering (hierarchical)
- Cell value annotations
- Z-score normalization option

---

## 3. Statistics Engine

### 3.1 Auto-Detection Pipeline

```
Data Input (2+ groups)
    │
    ▼
Shapiro-Wilk Normality Test (per group)
    │
    ├─ All groups normal (p > 0.05) ──► Parametric path
    │                                      │
    │                    ┌─────────────────┼───────────────┐
    │                    │                 │               │
    │               2 groups          3+ groups       2 factors
    │                    │                 │               │
    │           Student's t-test   One-way ANOVA    Two-way ANOVA
    │              (unpaired)       + pairwise        + post-hoc
    │
    └─ Any group non-normal ────────► Non-parametric path
                                         │
                           ┌─────────────┼──────────────┐
                           │             │              │
                      2 groups      3+ groups      Correlation
                           │             │              │
                    Mann-Whitney U  Kruskal-Wallis  Spearman
                                   + pairwise
```

### 3.2 Key Behavior
- **3+ groups**: Pairwise comparisons always run regardless of omnibus test significance
  - If omnibus p < α: marked as significant post-hoc
  - If omnibus p ≥ α: pairwise computed for reference (marked 'ns')
- **2 groups**: Direct t-test or Mann-Whitney U (no omnibus gate)
- **Multiple comparison correction**: Bonferroni or Benjamini-Hochberg FDR (user selectable)

### 3.3 Implemented Tests

| Category | Test | Implementation |
|----------|------|---------------|
| Parametric | Unpaired t-test | `scipy.stats.ttest_ind` |
| Parametric | One-way ANOVA | `scipy.stats.f_oneway` |
| Parametric | Two-way ANOVA | `statsmodels.stats.anova.anova_lm` |
| Non-parametric | Mann-Whitney U | `scipy.stats.mannwhitneyu` |
| Non-parametric | Kruskal-Wallis | `scipy.stats.kruskal` |
| Correction | Bonferroni | Manual p-value adjustment |
| Correction | Benjamini-Hochberg FDR | Rank-based adjustment |

### 3.4 Effect Sizes
- **Cohen's d**: parametric (t-test)
- **Rank-biserial r**: non-parametric (Mann-Whitney)

### 3.5 Significance Thresholds
```
ns    p > 0.05
*     p ≤ 0.05
**    p ≤ 0.01
***   p ≤ 0.001
****  p ≤ 0.0001
```

### 3.6 Annotation System
1. Run normality test → choose parametric/non-parametric
2. Run main test (t-test / ANOVA / Kruskal-Wallis)
3. Run pairwise comparisons (always, even when omnibus not significant)
4. Apply multiple comparison correction (FDR or Bonferroni)
5. Place significance markers on chart:
   - **above_bar**: star text above individual bars
   - **bracket**: connecting line between two compared bars, auto-stacked to avoid overlap
6. **Selective display**: user can choose which specific pairs to annotate
7. **ns toggle**: option to show or hide non-significant markers

---

## 4. Web UI Design

### 4.1 Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ✒️ Graphium                                    Dark Theme   │
├──────────────┬──────────────────────────┬───────────────────┤
│   SIDEBAR    │                          │   SETTINGS        │
│              │                          │                   │
│ 📁 Upload    │     📈 Preview           │ Data columns ▼    │
│ [Excel/CSV]  │   ┌──────────────────┐   │ Color palette ▼   │
│              │   │                  │   │ ☑ Show points     │
│ Sheet: ▼     │   │  [Live Chart]   │   │ Error: ● SEM ○ SD │
│              │   │                  │   │ Bar gap: ═══○═══  │
│ ┌──────────┐ │   │                  │   │                   │
│ │ Data     │ │   └──────────────────┘   │ ─── Statistics ── │
│ │ Preview  │ │                          │ ☑ Auto-run stats  │
│ │ (10 rows)│ │   📊 Statistics          │ Correction: ▼     │
│ └──────────┘ │   ┌──────────────────┐   │ Style: ● above    │
│              │   │ Test: ANOVA      │   │        ○ bracket  │
│              │   │ F=12.3, p=0.001  │   │ ☐ Show ns         │
│              │   │                  │   │                   │
│              │   │ Post-hoc table   │   │ Comparisons: ▼    │
│              │   │ A vs B: * p=.003 │   │ [multiselect]     │
│              │   └──────────────────┘   │                   │
│              │                          │ Y-label: ______   │
│              │   [PNG][TIFF][SVG][PDF]  │                   │
├──────────────┴──────────────────────────┴───────────────────┤
│  Graphium v1.0 · Publication-quality figures                 │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Sidebar — Data Import
- Excel (.xlsx, .xls) and CSV/TSV file upload
- Sheet selector for multi-sheet workbooks
- Auto-numeric coercion: mixed string/numeric columns converted via `pd.to_numeric(errors='coerce')`
- Data preview table (first 10 rows)

### 4.3 Main Area — Chart Preview
- Live matplotlib rendering via `st.pyplot()`
- Chart type selector (horizontal radio): Bar, Line, Box, Violin, Scatter, Pie, Heatmap
- Export buttons: PNG, TIFF, SVG, PDF (all 300 DPI)

### 4.4 Settings Panel — Configuration
- Column selection (multiselect for value columns)
- Color palette presets + custom hex input
- Individual data points toggle
- Error bar type (SEM / SD)
- Bar gap slider (0.0–0.5)
- Statistics auto-run toggle
- Annotation style selection
- **Selective comparisons**: multiselect of all possible pairwise pairs
- Axis labels

### 4.5 Stats Results Display
- Test name and rationale with color-coded box
- Test statistic, p-value, parametric/non-parametric indicator
- Normality test details (expandable)
- Post-hoc pairwise comparison table with raw p, adjusted p, significance stars, effect size

---

## 5. Smart Layout Features

### 5.1 Legend Placement
- **With annotations**: legend placed outside axes (right side, `bbox_to_anchor`) to avoid overlapping bars/stars/brackets
- **Without annotations**: smart quadrant scanning — placed in the quadrant with fewest data points

### 5.2 Auto Y-limit Expansion
- Dynamically expands y-axis upper limit to fit annotations
- Accounts for error bars, data points, and bracket heights

### 5.3 Bracket Stacking
- Multiple bracket annotations auto-stack vertically with incremental offset (`running_y_offset`)
- Prevents overlapping brackets when multiple comparisons are shown

---

## 6. Export Options

| Format | DPI | Use case |
|--------|-----|----------|
| PNG | 300 | Presentations, posters |
| TIFF | 300 | Journal submission |
| SVG | Vector | Illustrator/Inkscape editing |
| PDF | Vector | Figures in LaTeX/Word |

---

## 7. Color Palettes

| Palette | Description |
|---------|-------------|
| Grayscale | Print journals (5 shades) |
| Nature | Nature journal standard (#E64B35, #4DBBD5, ...) |
| Viridis | Perceptually uniform, colorblind-safe |
| Paired | Grouped comparisons (12 colors) |
| Pastel | Soft tones for presentations |
| Bold | High-contrast for posters |
| Custom | User-defined hex codes (comma-separated) |

---

## 8. Dark Theme

Monet "Nymphéas" inspired palette:

| Element | Color |
|---------|-------|
| Background | `#1a1a2e` |
| Card/Panel | `#16213e` |
| Primary accent | `#b07ee8` (wisteria) |
| Secondary accent | `#e87a90` (coral) |
| Success | `#56d4a5` (jade) |
| Info | `#4ec5d4` (teal) |
| Chart accent | `#64a8e8` (sky) |
| Warning | `#e8c94a` (amber) |
| Subtle | `#d4a5d0` (lily) |

---

## 9. Project Structure

```
graphium/
├── app.py              # Streamlit web application (entry point)
├── stat_engine.py      # Statistics engine (auto-detect + pairwise)
├── plot_engine.py      # Chart rendering (7 types + smart layout)
├── requirements.txt    # Python dependencies (Python 3.8+)
└── README.md           # Setup & usage instructions
```

---

## 10. Compatibility

- **Python**: 3.8+ (tested on 3.8, compatible with 3.9–3.12)
- **Streamlit**: ≥1.28.0, <1.41.0 (Python 3.8 compatibility)
- **OS**: macOS, Linux, Windows
- **Browser**: Any modern browser (Chrome, Firefox, Safari, Edge)

---

## 11. Key Design Decisions

**Why Streamlit over PyQt6?**
Open-source sharing with collaborators. No installation beyond `pip install`. Accessible via browser on any machine. Ideal for research teams.

**Why auto-detect stats method?**
Most biology students pick the wrong test. Auto-detection with clear explanation ("Chose Mann-Whitney because Group B failed Shapiro-Wilk, p=0.02") teaches correct practice while preventing errors.

**Why always run pairwise (even when omnibus not significant)?**
Users expect to see annotations. When ANOVA p > 0.05, pairwise results are computed and marked 'ns', giving the user full visibility instead of silent failure.

**Why both annotation styles?**
Some journals prefer above-bar stars (compact), others require brackets (explicit comparison). User picks per chart.

**Why legend outside with annotations?**
Prevents the #1 visual issue in scientific figures: legend overlapping bars, error bars, or significance markers. When no annotations are present, legend returns to inside placement in the emptiest quadrant.

**Why zero-gap bars by default?**
Prism cannot set inter-bar gap to zero. Many PIs require grouped bars to touch. Graphium defaults to zero gap with a slider for adjustment.
