"""File operations controller for the Airfoil Fitter GUI.

Handles loading airfoil data files and exporting B-spline models.
"""

from __future__ import annotations

import os
import math
from typing import Any
import numpy as np

from PySide6.QtWidgets import QFileDialog
from scipy import interpolate

from gui.airfoil_model import AirfoilModel
from gui import config
from utils.dxf_exporter import (
    DXF_EXPORT_MODE_BEZIER,
    DXF_EXPORT_MODE_NURBS,
    export_bspline_to_dxf,
)
from airfoil_fit import AirfoilProcessor, BSplineProcessor, export_bspline_to_bsp
from utils.bsp_importer import load_bspline_from_bsp
from airfoil_fit.data_loader import export_airfoil_to_selig_format
from gui.fit_session import FitSession


class FileController:
    """Handles file loading and export operations."""
    
    def __init__(self, processor: AirfoilModel, window: Any, ui_state_controller: Any = None):
        self.processor = processor
        self.window = window
        self.ui_state_controller = ui_state_controller

    def _get_bspline_processor(self):
        """Return the canonical B-spline processor instance."""
        bspline_controller = getattr(self.window, "bspline_controller", None)
        if bspline_controller is not None:
            bspline_proc = getattr(bspline_controller, "bspline_processor", None)
            if bspline_proc is not None:
                return bspline_proc
        return getattr(self.window, "bspline_processor", None)
    
    def load_airfoil_file(self) -> None:
        """Handle loading an airfoil data file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Load Airfoil Data / BSP",
            "",
            "Airfoil/BSP Files (*.dat *.bsp);;Airfoil Data Files (*.dat);;BSP Files (*.bsp);;All Files (*)",
        )

        if not file_path:
            return

        try:
            suffix = os.path.splitext(file_path)[1].lower()
            if suffix == ".bsp":
                if self._load_bsp_file(file_path):
                    self.processor.log_message.emit(
                        f"Successfully loaded BSP '{os.path.basename(file_path)}'."
                    )
                    self.window.file_panel.file_path_label.setText(os.path.basename(file_path))
                    if self.ui_state_controller:
                        self.ui_state_controller.update_button_states()
                else:
                    self.processor.log_message.emit(
                        f"Failed to load BSP '{os.path.basename(file_path)}'. Check file format and content."
                    )
            elif self.processor.load_airfoil_data_and_initialize_model(file_path):
                self.processor.log_message.emit(
                    f"Successfully loaded '{os.path.basename(file_path)}'."
                )
                
                self.window.file_panel.file_path_label.setText(os.path.basename(file_path))
                # Reset UI state for new airfoil
                if self.ui_state_controller:
                    self.ui_state_controller.reset_ui_for_new_airfoil()
            else:
                self.processor.log_message.emit(
                    f"Failed to load '{os.path.basename(file_path)}'. Check file format and content."
                )
        except Exception as exc:  # pragma: no cover – unexpected error path
            self.processor.log_message.emit(
                f"An unexpected error occurred during file loading: {exc}"
            )

    def _load_bsp_file(self, file_path: str) -> bool:
        """Adopt a validated model atomically, with an optional measured DAT reference."""
        data = load_bspline_from_bsp(file_path)
        session = FitSession((data.upper_degree, data.lower_degree))
        model = session.model
        for side in ("upper", "lower"):
            cp = getattr(data, side + "_control_points")
            knots = getattr(data, side + "_knots")
            degree = getattr(data, side + "_degree")
            setattr(model, side + "_control_points", cp.copy())
            setattr(model, side + "_knot_vector", knots.copy())
            setattr(model, side + "_curve", interpolate.BSpline(knots, cp, degree))
            setattr(model, "num_cp_" + side, len(cp))
        model.fitted_degree = (data.upper_degree, data.lower_degree)
        model.is_sharp_te = bool(np.linalg.norm(data.upper_control_points[-1] - data.lower_control_points[-1]) <= 1e-8)
        model.fitted = True
        source = AirfoilProcessor(logger_func=self.processor.log_message.emit)
        reference_path = self._find_matching_dat_for_bsp(file_path)
        has_reference = False
        if reference_path:
            has_reference = source.load_airfoil_data_and_initialize_model(reference_path)
        if not has_reference:
            source.upper_data, source.lower_data = self._sample_bsp_curves(model.upper_curve, model.lower_curve)
            source.upper_display_reference_data = source.upper_data.copy()
            source.lower_display_reference_data = source.lower_data.copy()
            source.airfoil_name = data.airfoil_name
        model.upper_original_data = source.upper_data.copy()
        model.lower_original_data = source.lower_data.copy()
        self.processor.source = source
        self.processor.error_reference_available = has_reference
        self.processor.error_metrics = {}
        controller = self.window.bspline_controller
        controller.session = session
        controller._sync_model()
        # Imported degrees/counts belong to the file, not the last-used controls.
        opt = self.window.optimizer_panel
        for widget in (opt.bspline_degree_spin, opt.initial_cp_spin, opt.g2_checkbox, opt.g3_checkbox):
            widget.blockSignals(True)
        opt.bspline_degree_spin.setValue(max(data.upper_degree, data.lower_degree))
        opt._sync_initial_cp_min()
        opt.initial_cp_spin.setValue(max(model.num_cp_upper, model.num_cp_lower))
        # BSP has no continuity metadata. Do not claim it was fitted with G2/G3.
        opt.g2_checkbox.setChecked(False)
        opt.g3_checkbox.setChecked(False)
        opt._update_g3_checkbox_state()
        for widget in (opt.bspline_degree_spin, opt.initial_cp_spin, opt.g2_checkbox, opt.g3_checkbox):
            widget.blockSignals(False)
        if self.ui_state_controller:
            self.ui_state_controller._calculate_initial_thickness()
        controller._update_fit_button_text()
        controller._update_final_error_metrics()
        controller._update_plot_with_bsplines()
        return True

    def _sample_bsp_curves(self, upper_curve, lower_curve) -> tuple[np.ndarray, np.ndarray]:
        sample_count = max(200, int(config.PLOT_POINTS_PER_SURFACE))
        t_values = np.linspace(0.0, 1.0, sample_count)
        if len(t_values) > 0:
            t_values[-1] = min(t_values[-1], 1.0 - 1e-12)
        return upper_curve(t_values), lower_curve(t_values)

    def _find_matching_dat_for_bsp(self, bsp_path: str) -> str | None:
        bsp = os.path.abspath(bsp_path)
        base_dir = os.path.dirname(bsp)
        stem = os.path.splitext(os.path.basename(bsp))[0].lower()
        try:
            for name in os.listdir(base_dir):
                path = os.path.join(base_dir, name)
                if not os.path.isfile(path):
                    continue
                file_stem, ext = os.path.splitext(name)
                if ext.lower() == ".dat" and file_stem.lower() == stem:
                    return path
        except OSError:
            return None
        return None
    

    def export_dxf(self) -> None:
        """Export the current B-spline model as a DXF file."""
        # Check if B-spline is available and fitted
        bspline_proc = self._get_bspline_processor()
        bspline_fitted = False
        if bspline_proc is not None:
            try:
                bspline_fitted = bool(getattr(bspline_proc, "fitted", False))
            except Exception:
                bspline_fitted = False

        if not bspline_fitted or getattr(bspline_proc, "upper_control_points", None) is None or \
           getattr(bspline_proc, "lower_control_points", None) is None:
            self.processor.log_message.emit(
                "Error: B-spline model not available for export. Please fit B-spline first."
            )
            return

        # Use B-spline export
        self.export_bspline_dxf()
    
    def export_bspline_dxf(self) -> None:
        """Export the current B-spline model as a DXF file."""
        # Check if B-spline processor is available and fitted
        bspline_proc = self._get_bspline_processor()
        if bspline_proc is None or not getattr(bspline_proc, "fitted", False):
            self.processor.log_message.emit(
                "Error: B-spline model not available for export. Please fit B-spline first."
            )
            return

        try:
            chord_length_mm = float(
                self.window.airfoil_settings_panel.chord_length_input.text()
            )
            if not math.isfinite(chord_length_mm) or chord_length_mm <= 0:
                raise ValueError("Chord length must be positive.")
        except ValueError:
            self.processor.log_message.emit(
                "Error: Invalid chord length. Please enter a number."
            )
            return

        export_mode = DXF_EXPORT_MODE_NURBS
        file_panel = getattr(self.window, "file_panel", None)
        if file_panel is not None:
            as_bezier_checkbox = getattr(file_panel, "export_dxf_as_bezier_checkbox", None)
            if as_bezier_checkbox is not None and as_bezier_checkbox.isChecked():
                export_mode = DXF_EXPORT_MODE_BEZIER

        dxf_doc = export_bspline_to_dxf(
            bspline_proc,
            chord_length_mm,
            self.processor.log_message.emit,
            export_mode=export_mode,
        )

        if not dxf_doc:
            self.processor.log_message.emit(
                "B-spline DXF export failed during document creation."
            )
            return

        default_filename = self._get_default_dxf_filename()
        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save B-spline DXF File",
            default_filename,
            "DXF Files (*.dxf)",
        )
        if not file_path:
            self.processor.log_message.emit("B-spline DXF export cancelled by user.")
            return

        try:
            dxf_doc.saveas(file_path)
            self.processor.log_message.emit(
                f"B-spline DXF export successful to '{os.path.basename(file_path)}'."
            )
            self.processor.log_message.emit(
                "Note: For correct scale in CAD software, ensure import settings are configured for millimeters."
            )
        except IOError as exc:
            self.processor.log_message.emit(f"Could not save DXF file: {exc}")
    
    def _get_default_dxf_filename(self) -> str:
        """Return a safe default filename based on the loaded profile."""
        import re

        profile_name = getattr(self.processor, "airfoil_name", None)
        if profile_name:
            sanitized = re.sub(r"[^A-Za-z0-9\-_]+", "_", profile_name)
            if sanitized:
                return f"{sanitized}.dxf"
        return "airfoil.dxf" 

    def export_dat_file(self) -> None:
        """Export the current B-spline model as a high-resolution .dat file."""
        if not config.ENABLE_DAT_EXPORT:
            self.processor.log_message.emit("DAT export is disabled in config.")
            return

        # Get the number of points per surface from the UI
        try:
            points_per_surface = self.window.file_panel.points_per_surface_input.value()
        except ValueError:
            self.processor.log_message.emit(
                "Error: Invalid number of points. Please enter a valid number."
            )
            return

        # Get the current airfoil name
        airfoil_name = getattr(self.processor, "airfoil_name", "airfoil")
        if not airfoil_name:
            airfoil_name = "airfoil"

        # Check if B-spline is available and fitted
        bspline_proc = self._get_bspline_processor()
        try:
            bspline_fitted = bool(getattr(bspline_proc, "fitted", False))
        except Exception:
            bspline_fitted = False

        if not bspline_fitted or getattr(bspline_proc, "upper_curve", None) is None or \
           getattr(bspline_proc, "lower_curve", None) is None:
            self.processor.log_message.emit(
                "Error: B-spline model not available for export. Please fit B-spline first."
            )
            return

        try:
            t_values = np.linspace(0.0, 1.0, points_per_surface)
            if len(t_values) > 0:
                t_values[-1] = min(t_values[-1], 1.0 - 1e-12)
            upper_points = bspline_proc.upper_curve(t_values)
            lower_points = bspline_proc.lower_curve(t_values)

            # Default filename
            default_filename = self._get_default_dat_filename(f"{airfoil_name}_bspline")

            file_path, _ = QFileDialog.getSaveFileName(
                self.window,
                "Save B-spline High-Resolution .dat File",
                default_filename,
                "DAT Files (*.dat);;All Files (*)",
            )
            if not file_path:
                self.processor.log_message.emit(".dat export cancelled by user.")
                return

            export_airfoil_to_selig_format(upper_points, lower_points, airfoil_name, file_path)
            self.processor.log_message.emit(
                f"B-spline .dat export successful to '{os.path.basename(file_path)}'."
            )
            self.processor.log_message.emit(
                f"Exported {len(upper_points)} points per surface in Selig format."
            )
        except Exception as exc:
            self.processor.log_message.emit(
                f"Error during B-spline .dat export: {exc}"
            )

    def _get_default_dat_filename(self, airfoil_name: str) -> str:
        """Return a safe default filename for .dat export based on the loaded profile."""
        import re

        if airfoil_name:
            sanitized = re.sub(r"[^A-Za-z0-9\-_]+", "_", airfoil_name)
            if sanitized:
                return f"{sanitized}_highres.dat"
        return "airfoil_highres.dat"

    def export_bsp_file(self) -> None:
        """Export the current B-spline model as a .bsp file."""
        if not config.ENABLE_BSP_EXPORT:
            self.processor.log_message.emit("BSP export is disabled in config.")
            return

        bspline_proc = self._get_bspline_processor()
        try:
            bspline_fitted = bool(getattr(bspline_proc, "fitted", False))
        except Exception:
            bspline_fitted = False

        if not bspline_fitted:
            self.processor.log_message.emit(
                "Error: B-spline model not available for export. Please fit B-spline first."
            )
            return

        airfoil_name = getattr(self.processor, "airfoil_name", "airfoil") or "airfoil"
        default_filename = self._get_default_bsp_filename(airfoil_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "Save B-spline .bsp File",
            default_filename,
            "BSP Files (*.bsp);;All Files (*)",
        )
        if not file_path:
            self.processor.log_message.emit(".bsp export cancelled by user.")
            return

        ok = export_bspline_to_bsp(
            bspline_proc,
            airfoil_name,
            file_path,
            self.processor.log_message.emit,
        )
        if ok:
            self.processor.log_message.emit(
                f"B-spline .bsp export successful to '{os.path.basename(file_path)}'."
            )
        else:
            self.processor.log_message.emit("Error during B-spline .bsp export.")

    def _get_default_bsp_filename(self, airfoil_name: str) -> str:
        """Return a safe default filename for .bsp export based on the loaded profile."""
        import re

        if airfoil_name:
            sanitized = re.sub(r"[^A-Za-z0-9\-_]+", "_", airfoil_name)
            if sanitized:
                return f"{sanitized}.bsp"
        return "airfoil.bsp"
