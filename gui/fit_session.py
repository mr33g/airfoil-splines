"""Desktop fit state and operations; numerical work belongs to airfoil-splines-core."""
from copy import deepcopy
import numpy as np
from airfoil_splines_core import BSplineProcessor
from airfoil_splines_core.bspline_helper import apply_te_thickness_to_reference
from airfoil_splines_core.optimization import vertical_error_metrics


class FitSession:
    def __init__(self, degree):
        self.model = BSplineProcessor(degree)
        self.te_thickness = None

    def fit(self, source, *, degree, counts, continuity, smoothing, preserve_knots=False):
        candidate = BSplineProcessor(degree)
        upper, lower = source.upper_data, source.lower_data
        if upper is None or lower is None:
            raise ValueError("Load airfoil data first.")
        if self.te_thickness is not None:
            upper, lower = apply_te_thickness_to_reference(upper, lower, self.te_thickness)
        knots = None
        if preserve_knots and self.model.is_fitted():
            if (candidate.degree_upper, candidate.degree_lower) == self.model.fitted_degree:
                knots = (self.model.upper_knot_vector, self.model.lower_knot_vector)
        result = candidate.fit_bspline(
            upper, lower, counts, continuity=continuity, smoothing_weight=smoothing,
            upper_te_tangent_vector=source.upper_te_tangent_vector,
            lower_te_tangent_vector=source.lower_te_tangent_vector, knot_vectors=knots)
        if not result:
            raise ValueError(result.message)
        self.model = candidate
        return result.message

    def insert(self, surface):
        candidate = deepcopy(self.model)
        if not candidate.insert_knot_at_max_error(surface):
            raise ValueError(candidate.last_error_message or "Knot insertion failed.")
        self.model = candidate
        return f"Inserted knot on {surface} surface."

    def thicken(self, source, thickness):
        if not self.model.is_fitted():
            raise ValueError("Fit a model before changing trailing-edge thickness.")
        if thickness is not None and (not np.isfinite(thickness) or thickness < 0):
            raise ValueError("Trailing-edge thickness must be finite and nonnegative.")
        previous = self.te_thickness
        self.te_thickness = thickness
        try:
            self.fit(source, degree=self.model.fitted_degree,
                     counts=(self.model.num_cp_upper, self.model.num_cp_lower),
                     continuity=3 if self.model.enforce_g3 else 2 if self.model.enforce_g2 else 1,
                     smoothing=self.model.smoothing_weight, preserve_knots=True)
        except Exception:
            self.te_thickness = previous
            raise
        return "Trailing-edge thickness removed." if thickness is None else "Trailing-edge thickness applied."

    def error_metrics(self, source):
        upper, lower = source.error_reference_data()
        if self.te_thickness is not None:
            upper, lower = apply_te_thickness_to_reference(upper, lower, self.te_thickness)
        return {side: vertical_error_metrics(curve, data) for side, curve, data in (
            ("upper", self.model.upper_curve, upper), ("lower", self.model.lower_curve, lower))}
