"""
Graphium — Statistics Engine
Auto-detection pipeline: normality → parametric/non-parametric → post-hoc → correction
"""

import numpy as np
import pandas as pd
from scipy import stats
from dataclasses import dataclass, field
from typing import Optional
import warnings

warnings.filterwarnings('ignore')

# ── Significance thresholds ──────────────────────────────────
SIG_THRESHOLDS = [
    (0.0001, '****'),
    (0.001,  '***'),
    (0.01,   '**'),
    (0.05,   '*'),
    (1.0,    'ns'),
]

def p_to_stars(p: float) -> str:
    for threshold, label in SIG_THRESHOLDS:
        if p <= threshold:
            return label
    return 'ns'


@dataclass
class PairwiseResult:
    group1: str
    group2: str
    p_value: float
    p_adjusted: float
    stars: str
    test_name: str
    statistic: float = 0.0
    effect_size: float = 0.0
    effect_label: str = "Cohen's d"
    n1: Optional[int] = None
    n2: Optional[int] = None


@dataclass
class StatResult:
    """Complete result from the auto-detection pipeline."""
    test_name: str
    statistic: Optional[float]
    p_value: Optional[float]
    is_parametric: bool
    normality_results: dict = field(default_factory=dict)  # {group: (W, p)}
    variance_test: Optional[tuple] = None  # (stat, p)
    pairwise: list = field(default_factory=list)  # list of PairwiseResult
    correction_method: str = 'none'
    rationale: str = ''  # Human-readable explanation
    pairwise_only: bool = False


# ── Normality Tests ──────────────────────────────────────────

def test_normality(data: np.ndarray, alpha=0.05) -> tuple:
    """Shapiro-Wilk (n<50) or D'Agostino-Pearson (n≥50). Returns (stat, p, is_normal)."""
    if len(data) < 3:
        return (np.nan, 1.0, True)  # Too few samples, assume normal
    if len(data) < 8:
        # Shapiro-Wilk needs at least 3, but is unreliable below 8
        w, p = stats.shapiro(data)
        return (w, p, p > alpha)
    if len(data) < 50:
        w, p = stats.shapiro(data)
    else:
        w, p = stats.normaltest(data)  # D'Agostino-Pearson
    return (w, p, p > alpha)


def test_variance_homogeneity(*groups, alpha=0.05) -> tuple:
    """Levene's test. Returns (stat, p, is_homogeneous)."""
    if any(len(g) < 2 for g in groups):
        return (np.nan, 1.0, True)
    stat, p = stats.levene(*groups)
    return (stat, p, p > alpha)


# ── Effect Size ──────────────────────────────────────────────

def cohens_d(g1, g2):
    """Cohen's d for two groups."""
    n1, n2 = len(g1), len(g2)
    pooled_std = np.sqrt(((n1 - 1) * np.std(g1, ddof=1)**2 + (n2 - 1) * np.std(g2, ddof=1)**2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(g1) - np.mean(g2)) / pooled_std


def rank_biserial(g1, g2):
    """Rank-biserial correlation (effect size for Mann-Whitney)."""
    try:
        u_stat, _ = stats.mannwhitneyu(g1, g2, alternative='two-sided')
        n1, n2 = len(g1), len(g2)
        return 1 - (2 * u_stat) / (n1 * n2)
    except:
        return 0.0


# ── Multiple Comparison Corrections ─────────────────────────

def bonferroni(p_values):
    """Bonferroni correction."""
    n = len(p_values)
    return [min(p * n, 1.0) for p in p_values]


def benjamini_hochberg(p_values):
    """Benjamini-Hochberg FDR correction."""
    from statsmodels.stats.multitest import multipletests

    if len(p_values) == 0:
        return []
    return multipletests(p_values, method='fdr_bh')[1].tolist()


# ── Main Auto-Detection Pipeline ────────────────────────────

def auto_analyze(groups_dict: dict, paired=False, correction='fdr',
                 control_group=None, alpha=0.05) -> StatResult:
    """
    Fully automatic statistical analysis.

    Parameters:
        groups_dict: {'Ctrl': [1.0, 1.1, ...], 'TGFb1': [3.2, 2.8, ...]}
        paired: whether measurements are paired
        correction: 'bonferroni', 'fdr', or 'none'
        control_group: if set, only compare all others vs this group (Dunnett-like)
        alpha: significance level

    Returns:
        StatResult with full details.
    """
    group_names = list(groups_dict.keys())
    group_data = [np.array(groups_dict[g], dtype=float) for g in group_names]
    n_groups = len(group_names)

    # ── Step 1: Normality ────────────────────────────────
    normality = {}
    all_normal = True
    rationale_parts = []

    for name, data in zip(group_names, group_data):
        w, p, is_normal = test_normality(data)
        normality[name] = (w, p)
        if not is_normal:
            all_normal = False
            rationale_parts.append(f"'{name}' failed normality (Shapiro-Wilk p={p:.3f})")

    if all_normal:
        rationale_parts.append("All groups passed normality test")

    # ── Step 2: Choose test ──────────────────────────────
    if n_groups == 1:
        # One-sample — not common, but handle it
        t, p = stats.ttest_1samp(group_data[0], 0)
        return StatResult(
            test_name='One-sample t-test',
            statistic=t, p_value=p,
            is_parametric=True,
            normality_results=normality,
            rationale='Single group tested against zero.'
        )

    elif n_groups == 2:
        g1, g2 = group_data
        if all_normal:
            # Check variance homogeneity
            lev_stat, lev_p, homogeneous = test_variance_homogeneity(g1, g2)
            if paired:
                t, p = stats.ttest_rel(g1, g2)
                test_name = 'Paired t-test'
                rationale_parts.append("Paired design → paired t-test")
            elif homogeneous:
                t, p = stats.ttest_ind(g1, g2)
                test_name = "Student's t-test (unpaired)"
                rationale_parts.append(f"Equal variance (Levene's p={lev_p:.3f}) → Student's t")
            else:
                t, p = stats.ttest_ind(g1, g2, equal_var=False)
                test_name = "Welch's t-test"
                rationale_parts.append(f"Unequal variance (Levene's p={lev_p:.3f}) → Welch's t")

            d = cohens_d(g1, g2)
            pw = PairwiseResult(
                group1=group_names[0], group2=group_names[1],
                p_value=p, p_adjusted=p, stars=p_to_stars(p),
                test_name=test_name, statistic=t,
                effect_size=d, effect_label="Cohen's d"
            )
            return StatResult(
                test_name=test_name, statistic=t, p_value=p,
                is_parametric=True, normality_results=normality,
                variance_test=(lev_stat, lev_p) if not paired else None,
                pairwise=[pw],
                rationale=' → '.join(rationale_parts)
            )
        else:
            # Non-parametric
            if paired:
                t, p = stats.wilcoxon(g1, g2)
                test_name = 'Wilcoxon signed-rank test'
            else:
                t, p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
                test_name = 'Mann-Whitney U test'

            r = rank_biserial(g1, g2)
            pw = PairwiseResult(
                group1=group_names[0], group2=group_names[1],
                p_value=p, p_adjusted=p, stars=p_to_stars(p),
                test_name=test_name, statistic=t,
                effect_size=r, effect_label='Rank-biserial r'
            )
            rationale_parts.append(f"→ {'Wilcoxon' if paired else 'Mann-Whitney U'}")
            return StatResult(
                test_name=test_name, statistic=t, p_value=p,
                is_parametric=False, normality_results=normality,
                pairwise=[pw],
                rationale=' → '.join(rationale_parts)
            )

    else:
        # ── 3+ groups ───────────────────────────────────
        if all_normal:
            f_stat, p = stats.f_oneway(*group_data)
            test_name = 'One-way ANOVA'
            rationale_parts.append("3+ groups, all normal → one-way ANOVA")
        else:
            f_stat, p = stats.kruskal(*group_data)
            test_name = 'Kruskal-Wallis H test'
            rationale_parts.append("3+ groups, non-normal → Kruskal-Wallis")

        result = StatResult(
            test_name=test_name, statistic=f_stat, p_value=p,
            is_parametric=all_normal, normality_results=normality,
            rationale=' → '.join(rationale_parts)
        )

        # ── Always run pairwise comparisons ───────────────
        # (Even when omnibus p > alpha, so users see 'ns' annotations)
        pairwise_results = []
        raw_p_values = []

        if control_group and control_group in group_names:
            # Compare all vs control
            ctrl_data = groups_dict[control_group]
            comparisons = [(control_group, g) for g in group_names if g != control_group]
        else:
            # All pairwise
            comparisons = []
            for i in range(n_groups):
                for j in range(i + 1, n_groups):
                    comparisons.append((group_names[i], group_names[j]))

        for g1_name, g2_name in comparisons:
            g1 = np.array(groups_dict[g1_name], dtype=float)
            g2 = np.array(groups_dict[g2_name], dtype=float)

            if all_normal:
                t, pw_p = stats.ttest_ind(g1, g2)
                eff = cohens_d(g1, g2)
                eff_label = "Cohen's d"
            else:
                t, pw_p = stats.mannwhitneyu(g1, g2, alternative='two-sided')
                eff = rank_biserial(g1, g2)
                eff_label = 'Rank-biserial r'

            raw_p_values.append(pw_p)
            pairwise_results.append(PairwiseResult(
                group1=g1_name, group2=g2_name,
                p_value=pw_p, p_adjusted=pw_p,  # updated below
                stars='', test_name='post-hoc',
                statistic=t, effect_size=eff, effect_label=eff_label
            ))

        # Apply correction
        if correction == 'bonferroni' and raw_p_values:
            adjusted = bonferroni(raw_p_values)
            result.correction_method = 'Bonferroni'
        elif correction == 'fdr' and raw_p_values:
            adjusted = benjamini_hochberg(raw_p_values)
            result.correction_method = 'Benjamini-Hochberg FDR'
        else:
            adjusted = raw_p_values
            result.correction_method = 'none'

        for i, pw in enumerate(pairwise_results):
            pw.p_adjusted = adjusted[i]
            pw.stars = p_to_stars(adjusted[i])

        result.pairwise = pairwise_results
        if p < alpha:
            result.rationale += f" → significant (p={p:.4f}) → post-hoc with {result.correction_method} correction"
        else:
            result.rationale += f" → not significant (p={p:.4f}) → pairwise computed for reference"

        return result


def pairwise_t_tests(groups_dict, comparisons, test_type='welch', correction='fdr'):
    """Run selected two-sided t-tests without automatic test substitution.

    Paired inputs retain their source-row positions, including NaNs. Missing
    observations are removed jointly for paired tests, independently otherwise.
    Corrections cover only the selected pairs in this call.
    """
    from statsmodels.stats.multitest import multipletests

    names = {'welch': "Welch's t-test", 'student': "Student's t-test",
             'paired': 'Paired t-test'}
    corrections = {'none': 'none', 'bonferroni': 'Bonferroni',
                   'fdr': 'Benjamini-Hochberg FDR'}
    if test_type not in names or correction not in corrections:
        raise ValueError('Choose a supported t-test and correction method.')
    if not comparisons:
        raise ValueError('Select at least one comparison for the t-test.')

    results, seen = [], set()
    for first, second in comparisons:
        if first == second or first not in groups_dict or second not in groups_dict:
            raise ValueError('Each comparison must contain two different available groups.')
        pair = frozenset((first, second))
        if pair in seen:
            continue
        seen.add(pair)
        a, b = (np.asarray(groups_dict[group], dtype=float) for group in (first, second))
        if a.ndim != 1 or b.ndim != 1:
            raise ValueError('Each group must be a one-dimensional list of observations.')
        if test_type == 'paired':
            if len(a) != len(b):
                raise ValueError(f'{first} vs {second}: paired tests require matching source rows.')
            valid = np.isfinite(a) & np.isfinite(b)
            a, b = a[valid], b[valid]
        else:
            a, b = a[np.isfinite(a)], b[np.isfinite(b)]
        if min(len(a), len(b)) < 2:
            requirement = 'complete pairs' if test_type == 'paired' else 'values in each group'
            raise ValueError(f'{first} vs {second}: at least two {requirement} are required.')

        if test_type == 'paired':
            statistic, p_value = stats.ttest_rel(a, b, alternative='two-sided')
            differences = a - b
            sd = differences.std(ddof=1)
            effect = differences.mean() / sd if sd > 0 else np.nan
            effect_label = "Cohen's dz"
        else:
            statistic, p_value = stats.ttest_ind(
                a, b, equal_var=test_type == 'student', alternative='two-sided')
            effect = cohens_d(a, b) if a.std(ddof=1) > 0 or b.std(ddof=1) > 0 else np.nan
            effect_label = "Cohen's d"
        if not np.isfinite(p_value):
            raise ValueError(f'{first} vs {second}: the t-test is undefined for these values '
                             '(check for samples with no variation).')
        results.append(PairwiseResult(
            group1=first, group2=second, p_value=float(p_value),
            p_adjusted=float(p_value), stars='', test_name=names[test_type],
            statistic=float(statistic), effect_size=float(effect), effect_label=effect_label,
            n1=len(a), n2=len(b)))

    raw_p = [row.p_value for row in results]
    adjusted = (raw_p if correction == 'none' else multipletests(
        raw_p, method='fdr_bh' if correction == 'fdr' else 'bonferroni')[1])
    for row, p_value in zip(results, adjusted):
        row.p_adjusted = float(p_value)
        row.stars = p_to_stars(row.p_adjusted)
    rationale = f'Two-sided t-tests for {len(results)} selected comparison(s). '
    if test_type == 'paired':
        rationale += 'Observations are paired by source row; incomplete pairs are excluded. '
    rationale += f'Correction across these selected comparisons: {corrections[correction]}.'
    return StatResult(
        test_name=names[test_type], statistic=None, p_value=None,
        is_parametric=True, pairwise=results, pairwise_only=True,
        correction_method=corrections[correction], rationale=rationale)


def auto_analyze_twoway(df: pd.DataFrame, value_col: str,
                        factor1_col: str, factor2_col: str) -> dict:
    """
    Two-way ANOVA using statsmodels.

    Returns dict with ANOVA table and simple effects.
    """
    try:
        import statsmodels.api as sm
        from statsmodels.formula.api import ols

        formula = f'Q("{value_col}") ~ C(Q("{factor1_col}")) * C(Q("{factor2_col}"))'
        model = ols(formula, data=df).fit()
        anova_table = sm.stats.anova_lm(model, typ=2)

        return {
            'test_name': 'Two-way ANOVA',
            'table': anova_table,
            'rationale': f'Two factors: {factor1_col} × {factor2_col}'
        }
    except Exception as e:
        return {'test_name': 'Two-way ANOVA', 'error': str(e)}
