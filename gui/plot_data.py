"""Control-polygon diagnostics for plotting."""
import numpy as np

def calculate_control_point_fourth_difference_data(
    upper_control_points: np.ndarray | None,
    lower_control_points: np.ndarray | None,
    *,
    max_plot_length: float = 0.040,
) -> dict[str, object] | None:
    """
    Calculate fourth finite differences of the B-spline control polygons for
    visualization only.

    Each fourth difference belongs to a five-control-point window and is plotted
    at the middle point of that window. The raw d4 vectors are returned unchanged;
    only the display segments are scaled so the largest vector has a predictable
    on-plot length.
    """
    surfaces: dict[str, dict[str, np.ndarray]] = {}
    max_norm = 0.0

    for name, control_points in (
        ("upper", upper_control_points),
        ("lower", lower_control_points),
    ):
        if control_points is None:
            continue
        cp = np.asarray(control_points, dtype=float)
        if cp.ndim != 2 or cp.shape[0] < 5 or cp.shape[1] < 2:
            continue

        d4 = np.diff(cp[:, :2], n=4, axis=0)
        anchors = cp[2:-2, :2]
        magnitudes = np.linalg.norm(d4, axis=1)
        if magnitudes.size:
            max_norm = max(max_norm, float(np.max(magnitudes)))

        surfaces[name] = {
            "anchors": anchors,
            "vectors": d4,
            "magnitudes": magnitudes,
        }

    if not surfaces:
        return None

    scale = 0.0 if max_norm <= 1e-15 else float(max_plot_length) / max_norm
    for surface in surfaces.values():
        anchors = surface["anchors"]
        vectors = surface["vectors"]
        endpoints = anchors + vectors * scale
        segments = np.empty((anchors.shape[0] * 2, 2), dtype=float)
        segments[0::2] = anchors
        segments[1::2] = endpoints
        surface["segments"] = segments
        surface["scale"] = np.array([scale], dtype=float)

    return {
        "surfaces": surfaces,
        "scale": float(scale),
        "max_magnitude": float(max_norm),
    }
