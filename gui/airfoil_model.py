"""Qt signals and plot data around a headless airfoil-splines-core source model."""
from PySide6.QtCore import QObject, Signal
from airfoil_splines_core import AirfoilProcessor
from airfoil_splines_core.bspline_helper import apply_te_thickness_to_reference
from gui import config
from gui.plot_data import calculate_control_point_fourth_difference_data


class AirfoilModel(QObject):
    log_message = Signal(str)
    plot_update_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.source = AirfoilProcessor(logger_func=self.log_message.emit)
        self.error_reference_available = False
        self.error_metrics = {}
        self.display_te_thickness = None

    def load_airfoil_data_and_initialize_model(self, path):
        candidate = AirfoilProcessor(logger_func=self.log_message.emit)
        if not candidate.load_airfoil_data_and_initialize_model(path):
            return False
        self.source = candidate
        self.error_reference_available = True
        self.error_metrics = {}
        return True

    def is_trailing_edge_thickened(self):
        return self.source.is_trailing_edge_thickened()

    @property
    def upper_data(self):
        return self.source.upper_data

    @property
    def lower_data(self):
        return self.source.lower_data

    @property
    def upper_display_reference_data(self):
        return self.source.upper_display_reference_data

    @property
    def lower_display_reference_data(self):
        return self.source.lower_display_reference_data

    @property
    def upper_te_tangent_vector(self):
        return self.source.upper_te_tangent_vector

    @property
    def lower_te_tangent_vector(self):
        return self.source.lower_te_tangent_vector

    @property
    def airfoil_name(self):
        return self.source.airfoil_name

    def build_plot_payload(
        self,
        *,
        bspline_processor=None,
        comb_bspline=None,
    ) -> dict:
        """Build a complete plot payload from current core state and optional B-spline state."""
        display_upper = self.upper_display_reference_data
        display_lower = self.lower_display_reference_data
        if display_upper is None or display_lower is None:
            display_upper = self.upper_data
            display_lower = self.lower_data

        if self.display_te_thickness is not None and display_upper is not None:
            display_upper, display_lower = apply_te_thickness_to_reference(
                display_upper, display_lower, self.display_te_thickness)

        plot_data = {
            'upper_data': display_upper,
            'lower_data': display_lower,
            'upper_te_tangent_vector': self.upper_te_tangent_vector,
            'lower_te_tangent_vector': self.lower_te_tangent_vector,
            'geometry_metrics': None,
        }

        if bspline_processor is None:
            return plot_data

        plot_data.update(
            {
                'bspline_upper_curve': bspline_processor.upper_curve,
                'bspline_lower_curve': bspline_processor.lower_curve,
                'bspline_upper_control_points': bspline_processor.upper_control_points,
                'bspline_lower_control_points': bspline_processor.lower_control_points,
                'comb_bspline': comb_bspline,
                'bspline_is_blunt': not bspline_processor.is_sharp_te,
                'bspline_num_cp_upper': bspline_processor.num_cp_upper,
                'bspline_num_cp_lower': bspline_processor.num_cp_lower,
                'bspline_fourth_difference_data': (
                    calculate_control_point_fourth_difference_data(
                        bspline_processor.upper_control_points, bspline_processor.lower_control_points,
                        max_plot_length=config.CP_FOURTH_DIFF_MAX_PLOT_LENGTH)
                    if bool(getattr(config, "SHOW_CP_FOURTH_DIFFERENCES", False))
                    else None
                ),
            }
        )

        if self.error_reference_available and bool(self.error_metrics):
            plot_data['bspline_upper_max_error'] = self.error_metrics["upper"]["max_error"]
            plot_data['bspline_upper_max_error_idx'] = self.error_metrics["upper"]["max_error_idx"]
            plot_data['bspline_lower_max_error'] = self.error_metrics["lower"]["max_error"]
            plot_data['bspline_lower_max_error_idx'] = self.error_metrics["lower"]["max_error_idx"]

        return plot_data

    def emit_plot_update(
        self,
        *,
        bspline_processor=None,
        comb_bspline=None,
    ) -> None:
        """Emit a plot update request from a centrally generated payload."""
        plot_data = self.build_plot_payload(
            bspline_processor=bspline_processor,
            comb_bspline=comb_bspline,
        )
        self._last_plot_data = plot_data.copy()
        self.plot_update_requested.emit(plot_data)

