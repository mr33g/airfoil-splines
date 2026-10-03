import unittest
from unittest.mock import patch
import numpy as np
from airfoil_splines_core import AirfoilProcessor, BSplineProcessor
from gui.fit_session import FitSession


def source_data():
    source = AirfoilProcessor(logger_func=lambda _: None)
    x = np.linspace(0, 1, 81)
    y = .12 * np.sqrt(x) * (1-x)
    source.upper_data = np.column_stack((x, y))
    source.lower_data = np.column_stack((x, -y))
    return source


class FitSessionTests(unittest.TestCase):
    def setUp(self):
        self.source = source_data()
        self.session = FitSession(4)
        self.fit()

    def fit(self, **overrides):
        params = dict(degree=4, counts=5, continuity=2, smoothing=0)
        params.update(overrides)
        return self.session.fit(self.source, **params)

    def test_shared_model_and_vertical_metrics(self):
        self.assertIs(type(self.session.model), BSplineProcessor)
        metrics = self.session.error_metrics(self.source)
        self.assertLess(metrics['upper']['max_error'], .005)
        self.assertTrue(self.session.model.enforce_g2)

    def test_insertion_changes_only_requested_surface_count(self):
        for surface in ('upper', 'lower'):
            with self.subTest(surface=surface):
                self.fit()
                other = 'lower' if surface == 'upper' else 'upper'
                knots = getattr(self.session.model, other + '_knot_vector').copy()
                self.session.insert(surface)
                self.assertEqual(getattr(self.session.model, 'num_cp_' + surface), 6)
                self.assertEqual(getattr(self.session.model, 'num_cp_' + other), 5)
                np.testing.assert_array_equal(getattr(self.session.model, other + '_knot_vector'), knots)

    def test_refit_retains_asymmetric_knots(self):
        self.session.insert('upper')
        knots = self.session.model.upper_knot_vector.copy()
        self.fit(counts=(6,5), continuity=3, preserve_knots=True)
        np.testing.assert_array_equal(self.session.model.upper_knot_vector, knots)
        self.assertTrue(self.session.model.enforce_g3)

    def test_thickening_retains_source_and_removes_cleanly(self):
        original = self.source.upper_data.copy()
        self.session.insert('upper')
        knots = self.session.model.upper_knot_vector.copy()
        self.session.thicken(self.source, .01)
        model = self.session.model
        self.assertAlmostEqual(model.upper_curve(1)[1] - model.lower_curve(1)[1], .01)
        np.testing.assert_array_equal(self.source.upper_data, original)
        np.testing.assert_array_equal(model.upper_knot_vector, knots)
        self.session.thicken(self.source, None)
        self.assertAlmostEqual(self.session.model.upper_curve(1)[1] - self.session.model.lower_curve(1)[1], 0)

    def test_failed_fit_preserves_previous_model(self):
        model = self.session.model
        with self.assertRaises(ValueError):
            self.fit(counts=2)
        self.assertIs(self.session.model, model)

    def test_failed_thickness_and_insertion_preserve_state(self):
        model = self.session.model
        with patch.object(BSplineProcessor, 'fit_bspline', side_effect=ValueError('failure')):
            with self.assertRaises(ValueError):
                self.session.thicken(self.source, .01)
        self.assertIsNone(self.session.te_thickness)
        self.assertIs(self.session.model, model)
        with patch.object(BSplineProcessor, 'insert_knot_at_max_error', return_value=False):
            with self.assertRaises(ValueError):
                self.session.insert('upper')
        self.assertIs(self.session.model, model)

    def test_invalid_thickness(self):
        for thickness in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                self.session.thicken(self.source, thickness)
