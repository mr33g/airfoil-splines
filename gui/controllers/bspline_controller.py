"""Translate desktop actions into isolated AirfoilFit session operations."""
from copy import deepcopy
from PySide6.QtCore import QObject
from gui import config
from gui.fit_session import FitSession
from gui.workers.bspline_worker import BSplineWorker


class BSplineController(QObject):
    def __init__(self, processor, window):
        super().__init__(window)
        self.processor = processor
        self.window = window
        self.session = FitSession(config.DEFAULT_BSPLINE_DEGREE)
        self._current_worker = None
        self._sync_model()

    @property
    def bspline_processor(self):
        return self.session.model

    @property
    def busy(self):
        return self._current_worker is not None

    def _sync_model(self):
        self.window.bspline_processor = self.session.model
        self.processor.display_te_thickness = self.session.te_thickness

    def reset(self):
        self.session = FitSession(self.window.optimizer_panel.bspline_degree_spin.value())
        self.processor.error_metrics = {}
        self._sync_model()

    def refit_if_fitted(self):
        if self.bspline_processor.is_fitted():
            self._fit(preserve_counts=True, preserve_knots=True)

    def refit_smoothing_full(self):
        if self.bspline_processor.is_fitted():
            self._fit(preserve_counts=True, preserve_knots=False)

    def fit_bspline(self):
        self._fit(preserve_counts=False, preserve_knots=False)

    def _fit(self, *, preserve_counts, preserve_knots):
        opt = self.window.optimizer_panel
        degree = opt.bspline_degree_spin.value()
        initial = opt.initial_cp_spin.value()
        counts = (initial, initial)
        if preserve_counts:
            counts = (max(degree + 1, self.bspline_processor.num_cp_upper),
                      max(degree + 1, self.bspline_processor.num_cp_lower))
        continuity = 3 if opt.g3_checkbox.isChecked() else 2 if opt.g2_checkbox.isChecked() else 1
        smoothing = opt.smoothness_penalty_value()
        source = self.processor.source
        self._start("Fitting B-spline", lambda session: session.fit(
            source, degree=degree, counts=counts, continuity=continuity,
            smoothing=smoothing, preserve_knots=preserve_knots))

    def insert_knot(self, surface):
        self._start("Inserting knot", lambda session: session.insert(surface))

    def apply_te_thickening(self, te_thickness_percent):
        source = self.processor.source
        return self._start("Applying TE thickness", lambda session: session.thicken(source, te_thickness_percent / 100.0))

    def remove_te_thickening(self):
        source = self.processor.source
        return self._start("Removing TE thickness", lambda session: session.thicken(source, None))

    def _start(self, label, operation):
        if self.busy:
            self.window.status_log.append("A fitting operation is already running.")
            return False
        if self.processor.upper_data is None:
            self.window.status_log.append("Load airfoil data first.")
            return False
        self._current_worker = BSplineWorker(deepcopy(self.session), operation, self)
        self._current_worker.finished.connect(self._on_finished)
        self.window.status_log.start_spinner(label)
        self._set_buttons_enabled(False)
        self._current_worker.start()
        return True

    def _on_finished(self):
        worker = self._current_worker
        self._current_worker = None
        self.window.status_log.stop_spinner()
        self.window.status_log.append(worker.message)
        try:
            if worker.success:
                self.session = worker.session
                self._sync_model()
                self._update_final_error_metrics()
                self._update_fit_button_text()
                self._update_plot_with_bsplines()
                if self.session.te_thickness is None:
                    self.window.controller.ui_state_controller._calculate_initial_thickness()
        finally:
            worker.deleteLater()
            self._set_buttons_enabled(True)

    def _set_buttons_enabled(self, enabled):
        self.window.file_panel.setEnabled(enabled)
        self.window.optimizer_panel.setEnabled(enabled)
        self.window.airfoil_settings_panel.setEnabled(enabled)
        self.window.comb_panel.setEnabled(enabled)
        if enabled:
            self.window.controller.ui_state_controller.update_button_states()

    def _update_fit_button_text(self):
        model = self.bspline_processor
        opt = self.window.optimizer_panel
        opt.upper_cp_label.setText(f"Upper CPs: {model.num_cp_upper}")
        opt.lower_cp_label.setText(f"Lower CPs: {model.num_cp_lower}")
        opt.fit_bspline_button.setText("Reset fit" if model.is_fitted() else "Fit B-spline")

    def _update_final_error_metrics(self):
        if not self.processor.error_reference_available:
            self.processor.error_metrics = {}
            return
        self.processor.error_metrics = self.session.error_metrics(self.processor.source)
        upper, lower = (self.processor.error_metrics[side] for side in ("upper", "lower"))
        self.window.status_log.append(
            f"Vertical error (% chord): max {upper['max_error'] * 100:.4f} / {lower['max_error'] * 100:.4f}; "
            f"RMS {upper['rms'] * 100:.4f} / {lower['rms'] * 100:.4f} (upper/lower).")

    def _update_plot_with_bsplines(self):
        comb = self.window.comb_panel
        comb_data = self.bspline_processor.calculate_curvature_comb_data(
            num_points_per_segment=comb.comb_density_slider.value(),
            scale_factor=comb.comb_scale_slider.value() / 1000.0)
        self.processor.emit_plot_update(bspline_processor=self.bspline_processor, comb_bspline=comb_data)
