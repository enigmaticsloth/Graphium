"""Transform observations without changing their source-row alignment."""

import numpy as np


class NormalizationError(ValueError):
    """The selected control cannot define a valid fold-change scale."""


def normalize_to_control(groups, control):
    """Divide every observation by the control mean, preserving NaNs and spread.

    Each call represents one category. The control mean becomes 1.0, while
    individual control observations retain their variation. Inputs are unchanged.
    """
    if control not in groups:
        raise NormalizationError(f'Control group "{control}" is missing from this category.')

    arrays = {name: np.asarray(values, dtype=float) for name, values in groups.items()}
    for name, values in arrays.items():
        if values.ndim != 1 or np.isinf(values).any():
            raise NormalizationError(f'Group "{name}" must contain finite numeric values or missing values.')

    control_values = arrays[control][~np.isnan(arrays[control])]
    if not control_values.size:
        raise NormalizationError(f'Control group "{control}" has no numeric observations.')
    with np.errstate(over='ignore', invalid='ignore'):
        baseline = control_values.mean()
    if not np.isfinite(baseline) or baseline == 0:
        raise NormalizationError(f'Control group "{control}" must have a finite, non-zero mean.')

    normalized = {}
    for name, values in arrays.items():
        with np.errstate(over='ignore', invalid='ignore'):
            scaled = values / baseline
        if np.isinf(scaled).any():
            raise NormalizationError(f'Fold change for "{name}" exceeds the numeric range.')
        normalized[name] = scaled.tolist()
    return normalized
