import sys
import io # Add io for image data handling
import requests # Add requests for fetching tiles
import requests_cache # Add requests_cache for caching
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSplitter, QDockWidget, QListWidget, QSlider, QCheckBox,
    QPushButton, QTableView, QGroupBox, QComboBox, QDoubleSpinBox, QStatusBar,
    QLineEdit, QSpinBox # Add QLineEdit and QSpinBox
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize # Add QRectF, QSize
from PyQt6.QtGui import QPixmap, QPainter, QTransform, QImage # Add QImage
import math # Add math for calculations

# --- Constants ---
TILE_SIZE = 256 # Standard size for web map tiles

# Setup caching (configure as needed, e.g., cache name, backend)
# Cache expires after 1 day by default, can be configured
requests_cache.install_cache('tile_cache', backend='sqlite', expire_after=86400) # Default 1 day expiry

# Placeholder for a custom MapView widget
class MapViewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(600, 400)
        self.image_layer = None
        # Tile Layer Attributes
        self.tile_layer = {} # Dictionary to store fetched tiles { (z,x,y): QImage }
        self.tile_url_template = None # e.g., "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        self.tile_visible = True
        self.requests_session = requests_cache.CachedSession() # Use cached session

        self.gcps = []
        self.preview_enabled = False
        self.transformation = None
        # Map view state (basic example)
        self.zoom = 1 # Start at zoom level 1
        # Center point in *pixel* coordinates at the current zoom level
        # (0,0) corresponds to the top-left corner of the world map at this zoom
        self.center_pixel_x = TILE_SIZE / 2
        self.center_pixel_y = TILE_SIZE / 2
        self._last_pan_pos = None # For mouse panning

        # Set focus policy to accept keyboard events if needed, and mouse events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True) # Receive mouse move events even when no button is pressed

    def load_image(self, image_path):
        print(f"Loading image: {image_path}")
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print(f"Error: Failed to load image {image_path}")
            self.image_layer = None
            # Optionally show an error message to the user
        else:
            self.image_layer = pixmap
            print(f"Image loaded successfully: {self.image_layer.size()}")
            # TODO: Potentially reset view or fit image?
        self.update() # Redraw

    def set_preview(self, enabled):
        self.preview_enabled = enabled
        print(f"Preview enabled: {enabled}")
        self.update() # Redraw

    def add_gcp(self, img_pos: QPointF, map_pos: QPointF):
         # TODO: Add GCP logic
         print(f"Adding GCP: Image={img_pos}, Map={map_pos}")
         self.gcps.append((img_pos, map_pos))
         self.update_transformation() # Recalculate transformation
         self.update() # Redraw

    def update_transformation(self):
        # TODO: Implement transformation calculation based on self.gcps and selected algorithm
        print("Updating transformation...")
        # Example using scikit-image (requires more setup)
        # if len(self.gcps) >= 3: # Need enough points for transformation
        #    src = np.array([[p[0].x(), p[0].y()] for p in self.gcps])
        #    dst = np.array([[p[1].x(), p[1].y()] for p in self.gcps])
        #    if self.selected_algorithm == "Polynomial":
        #        self.transformation = PolynomialTransform()
        #        self.transformation.estimate(src, dst)
        #    # Add other algorithms (TPS, etc.)
        pass

    def set_tile_url(self, url_template: str):
        """Sets the XYZ tile URL template."""
        if '{z}' in url_template and '{x}' in url_template and '{y}' in url_template:
            self.tile_url_template = url_template
            self.tile_layer.clear() # Clear old tiles
            self.update() # Redraw with new tiles
            print(f"Tile URL set to: {url_template}")
        else:
            print("Invalid tile URL template. Must contain {z}, {x}, {y}.")
            self.tile_url_template = None
            self.update()

    def set_tile_visibility(self, visible: bool):
        """Sets the visibility of the tile layer."""
        if self.tile_visible != visible:
            self.tile_visible = visible
            print(f"Tile visibility set to: {visible}")
            self.update() # Redraw

    def set_cache_duration(self, days: int):
        """Sets the cache expiration duration in days."""
        if days >= 0:
            expire_after = days * 86400 # Convert days to seconds
            # Reconfigure the cache session
            requests_cache.install_cache('tile_cache', backend='sqlite', expire_after=expire_after)
            self.requests_session = requests_cache.CachedSession() # Recreate session with new expiry
            print(f"Tile cache duration set to {days} days.")
        else:
            print("Cache duration must be non-negative.")


    def fetch_tile(self, z, x, y):
        """Fetches a single tile image, using cache if available."""
        if not self.tile_url_template or not self.tile_visible:
            return None
        if (z, x, y) in self.tile_layer:
            return self.tile_layer[(z, x, y)]

        url = self.tile_url_template.format(z=z, x=x, y=y)
        try:
            # Use the cached session
            response = self.requests_session.get(url, headers={'User-Agent': 'GeoreferenceApp/0.1'}) # Add User-Agent
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Check if the response came from cache
            was_cached = getattr(response, 'from_cache', False)
            if not was_cached:
                print(f"Fetched tile (Not Cached): {z}/{x}/{y}")
            # else:
            #     print(f"Fetched tile (Cached): {z}/{x}/{y}")


            image = QImage()
            image.loadFromData(response.content)
            if not image.isNull():
                self.tile_layer[(z, x, y)] = image
                return image
            else:
                print(f"Failed to load image data for tile: {z}/{x}/{y}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"Error fetching tile {z}/{x}/{y}: {e}")
            # Optionally cache a 'failed' tile marker?
            return None
        except Exception as e:
            print(f"Error processing tile {z}/{x}/{y}: {e}")
            return None

    # --- Coordinate Conversion Helpers ---
    def world_pixels_to_tile_coords(self, px, py, zoom):
        """Converts world pixel coordinates at a given zoom to tile coordinates (z, x, y)."""
        # Total pixels in the world map at this zoom level
        # map_size_pixels = TILE_SIZE * (2 ** zoom)
        tile_x = math.floor(px / TILE_SIZE)
        tile_y = math.floor(py / TILE_SIZE)
        return zoom, tile_x, tile_y

    def screen_to_world_pixels(self, screen_pos: QPointF):
        """Converts screen pixel coordinates (relative to widget) to world pixel coordinates."""
        # Calculate the top-left world pixel coordinate visible in the widget
        view_width = self.width()
        view_height = self.height()
        top_left_world_x = self.center_pixel_x - view_width / 2
        top_left_world_y = self.center_pixel_y - view_height / 2

        world_x = top_left_world_x + screen_pos.x()
        world_y = top_left_world_y + screen_pos.y()
        return QPointF(world_x, world_y)

    def world_to_screen_pixels(self, world_pos: QPointF):
        """Converts world pixel coordinates to screen pixel coordinates (relative to widget)."""
        view_width = self.width()
        view_height = self.height()
        top_left_world_x = self.center_pixel_x - view_width / 2
        top_left_world_y = self.center_pixel_y - view_height / 2

        screen_x = world_pos.x() - top_left_world_x
        screen_y = world_pos.y() - top_left_world_y
        return QPointF(screen_x, screen_y)

    # --- Painting Logic ---
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray) # Background
        view_rect = self.rect() # The rectangle of the widget area

        # --- Draw Tile Layer ---
        if self.tile_visible and self.tile_url_template:
            # Determine the range of world pixels visible in the view
            top_left_world = self.screen_to_world_pixels(QPointF(0, 0))
            bottom_right_world = self.screen_to_world_pixels(QPointF(view_rect.width(), view_rect.height()))

            # Determine the range of tiles needed
            z = self.zoom
            _, min_tile_x, min_tile_y = self.world_pixels_to_tile_coords(top_left_world.x(), top_left_world.y(), z)
            _, max_tile_x, max_tile_y = self.world_pixels_to_tile_coords(bottom_right_world.x(), bottom_right_world.y(), z)

            # Fetch and draw the required tiles
            for tile_x in range(min_tile_x, max_tile_x + 1):
                for tile_y in range(min_tile_y, max_tile_y + 1):
                    tile_image = self.fetch_tile(z, tile_x, tile_y)
                    if tile_image:
                        # Calculate the top-left world pixel coordinate of this tile
                        tile_world_x = tile_x * TILE_SIZE
                        tile_world_y = tile_y * TILE_SIZE
                        # Convert tile's world position to screen position
                        screen_pos = self.world_to_screen_pixels(QPointF(tile_world_x, tile_world_y))
                        # Draw the tile
                        painter.drawImage(screen_pos, tile_image)
                    # else: # Optionally draw a placeholder for missing tiles
                    #     tile_world_x = tile_x * TILE_SIZE
                    #     tile_world_y = tile_y * TILE_SIZE
                    #     screen_pos = self.world_to_screen_pixels(QPointF(tile_world_x, tile_world_y))
                    #     painter.setPen(Qt.GlobalColor.red)
                    #     painter.drawRect(QRectF(screen_pos.x(), screen_pos.y(), TILE_SIZE, TILE_SIZE))
                    #     painter.drawText(QRectF(screen_pos.x(), screen_pos.y(), TILE_SIZE, TILE_SIZE), Qt.AlignmentFlag.AlignCenter, f"{z}/{tile_x}/{tile_y}")

        # --- Draw Image Layer ---
        if self.image_layer:
            # TODO: Apply zoom/pan to the image layer as well.
            # This requires mapping image coordinates to the same world coordinate system
            # or applying a separate transformation based on view state.
            # For now, just draw it at the top-left, untransformed.
            if self.preview_enabled and self.transformation:
                 print("Drawing preview (not implemented)")
                 # Placeholder: draw original image slightly offset
                 painter.drawPixmap(10, 10, self.image_layer)
            else:
                # Draw image at a fixed screen position (e.g., top-left) for now
                # Ideally, this should also be positioned based on self.center_pixel_x/y and self.zoom
                # or based on the georeferencing transformation.
                painter.drawPixmap(0, 0, self.image_layer)

        # --- Draw GCP Markers ---
        painter.setPen(Qt.GlobalColor.red)
        painter.setBrush(Qt.GlobalColor.red)
        for img_pos, map_pos in self.gcps:
             # TODO: Adjust img_pos based on image layer's current transformation (zoom/pan)
             # For now, draw relative to the fixed image position (0,0)
             screen_img_pos = img_pos # Assuming image is drawn at 0,0
             painter.drawEllipse(screen_img_pos, 3, 3)

             # TODO: Convert map_pos (map coordinates - lat/lon or projected) to world pixels
             # This requires a projection conversion (e.g., Mercator for standard web maps)
             # Then convert world pixels to screen pixels.
             # world_gcp_pos = self.map_coords_to_world_pixels(map_pos, self.zoom)
             # screen_gcp_pos = self.world_to_screen_pixels(world_gcp_pos)
             # painter.drawEllipse(screen_gcp_pos, 3, 3)

        painter.end()

    # --- Mouse Event Handlers ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_pan_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._last_pan_pos is not None:
            delta = event.position() - self._last_pan_pos
            self._last_pan_pos = event.position()

            # Pan the map by adjusting the center pixel coordinates
            self.center_pixel_x -= delta.x()
            self.center_pixel_y -= delta.y()
            self.update() # Trigger redraw
            event.accept()
        else:
            # TODO: Show coordinates in status bar?
            # world_pos = self.screen_to_world_pixels(event.position())
            # print(f"Mouse World Pos: {world_pos.x():.2f}, {world_pos.y():.2f} | Zoom: {self.zoom}")
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._last_pan_pos is not None:
            self._last_pan_pos = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        # Zoom Factor
        zoom_factor = 1.2
        delta = event.angleDelta().y()

        # Mouse position before zoom (in world pixels)
        mouse_screen_pos = event.position()
        mouse_world_pos_before = self.screen_to_world_pixels(mouse_screen_pos)

        if delta > 0:
            # Zoom In
            new_zoom = min(18, self.zoom + 1) # Limit max zoom
            scale_change = 2**(new_zoom - self.zoom)
        elif delta < 0:
            # Zoom Out
            new_zoom = max(0, self.zoom - 1) # Limit min zoom
            scale_change = 2**(new_zoom - self.zoom)
        else:
            return # No change

        if new_zoom != self.zoom:
            # Update zoom level
            self.zoom = new_zoom

            # Update center point to keep mouse position fixed relative to the world
            # New center = mouse_world + (old_center - mouse_world) / scale_change
            # Since we store center in pixels at the *current* zoom, we scale the old center
            old_center_world = QPointF(self.center_pixel_x, self.center_pixel_y)

            # Calculate the new world pixel coordinates for the center
            new_center_x = mouse_world_pos_before.x() + (old_center_world.x() - mouse_world_pos_before.x()) / scale_change
            new_center_y = mouse_world_pos_before.y() + (old_center_world.y() - mouse_world_pos_before.y()) / scale_change

            self.center_pixel_x = new_center_x
            self.center_pixel_y = new_center_y

            # Clear existing tile images as they are for the wrong zoom level
            # self.tile_layer.clear() # Keep tiles for potential reuse if panning back?
            self.update() # Trigger redraw

        event.accept()

# Main Application Window
class GeoreferenceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Georeferencing Tool")
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        # Central Widget (Map View)
        self.map_view = MapViewWidget()

        # --- Docks ---
        self.create_layer_dock()
        self.create_gcp_dock()
        self.create_transform_dock()

        # --- Layout ---
        main_widget = QWidget() # Central widget to hold map view if docks aren't central
        layout = QVBoxLayout(main_widget)
        layout.addWidget(self.map_view)
        # If you want docks around a central map view, set it as CentralWidget
        self.setCentralWidget(self.map_view) # Make map view the central area

        # --- Menu Bar (Example) ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")
        open_action = file_menu.addAction("&Open Image...")
        open_action.triggered.connect(self.open_image) # Connect later
        # TODO: Add Open Tileset, Save GCPs, Export Georeferenced Image actions

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # TODO: Connect signals/slots between widgets

    def create_layer_dock(self):
        dock = QDockWidget("Layers", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        layer_widget = QWidget()
        layout = QVBoxLayout(layer_widget)

        # --- Image Layer ---
        img_group = QGroupBox("Image Layer")
        img_layout = QVBoxLayout(img_group)
        # TODO: Add controls specific to image layer if needed (e.g., path display)
        img_visible_cb = QCheckBox("Visible")
        img_visible_cb.setChecked(True)
        img_layout.addWidget(img_visible_cb)
        img_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        img_opacity_slider.setValue(100)
        img_layout.addWidget(QLabel("Opacity:"))
        img_layout.addWidget(img_opacity_slider)
        layout.addWidget(img_group)

        # --- Tile Layer ---
        tile_group = QGroupBox("Tile Layer")
        tile_layout = QVBoxLayout(tile_group)

        self.tile_visible_cb = QCheckBox("Visible")
        self.tile_visible_cb.setChecked(self.map_view.tile_visible) # Init from map_view state
        tile_layout.addWidget(self.tile_visible_cb)

        tile_layout.addWidget(QLabel("XYZ Tile URL Template:"))
        self.tile_url_input = QLineEdit()
        self.tile_url_input.setPlaceholderText("e.g., https://.../{z}/{x}/{y}.png")
        tile_layout.addWidget(self.tile_url_input)

        cache_layout = QHBoxLayout()
        cache_layout.addWidget(QLabel("Cache Duration (days):"))
        self.cache_duration_spin = QSpinBox()
        self.cache_duration_spin.setRange(0, 365) # 0 to 1 year
        self.cache_duration_spin.setValue(1) # Default 1 day
        # TODO: Get initial value from cache settings if possible?
        cache_layout.addWidget(self.cache_duration_spin)
        cache_layout.addStretch()
        tile_layout.addLayout(cache_layout)

        apply_tile_settings_button = QPushButton("Apply Tile Settings")
        tile_layout.addWidget(apply_tile_settings_button)

        tile_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        tile_opacity_slider.setValue(100)
        tile_layout.addWidget(QLabel("Opacity:")) # Opacity not implemented yet
        tile_layout.addWidget(tile_opacity_slider)
        tile_opacity_slider.setEnabled(False) # Disable until implemented

        layout.addWidget(tile_group)


        layout.addStretch()
        dock.setWidget(layer_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        # --- Connect Layer Signals ---
        # TODO: Connect image layer controls
        self.tile_visible_cb.stateChanged.connect(
            lambda state: self.map_view.set_tile_visibility(state == Qt.CheckState.Checked.value)
        )
        apply_tile_settings_button.clicked.connect(self.apply_tile_settings)
        # TODO: Connect opacity sliders when implemented

    def create_gcp_dock(self):
        dock = QDockWidget("Ground Control Points (GCPs)", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        gcp_widget = QWidget()
        layout = QVBoxLayout(gcp_widget)

        # TODO: Replace with QTableView and a model (QAbstractTableModel)
        self.gcp_table = QTableView()
        layout.addWidget(self.gcp_table)

        input_layout = QHBoxLayout()
        # TODO: Add input fields for Image X/Y, Map X/Y and an "Add GCP" button
        input_layout.addWidget(QLabel("ImgX:"))
        img_x_spin = QDoubleSpinBox()
        input_layout.addWidget(img_x_spin)
        # ... add ImgY, MapX, MapY ...
        add_gcp_button = QPushButton("Add Manually")
        input_layout.addWidget(add_gcp_button)
        layout.addLayout(input_layout)

        # TODO: Add buttons for "Remove Selected GCP", "Load GCPs", "Save GCPs"

        dock.setWidget(gcp_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        # TODO: Connect signals (add button, table selection changes)

    def create_transform_dock(self):
        dock = QDockWidget("Transformation", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        transform_widget = QWidget()
        layout = QVBoxLayout(transform_widget)

        algo_label = QLabel("Algorithm:")
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Polynomial (Order 1)", "Polynomial (Order 2)", "Thin Plate Spline"]) # Add more
        layout.addWidget(algo_label)
        layout.addWidget(self.algo_combo)

        weighting_label = QLabel("GCP Weighting:")
        self.weighting_combo = QComboBox()
        self.weighting_combo.addItems(["None", "Inverse Distance"]) # Add more
        layout.addWidget(weighting_label)
        layout.addWidget(self.weighting_combo)

        self.preview_cb = QCheckBox("Real-time Preview")
        layout.addWidget(self.preview_cb)

        layout.addStretch()
        dock.setWidget(transform_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock) # Add below GCP dock

        # Connect signals
        self.preview_cb.stateChanged.connect(lambda state: self.map_view.set_preview(state == Qt.CheckState.Checked.value))
        # TODO: Connect algorithm/weighting changes to update transformation

    def apply_tile_settings(self):
        """Applies the URL and cache duration from the UI to the MapViewWidget."""
        url = self.tile_url_input.text()
        duration = self.cache_duration_spin.value()
        self.map_view.set_cache_duration(duration) # Set cache duration first
        self.map_view.set_tile_url(url) # Then set URL (triggers redraw)
        self.status_bar.showMessage(f"Tile settings applied. Cache duration: {duration} days.", 5000)


    def open_image(self):
        # TODO: Implement file dialog to select image
        from PyQt6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.bmp *.tif *.tiff)")
        if file_path:
           self.map_view.load_image(file_path)
           self.status_bar.showMessage(f"Image loaded: {file_path}", 5000)
        # print("Open image action triggered (implement file dialog)")
        # Example: Load a dummy path
        # self.map_view.load_image("path/to/your/image.tif")


if __name__ == '__main__':
    # Ensure QApplication is created before any QWidgets
    app = QApplication(sys.argv)
    main_window = GeoreferenceApp()
    main_window.show()
    sys.exit(app.exec())