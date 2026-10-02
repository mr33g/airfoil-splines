import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PySide6.QtWidgets import QApplication, QFileDialog
from airfoil_fit import export_bspline_to_bsp
from airfoil_fit.data_loader import export_airfoil_to_selig_format, load_airfoil_data
from gui.main_window import MainWindow
from gui.controllers import MainController
from utils.bsp_importer import load_bspline_from_bsp
from test_fit_session import source_data


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        source = source_data()
        self.dat = self.path / "profile.dat"
        export_airfoil_to_selig_format(source.upper_data, source.lower_data, "Test foil", self.dat)
        self.window = MainWindow()
        self.controller = MainController(self.window)
        self.fit = self.controller.bspline_controller
        self.load(self.dat)

    def tearDown(self):
        self.wait()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()

    def load(self, path):
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(path), '')):
            self.controller.file_controller.load_airfoil_file()

    def wait(self):
        deadline = time.monotonic() + 60
        while self.fit.busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.005)
        self.assertFalse(self.fit.busy, "Worker did not finish")
        self.app.processEvents()

    def fitted(self):
        self.window.optimizer_panel.fit_bspline_button.click()
        self.wait()
        self.assertTrue(self.fit.bspline_processor.is_fitted())

    def test_load_fit_reset_and_one_surface_insertion(self):
        self.assertIsNotNone(self.controller.processor.upper_data)
        self.fitted()
        model = self.fit.bspline_processor
        self.assertIsNotNone(self.controller.processor._last_plot_data['comb_bspline'])
        self.window.optimizer_panel.initial_cp_spin.setValue(8)
        self.assertIs(self.fit.bspline_processor, model)
        self.assertFalse(self.fit.busy)
        self.window.optimizer_panel.upper_insert_btn.click()
        self.wait()
        self.assertEqual(self.fit.bspline_processor.num_cp_upper, model.num_cp_upper + 1)
        self.assertEqual(self.fit.bspline_processor.num_cp_lower, model.num_cp_lower)
        self.window.optimizer_panel.fit_bspline_button.click()
        self.wait()
        self.assertEqual(self.fit.bspline_processor.num_cp_upper, 8)
        self.assertEqual(self.fit.bspline_processor.num_cp_lower, 8)
        self.load(self.dat)
        self.assertFalse(self.fit.bspline_processor.is_fitted())
        self.assertFalse(self.window.file_panel.export_bsp_button.isEnabled())

    def test_thickness_controls_and_worker_isolation(self):
        self.fitted()
        model = self.fit.bspline_processor
        panel = self.window.airfoil_settings_panel
        panel.chord_length_input.setText('100')
        panel.te_thickness_input.setText('1')
        panel.toggle_thickening_button.click()
        self.assertTrue(self.fit.busy)
        self.assertIs(self.fit.bspline_processor, model)
        self.assertFalse(self.window.file_panel.isEnabled())
        self.wait()
        self.assertAlmostEqual(self.fit.bspline_processor.upper_curve(1)[1] - self.fit.bspline_processor.lower_curve(1)[1], .01)
        self.assertEqual(panel.toggle_thickening_button.text(), 'Remove')
        panel.toggle_thickening_button.click()
        self.wait()
        self.assertIsNone(self.fit.session.te_thickness)
        self.assertEqual(panel.toggle_thickening_button.text(), 'Apply')

    def test_exports_and_bsp_import_with_and_without_reference(self):
        self.fitted()
        fc = self.controller.file_controller
        for suffix, export in [('bsp', fc.export_bsp_file), ('dat', fc.export_dat_file), ('dxf', fc.export_dxf)]:
            target = self.path / ('export.' + suffix)
            with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(target), '')):
                export()
            self.assertTrue(target.is_file(), suffix)
        bsp = self.path / 'export.bsp'
        data = load_bspline_from_bsp(bsp)
        np.testing.assert_allclose(data.upper_control_points, self.fit.bspline_processor.upper_control_points)
        self.load(bsp)
        self.assertTrue(self.controller.processor.error_reference_available)
        self.assertIn('upper', self.controller.processor.error_metrics)
        (self.path / 'export.dat').unlink()
        self.load(bsp)
        self.assertFalse(self.controller.processor.error_reference_available)
        self.assertEqual(self.controller.processor.error_metrics, {})
        self.assertTrue(self.fit.bspline_processor.is_fitted())
        self.fit.insert_knot('lower')
        self.wait()
        self.assertEqual(self.fit.bspline_processor.num_cp_lower, len(data.lower_control_points) + 1)

    def test_failed_file_load_keeps_model(self):
        self.fitted()
        previous = self.fit.bspline_processor
        invalid = self.path / 'invalid.bsp'
        invalid.write_text('{}')
        self.load(invalid)
        self.assertIs(self.fit.bspline_processor, previous)
        self.assertTrue(previous.is_fitted())

    def test_invalid_chord_and_thickness_do_not_start_worker(self):
        self.fitted()
        panel = self.window.airfoil_settings_panel
        for chord, thickness in [('0', '1'), ('nan', '1'), ('100', '-1')]:
            panel.chord_length_input.setText(chord)
            panel.te_thickness_input.setText(thickness)
            self.controller.ui_state_controller.handle_toggle_thickening()
            self.assertFalse(self.fit.busy)

    def test_continuity_refit_preserves_knots_and_degree_change_is_applied(self):
        self.fitted()
        opt = self.window.optimizer_panel
        opt.upper_insert_btn.click()
        self.wait()
        knots = self.fit.bspline_processor.upper_knot_vector.copy()
        opt.g3_checkbox.setChecked(True)
        self.wait()
        self.assertTrue(self.fit.bspline_processor.enforce_g3)
        np.testing.assert_array_equal(self.fit.bspline_processor.upper_knot_vector, knots)
        opt.bspline_degree_spin.setValue(5)
        self.wait()
        self.assertEqual(self.fit.bspline_processor.fitted_degree, (5,5))
        opt.smoothness_penalty_slider.setValue(30)
        opt.smoothness_penalty_slider.sliderReleased.emit()
        self.wait()
        self.assertAlmostEqual(self.fit.bspline_processor.smoothing_weight, opt.smoothness_penalty_value())

    def test_chord_updates_applied_thickness_units(self):
        self.fitted()
        panel = self.window.airfoil_settings_panel
        panel.chord_length_input.setText('100')
        panel.te_thickness_input.setText('1')
        panel.toggle_thickening_button.click()
        self.wait()
        panel.chord_length_input.setText('200')
        panel.chord_length_input.editingFinished.emit()
        self.assertAlmostEqual(float(panel.te_thickness_input.text()), 2)
        self.assertAlmostEqual(self.fit.session.te_thickness, .01)
        payload = self.controller.processor._last_plot_data
        self.assertAlmostEqual(payload['upper_data'][-1,1] - payload['lower_data'][-1,1], .01)

    def test_failed_worker_keeps_model_and_reenables_controls(self):
        self.fitted()
        model = self.fit.bspline_processor
        def fail(session):
            raise ValueError('expected failure')
        self.fit._start('Failure test', fail)
        self.wait()
        self.assertIs(self.fit.bspline_processor, model)
        self.assertTrue(self.window.file_panel.isEnabled())
        self.assertTrue(self.window.optimizer_panel.isEnabled())


class BSPValidationTests(unittest.TestCase):
    def test_rejects_nonfinite_unsorted_and_fractional_degree(self):
        from utils.bsp_importer import _parse_surface_json
        valid = dict(px=[0,0,.5,1], py=[0,.1,.1,0], knots=[0,0,0,0,1,1,1,1], degree=3)
        for patch_data in [dict(px=[0,0,float('nan'),1]), dict(degree=3.5),
                           dict(knots=[0,0,0,0,1,.5,1,1])]:
            with self.assertRaises(ValueError):
                _parse_surface_json(valid | patch_data, surface_name='upper')
