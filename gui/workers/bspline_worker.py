"""Run an isolated operation; adopt its result only after the thread exits."""
from PySide6.QtCore import QThread


class BSplineWorker(QThread):
    def __init__(self, session, operation, parent=None):
        super().__init__(parent)
        self.session = session
        self.operation = operation
        self.success = False
        self.message = ""

    def run(self):
        try:
            self.message = self.operation(self.session)
            self.success = True
        except Exception as exc:
            self.message = str(exc)
