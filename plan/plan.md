# Georeferencing Tool Development Plan

## 1. Project Goal

Develop a general-purpose, offline desktop application for georeferencing raster images using XYZ tiles as a reference.

## 2. Core Features

*   Display image and XYZ tile layers simultaneously.
*   Independent layer controls: visibility and opacity.
*   Map navigation: zoom, pan.
*   Ground Control Point (GCP) management:
    *   Add GCPs by clicking on image and map/tile layers.
    *   Add GCPs by manual coordinate input.
    *   Display GCPs in a table.
    *   Save/Load GCPs.
*   Multiple transformation algorithms (e.g., Polynomial, Thin Plate Spline).
*   Optional GCP weighting based on distance.
*   Real-time preview of the georeferenced image transformation.
*   Toggle preview on/off.
*   Export the georeferenced image (e.g., GeoTIFF).

## 3. Technical Stack

*   **Language:** Python 3
*   **GUI Framework:** PyQt6 (or Tkinter, but PyQt is preferred for features)
*   **Core Libraries:**
    *   NumPy: Numerical operations.
    *   Pillow: Image loading and basic manipulation.
    *   scikit-image: Transformation algorithms (Polynomial, TPS).
    *   rasterio / GDAL (Optional, for advanced GeoTIFF export/import): May add complexity for offline distribution. Consider optional installation or simpler TIFF writing initially.
*   **Environment:** Offline desktop application.

## 4. Architecture Overview

*   **Main Application (`QMainWindow`):** Hosts all components, menu bar, status bar.
*   **Map View Widget (`QWidget` or `QGraphicsView`):** Central widget for displaying layers, handling navigation (zoom/pan), and mouse interactions (GCP placement). Responsible for rendering the image, tiles (if implemented), GCP markers, and the transformed preview.
*   **Layer Control Dock (`QDockWidget`):** Contains controls (checkboxes, sliders) for managing layer visibility and opacity.
*   **GCP Management Dock (`QDockWidget`):** Contains a `QTableView` (with a custom `QAbstractTableModel`) to display GCPs, input fields for manual entry, and buttons for add/remove/save/load operations.
*   **Transformation Control Dock (`QDockWidget`):** Contains controls (`QComboBox`, `QCheckBox`) to select the transformation algorithm, weighting method, and toggle the real-time preview.
*   **Model/Logic:** Separate classes or modules for:
    *   Handling GCP data.
    *   Calculating transformations.
    *   Managing layer state.
    *   (Potentially) Handling tile fetching and caching if XYZ tiles are implemented.

## 5. Implementation Steps

### Phase 1: Basic UI and Image Display
1.  **Project Setup:** Create project structure, virtual environment, install initial dependencies (PyQt6, Pillow, NumPy).
2.  **Main Window:** Implement the `QMainWindow` structure (`main.py`).
3.  **Docks:** Create the basic `QDockWidget` areas for Layers, GCPs, and Transformation.
4.  **Map View Stub:** Create a basic `MapViewWidget` class.
5.  **Image Loading:** Implement "File -> Open Image" menu action using `QFileDialog`.
6.  **Basic Image Display:** Load the selected image using Pillow and display it (statically) in the `MapViewWidget` using `QPainter` or within a `QGraphicsView`/`QGraphicsPixmapItem`.

### Phase 2: Map Interaction
1.  **Zoom:** Implement zoom functionality in `MapViewWidget` (e.g., using mouse wheel events and `QPainter.scale` or `QGraphicsView.scale`).
2.  **Pan:** Implement panning in `MapViewWidget` (e.g., using mouse drag events and `QPainter.translate` or `QGraphicsView` scrollbars/drag mode).
3.  **Coordinate Display:** Show current mouse coordinates (image coordinates) in the status bar.

### Phase 3: GCP Management
1.  **GCP Data Structure:** Define how GCPs will be stored (e.g., list of tuples/objects).
2.  **GCP Table Model:** Implement a `QAbstractTableModel` to manage GCP data.
3.  **GCP Table View:** Display the model in the `QTableView` in the GCP dock.
4.  **Manual GCP Input:** Add input fields (`QDoubleSpinBox`) and an "Add GCP" button to the GCP dock. Connect the button to add data to the model.
5.  **Map Click for GCPs:** Implement mouse click handling in `MapViewWidget` to get image coordinates. Add logic to temporarily store the image click point, waiting for a corresponding map/tile click (or manual map coordinate input). *Initially, focus on image clicks and manual map coordinate entry.*
6.  **GCP Markers:** Draw markers on the `MapViewWidget` at the image coordinate locations for each GCP in the model.
7.  **GCP Selection/Deletion:** Allow selecting rows in the table and add a "Remove Selected" button.

### Phase 4: Transformation Logic & Preview
1.  **Install scikit-image:** Add `scikit-image` dependency.
2.  **Transformation Calculation:**
    *   Create a function/class to calculate the transformation matrix/object based on the current GCP list and the selected algorithm (start with Polynomial Order 1). Use `skimage.transform`.
    *   Trigger recalculation whenever GCPs are added/removed or the algorithm changes.
3.  **Algorithm Selection:** Connect the `QComboBox` in the Transformation dock to update the selected algorithm.
4.  **Preview Toggle:** Connect the "Real-time Preview" `QCheckBox`.
5.  **Preview Rendering:**
    *   In `MapViewWidget.paintEvent`, if preview is enabled and a valid transformation exists, apply the transformation when drawing the image. This might involve:
        *   Using `QPainter.setTransform()`.
        *   Warping the `QPixmap` before drawing (can be slow).
        *   Drawing a transformed grid over the original image.
        *   Drawing transformed GCP markers.

### Phase 5: XYZ Tile Integration (Optional/Advanced)
1.  **Tile Source Configuration:** Allow users to input an XYZ tile server URL template.
2.  **Tile Fetching:** Implement logic to calculate required tiles based on the current view (zoom/pan) and fetch them (requires network requests, consider `requests` library). Handle potential errors.
3.  **Tile Caching:** Implement a simple file-based cache for fetched tiles to improve performance and support offline use after initial fetch.
4.  **Tile Rendering:** Draw the fetched tiles in the correct positions in the `MapViewWidget`, underneath the image layer.
5.  **Map Coordinate Input:** Enable clicking on the tile layer in `MapViewWidget` to get map coordinates (requires converting view coordinates to geographic/projected coordinates based on tile schema). Link this click to the GCP creation process.

### Phase 6: Layer Controls
1.  **Visibility:** Connect the "Visible" checkboxes in the Layer dock to toggle the drawing of the image and tile layers in `MapViewWidget`.
2.  **Opacity:** Connect the `QSlider` controls to set the opacity level for the image layer when drawing it using `QPainter.setOpacity`. Tile layer opacity might be more complex depending on rendering.

### Phase 7: File I/O & Export
1.  **Save/Load GCPs:** Implement functionality to save the GCP list (image coords, map coords) to a simple format (e.g., CSV) and load them back. Use `QFileDialog`.
2.  **Export Georeferenced Image:**
    *   **Option A (Simpler):** If `rasterio`/`GDAL` is too complex, export the *transformed* image corners (calculated using the final transformation) along with the original image. The user would need external tools to create a proper GeoTIFF.
    *   **Option B (Better, requires `rasterio`):**
        *   Add `rasterio` as a dependency.
        *   Use the calculated transformation (e.g., affine matrix from Polynomial Order 1, or GCPs for `rasterio.warp.reproject` with TPS) to write a new GeoTIFF file containing the original image data warped to the target coordinate system defined by the GCPs. This requires defining a target Coordinate Reference System (CRS), which might need user input or be inferred if using standard web tiles (like EPSG:3857).

## 6. Potential Libraries

*   **PyQt6:** GUI Framework
*   **Pillow:** Image I/O
*   **NumPy:** Array manipulation
*   **scikit-image:** Image processing, transformations (Polynomial, TPS)
*   **requests:** (Optional) For fetching XYZ tiles
*   **rasterio:** (Optional) For advanced GeoTIFF I/O and warping

## 7. Future Enhancements

*   Support for more transformation algorithms.
*   Advanced GCP weighting options.
*   Coordinate system selection/handling (CRS).
*   Displaying transformation residuals/errors per GCP.
*   Vector layer overlay.
*   Integration with projection libraries (pyproj).
*   Asynchronous tile fetching.
