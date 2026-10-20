"""Widget holding settings related to the B-spline optimiser."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QWidget,
    QSpinBox,
    QSlider,
)

from gui import config


class OptimizerSettingsWidget(QGroupBox):
    """Panel exposing parameters for the B-spline airfoil optimiser."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Optimizer Settings", parent)

        # Enforce G2 at leading edge
        self.g2_checkbox = QCheckBox("G2")
        self.g2_checkbox.setChecked(True)  # Default to enabled
        self.g2_checkbox.setToolTip(
            "G2 continuity ensures smooth curvature transition at the leading edge.\n"
            "When enabled: Both surfaces share the same leading edge radius.\n"
            "When disabled: Only G1 (tangent) continuity is enforced."
        )
        
        # Enforce G3 at leading edge
        self.g3_checkbox = QCheckBox("G3")
        self.g3_checkbox.setToolTip(
            "G3 continuity ensures smooth curvature derivative transition at the leading edge.\n"
            "When enabled: Both surfaces share the same rate of change of curvature.\n"
            "Note: G3 requires G2 to be enabled. Enabling G3 will automatically enable G2."
        )

        self.le_continuity_label = QLabel("LE Continuity:")

        # Initial control point count
        self.initial_cp_label = QLabel("Initial CP count:")
        self.initial_cp_spin = QSpinBox()
        self.initial_cp_spin.setMaximum(200)
        self.initial_cp_spin.setValue(config.DEFAULT_BSPLINE_CP)
        self.initial_cp_spin.setToolTip(
            "Initial number of control points per surface. Must be at least degree + 1."
        )

        # B-spline settings (new layout for knots)
        self.upper_cp_label = QLabel("Upper CPs: -")
        self.upper_insert_btn = QPushButton("+")
        self.upper_insert_btn.setFixedWidth(100)
        self.upper_insert_btn.setToolTip("Insert a knot on the upper surface.")

        self.lower_cp_label = QLabel("Lower CPs: -")
        self.lower_insert_btn = QPushButton("+")
        self.lower_insert_btn.setFixedWidth(100)
        self.lower_insert_btn.setToolTip("Insert a knot on the lower surface.")


        # B-spline degree setting
        self.bspline_degree_label = QLabel("Degree:")
        self.bspline_degree_spin = QSpinBox()
        self.bspline_degree_spin.setMinimum(3)
        self.bspline_degree_spin.setMaximum(12)
        self.bspline_degree_spin.setValue(config.DEFAULT_BSPLINE_DEGREE)
        self.bspline_degree_spin.setToolTip(
            "The degree of the B-spline curves. Higher degree allows for smoother curves (G3+) but may be less stable."
        )

        # Smoothness penalty setting
        self.smoothness_penalty_label = QLabel("Smoothness:")
        self.smoothness_penalty_slider = QSlider(Qt.Horizontal)
        self.smoothness_penalty_slider.setMinimum(self._smoothness_ui_min())
        self.smoothness_penalty_slider.setMaximum(self._smoothness_ui_max())
        self.smoothness_penalty_slider.setSingleStep(1)
        self.smoothness_penalty_slider.setPageStep(5)
        self.smoothness_penalty_slider.setValue(
            self._slider_from_smoothness_value(float(config.DEFAULT_SMOOTHNESS_PENALTY))
        )
        self.smoothness_penalty_slider.setToolTip(
            "Controls the tradeoff between smoothness and accuracy.\n"
            "0 disables smoothing.\n"
            "Each step represents a smoothing weight of 0.0001.\n"
            "Higher values prioritize smoothness, but may reduce accuracy."
        )
        self.smoothness_penalty_spin = QSpinBox()
        self.smoothness_penalty_spin.setRange(
            self._smoothness_ui_min(), self._smoothness_ui_max())
        self.smoothness_penalty_spin.setSingleStep(1)
        self.smoothness_penalty_spin.setMinimumWidth(100)
        self.smoothness_penalty_spin.setValue(
            self._slider_from_smoothness_value(float(config.DEFAULT_SMOOTHNESS_PENALTY))
        )
        self.smoothness_penalty_spin.setToolTip(
            "Smoothing level from 0 to 100. Each step represents 0.0001."
        )

        # Action buttons - make them more prominent
        self.fit_bspline_button = QPushButton("Fit B-spline")
        #self.fit_bspline_button.setMinimumHeight(25)  # Make button taller
        self.fit_bspline_button.setStyleSheet("font-weight: bold;")

        # --- Layout ------------------------------------------------------
        layout = QVBoxLayout()

        # Initial control point count
        inital_row = QHBoxLayout()
        inital_row.addWidget(self.initial_cp_label)
        inital_row.addWidget(self.initial_cp_spin)
        layout.addLayout(inital_row)

        # Upper B-spline controls
        upper_row = QHBoxLayout()
        upper_row.addWidget(self.upper_cp_label)
        upper_row.addStretch(1)
        upper_row.addWidget(self.upper_insert_btn)
        layout.addLayout(upper_row)

        # Lower B-spline controls
        lower_row = QHBoxLayout()
        lower_row.addWidget(self.lower_cp_label)
        lower_row.addStretch(1)
        lower_row.addWidget(self.lower_insert_btn)
        layout.addLayout(lower_row)

        # Degree row
        degree_row = QHBoxLayout()
        degree_row.addWidget(self.bspline_degree_label)
        degree_row.addWidget(self.bspline_degree_spin)
        degree_row.addStretch(1)
        layout.addLayout(degree_row)

        # Smoothness row
        smoothness_row = QHBoxLayout()
        smoothness_row.addWidget(self.smoothness_penalty_label)
        smoothness_row.addWidget(self.smoothness_penalty_slider, 1)
        smoothness_row.addWidget(self.smoothness_penalty_spin)
        smoothness_row.addStretch(1)
        layout.addLayout(smoothness_row)

        # G2, G3 in same row
        continuity_row = QHBoxLayout()
        continuity_row.addWidget(self.le_continuity_label)
        continuity_row.addWidget(self.g2_checkbox)
        continuity_row.addWidget(self.g3_checkbox)
        continuity_row.addStretch(1)
        layout.addLayout(continuity_row)

        # Action buttons row
        action_row = QHBoxLayout()
        action_row.addWidget(self.fit_bspline_button, 1)  # Give buttons equal space
        layout.addLayout(action_row)

        self.setLayout(layout)

        # Connect G2/G3 checkboxes for dependency logic
        self.g2_checkbox.toggled.connect(self._update_g3_checkbox_state)
        self.g3_checkbox.toggled.connect(self._update_g2_from_g3)
        self._update_g3_checkbox_state()    # Set initial G3 state
        self.bspline_degree_spin.valueChanged.connect(self._sync_initial_cp_min)
        self.smoothness_penalty_slider.valueChanged.connect(self._update_smoothness_spin)
        self.smoothness_penalty_spin.valueChanged.connect(self._update_smoothness_slider)
        self._sync_initial_cp_min()

    def _update_g3_checkbox_state(self):
        """Enable/disable G3 checkbox based on G2 state."""
        is_g2_enabled = self.g2_checkbox.isChecked()
        self.g3_checkbox.setEnabled(is_g2_enabled)
        if not is_g2_enabled and self.g3_checkbox.isChecked():
            # If G2 is unchecked while G3 is checked, uncheck G3
            self.g3_checkbox.setChecked(False)
    
    def _update_g2_from_g3(self):
        """When G3 is checked, automatically check G2 if not already checked."""
        if self.g3_checkbox.isChecked() and not self.g2_checkbox.isChecked():
            # Temporarily disconnect to avoid recursion
            self.g2_checkbox.blockSignals(True)
            self.g2_checkbox.setChecked(True)
            self.g2_checkbox.blockSignals(False)
            self._update_g3_checkbox_state()  # Update G3 state (should enable it) 

    def _sync_initial_cp_min(self) -> None:
        """Keep initial control point count >= degree + 1."""
        min_cp = int(self.bspline_degree_spin.value()) + 1
        if self.initial_cp_spin.minimum() != min_cp:
            self.initial_cp_spin.setMinimum(min_cp)
        if self.initial_cp_spin.value() < min_cp:
            self.initial_cp_spin.setValue(min_cp)

    def smoothness_penalty_value(self) -> float:
        """Translate the human-friendly smoothing level to its fitter weight."""
        return self._smoothness_from_slider_value(self.smoothness_penalty_spin.value())

    def _update_smoothness_spin(self, slider_value: int) -> None:
        """Keep the numeric smoothing level synchronized with the slider."""
        self.smoothness_penalty_spin.blockSignals(True)
        self.smoothness_penalty_spin.setValue(int(slider_value))
        self.smoothness_penalty_spin.blockSignals(False)

    def _update_smoothness_slider(self, ui_value: int) -> None:
        """Keep the slider synchronized with the numeric smoothing level."""
        self.smoothness_penalty_slider.blockSignals(True)
        self.smoothness_penalty_slider.setValue(int(ui_value))
        self.smoothness_penalty_slider.blockSignals(False)

    @classmethod
    def _smoothness_from_slider_value(cls, slider_value: int) -> float:
        value = max(cls._smoothness_ui_min(),
                    min(cls._smoothness_ui_max(), int(slider_value)))
        return value / config.SMOOTHNESS_UI_SCALE

    @classmethod
    def _slider_from_smoothness_value(cls, smoothness_value: float) -> int:
        ui_value = round(float(smoothness_value) * config.SMOOTHNESS_UI_SCALE)
        return max(cls._smoothness_ui_min(), min(cls._smoothness_ui_max(), ui_value))

    @staticmethod
    def _smoothness_ui_min() -> int:
        return round(config.MIN_SMOOTHNESS_PENALTY * config.SMOOTHNESS_UI_SCALE)

    @staticmethod
    def _smoothness_ui_max() -> int:
        return round(config.MAX_SMOOTHNESS_PENALTY * config.SMOOTHNESS_UI_SCALE)
