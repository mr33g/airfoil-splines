"""Enable desktop controls and translate thickness units at the UI boundary."""
import math
from gui import config


class UIStateController:
    def __init__(self, processor, window):
        self.processor = processor
        self.window = window
        self._initial_thickness_mm = 0.0

    def update_comb_labels(self):
        comb = self.window.comb_panel
        comb.comb_scale_label.setText(f"{comb.comb_scale_slider.value() / 1000:.3f}")
        comb.comb_density_label.setText(str(comb.comb_density_slider.value()))

    def update_button_states(self):
        controller = self.window.bspline_controller
        fitted = controller.bspline_processor.is_fitted()
        available = not controller.busy
        loaded = self.processor.upper_data is not None
        applied = controller.session.te_thickness is not None
        fp, opt = self.window.file_panel, self.window.optimizer_panel
        airfoil, comb = self.window.airfoil_settings_panel, self.window.comb_panel
        try:
            chord = float(airfoil.chord_length_input.text())
            thickness = float(airfoil.te_thickness_input.text())
            valid = math.isfinite(chord) and chord > 0 and math.isfinite(thickness) and thickness >= 0
            original = self._source_thickness() * chord
            changed = abs(thickness - round(original, 3)) > 1e-6
        except ValueError:
            valid = changed = False
        airfoil.toggle_thickening_button.setText("Remove" if applied else "Apply")
        airfoil.toggle_thickening_button.setEnabled(available and fitted and (applied or (valid and changed)))
        fp.load_button.setEnabled(available)
        fp.export_dxf_button.setEnabled(available and fitted)
        fp.export_bsp_button.setEnabled(available and fitted and config.ENABLE_BSP_EXPORT)
        fp.export_dat_button.setEnabled(available and fitted and config.ENABLE_DAT_EXPORT)
        opt.fit_bspline_button.setEnabled(available and loaded)
        opt.upper_insert_btn.setEnabled(available and fitted)
        opt.lower_insert_btn.setEnabled(available and fitted)
        comb.comb_scale_slider.setEnabled(available and fitted)
        comb.comb_density_slider.setEnabled(available and fitted)

    def handle_comb_params_changed(self):
        self.update_comb_labels()
        controller = self.window.bspline_controller
        if controller.bspline_processor.is_fitted() and not controller.busy:
            controller._update_plot_with_bsplines()

    def handle_toggle_thickening(self):
        controller = self.window.bspline_controller
        if controller.session.te_thickness is not None:
            controller.remove_te_thickening()
            return
        panel = self.window.airfoil_settings_panel
        try:
            chord = float(panel.chord_length_input.text())
            thickness = float(panel.te_thickness_input.text())
            if not math.isfinite(chord) or chord <= 0 or not math.isfinite(thickness) or thickness < 0:
                raise ValueError()
            controller.apply_te_thickening(thickness / chord * 100)
        except ValueError:
            self.processor.log_message.emit("Enter a positive chord length and a nonnegative finite TE thickness.")

    def reset_ui_for_new_airfoil(self):
        self.window.bspline_controller.reset()
        self._calculate_initial_thickness()
        opt = self.window.optimizer_panel
        opt.upper_cp_label.setText("Upper CPs: -")
        opt.lower_cp_label.setText("Lower CPs: -")
        opt.fit_bspline_button.setText("Fit B-spline")
        self.processor.emit_plot_update()
        self.update_comb_labels()
        self.update_button_states()

    def _source_thickness(self):
        if self.processor.upper_data is None or self.processor.lower_data is None:
            return 0.0
        return abs(float(self.processor.upper_data[-1, 1] - self.processor.lower_data[-1, 1]))

    def _calculate_initial_thickness(self):
        panel = self.window.airfoil_settings_panel
        try:
            chord = float(panel.chord_length_input.text())
            if not math.isfinite(chord) or chord <= 0:
                return
        except ValueError:
            return
        self._initial_thickness_mm = round(self._source_thickness() * chord, 3)
        panel.te_thickness_input.setText(f"{self._initial_thickness_mm:.3f}")

    def handle_chord_changed(self):
        controller = self.window.bspline_controller
        if controller.session.te_thickness is None:
            self._calculate_initial_thickness()
        else:
            panel = self.window.airfoil_settings_panel
            try:
                chord = float(panel.chord_length_input.text())
                if math.isfinite(chord) and chord > 0:
                    panel.te_thickness_input.setText(f"{controller.session.te_thickness * chord:.3f}")
            except ValueError:
                pass
        if controller.bspline_processor.is_fitted() and not controller.busy:
            controller._update_plot_with_bsplines()
        self.update_button_states()

    def handle_thickness_input_changed(self):
        self.update_button_states()
