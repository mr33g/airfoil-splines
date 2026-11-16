"""Save dialog with options that affect spline representation only."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QFileDialog


class SplineExportDialog(QFileDialog):
    """A save dialog that keeps the loft-conversion choice local to export."""

    def __init__(
        self,
        parent,
        title: str,
        default_filename: str,
        name_filter: str,
    ) -> None:
        super().__init__(parent, title, default_filename, name_filter)
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.selectFile(default_filename)

        self.loft_compatible_checkbox = QCheckBox(
            "Export loft-compatible splines", self
        )
        self.loft_compatible_checkbox.setToolTip(
            "Export a derived degree-4, 35-point spline representation with "
            "fixed control-point X positions and a shared knot vector. This "
            "improves CAD loft compatibility without changing the fitted airfoil."
        )
        layout = self.layout()
        layout.addWidget(
            self.loft_compatible_checkbox,
            layout.rowCount(),
            0,
            1,
            layout.columnCount(),
        )

    @property
    def export_loft_compatible(self) -> bool:
        return self.loft_compatible_checkbox.isChecked()
