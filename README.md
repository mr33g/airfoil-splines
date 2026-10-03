# Airfoil Splines

A desktop application for fitting B-spline curves to airfoil coordinate data and exporting the result for use in CAD software.

## Installation

### Automatic Installation

Download and execute the latest .msi installer package.

### Manual Installation

#### Requirements

- Python 3.10 or later
- Windows, macOS, or Linux

#### Installation Procedure

1. Clone this repository and `mr33g/airfoil-splines-core` into sibling folders named `airfoil-splines` and `airfoil-splines-core`.

2. Create and activate a virtual environment (recommended):
   ```
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS/Linux
   ```

3. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```

airfoil-splines-core is installed in editable mode from the sibling folder. To use a different location, install it with `python -m pip install -e /path/to/airfoil-splines-core` and install the remaining dependencies separately. Packaged installers include the library; end users do not need a separate checkout.

#### Dependencies

| Package    | Purpose                              |
|------------|--------------------------------------|
| numpy      | Numerical operations                 |
| scipy      | B-spline fitting and optimization    |
| PySide6    | Qt GUI framework                     |
| pyqtgraph  | Interactive plotting                 |
| ezdxf      | DXF file export                      |
| airfoil-splines-core | Shared fitting and coordinate loading |
| pyinstaller| Installer utilities                  |


## Usage

### Starting the Application

```
python run_gui.py
```

### Workflow

1. **Load Airfoil Data**  
   Click *Load Airfoil File* and select a `.dat` file. Both Selig and Lednicer formats are supported. The application normalizes coordinates to unit chord with the leading edge at the origin.

2. **Fit B-spline**  
   Click *Fit B-spline* to perform the initial fit. The initial control-point count and degree come from the application settings.

3. **Adjust Parameters**
   - **Degree**: B-spline polynomial degree (4–12). Higher degrees allow smoother curves but may be less stable.
   - **Initial CP count**: Initial control points per surface. Must be greater than degree. Point insertion is biased towards the location of max error, so starting from a low initial count will produce different results than a high initial count.
   - **Smoothness**: Fourth-difference regularization weight. Higher values produce smoother control polygons at the cost of fitting accuracy. The slider uses a nonlinear mapping so the low end gives finer control.
   - **G2 / G3**: Enable curvature (G2) or curvature-derivative (G3) continuity at the leading edge.
   Trailing-edge direction is estimated automatically by airfoil-splines-core.

   Releasing the **Smoothness** slider triggers a fresh fit at the selected setting. Degree and continuity changes re-fit the current model; continuity changes retain inserted knots. The initial count takes effect only on Fit/Reset.

4. **Refine the Fit**
   Use the **+** buttons next to each surface label to insert control points. Knots are inserted at the location of maximum deviation.

5. **Trailing Edge Thickening**  
   Enter a thickness value in millimeters and click *Apply* to add a blunt trailing edge. The offset is applied using a C² quintic blend that preserves leading edge geometry.

6. **Export**  
   - *Export DXF*: Exports upper and lower curves scaled to the specified chord length. Enable the *As Bezier* checkbox to export piecewise Bezier segments instead of NURBS.
   - *Export BSP*: Saves control points and knot vectors in the JSON-based `.bsp` format used for tool interchange.
   - *Export DAT*: Saves a resampled coordinate file in Selig format.

### Configuration

Runtime defaults are defined in `gui/config.py`.
For packaged app installs, the installer ships a user-editable
`airfoil_splines.config.json` next to `AirfoilSplines.exe` in the install folder.
If this file exists, matching uppercase keys override defaults at startup.
You can also point to a custom file with `AIRFOIL_SPLINES_CONFIG`.

Override lookup order:
1. Path from `AIRFOIL_SPLINES_CONFIG` (if set)
2. `airfoil_splines.config.json` next to the executable
3. `airfoil_splines.config.json` in the project root (development fallback)

Available keys:

| Parameter                    | Default | Description                                              |
|------------------------------|---------|----------------------------------------------------------|
| `DEBUG_WORKER_LOGGING`       | False   | Enable verbose worker logging                            |
| `DEFAULT_BSPLINE_DEGREE`     | 4       | Initial B-spline degree                                  |
| `DEFAULT_BSPLINE_CP`         | 9       | Initial control points per surface                       |
| `DEFAULT_SMOOTHNESS_PENALTY` | 0.0     | Base fourth-difference smoothing weight                  |
| `DEFAULT_CHORD_LENGTH_MM`    | 200.0   | Default chord length used for export scaling             |
| `DEFAULT_TE_THICKNESS_MM`    | 0.0     | Default trailing edge thickness value in the UI          |
| `ENABLE_BSP_EXPORT`          | False   | Enable BSP export action                                 |
| `ENABLE_DAT_EXPORT`          | False   | Enable DAT export action                                 |
| `PLOT_POINTS_PER_SURFACE`    | 500     | Base number of sampled points per plotted surface        |
| `PLOT_CURVATURE_WEIGHT`      | 0.85    | Plot sampling blend (0.0 uniform to 1.0 curvature-based) |
| `COMB_DENSITY_MIN`           | 100     | Minimum allowed curvature comb density                   |
| `COMB_DENSITY_MAX`           | 1000    | Maximum allowed curvature comb density                   |
| `COMB_DENSITY_DEFAULT`       | 200     | Default curvature comb density                           |
| `COMB_SCALE_DEFAULT`         | 0.02    | Default curvature comb scale factor                      |

## Background

Airfoil coordinates from sources like the UIUC database are provided as discrete point sets. Importing these directly into CAD software typically results in polylines or low-quality splines that are difficult to edit and may introduce surface artifacts. Extreme cases might even cause problems in CAM due to excessive tool acceleration. 

This application fits smooth B-spline curves to the coordinate data, enforcing geometric constraints that ensure the resulting curves are suitable for CAD modeling.

### Architecture

airfoil-splines-core owns coordinate parsing/normalization, vertical-error fitting, continuity constraints, knot refinement, and BSP/DAT output. This app owns Qt controls, plotting, background jobs, import workflow, and DXF export. Numerical code is not copied into the app.

`gui/fit_session.py` holds desktop fitting state; `gui/airfoil_model.py` bridges the source model to Qt signals. Workers operate on a candidate session and the GUI adopts it only after success, preserving the previous result when an operation fails.

### Tests

Run `python -m unittest discover -s tests -v` from the app folder after installing dependencies. The suite includes numerical integration and offscreen Qt tests for loading, fitting/refitting, insertion, TE thickness, failure recovery, and exports. A visible GUI smoke test is still useful before releasing an installer.

## License

MIT License
