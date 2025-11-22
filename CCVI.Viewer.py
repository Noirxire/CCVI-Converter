import sys
import json
import math
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QWheelEvent

class CCVIViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCVI File Viewer")
        self.resize(800, 600)
        
        self.ccvi_data = None
        self.zoom_factor = 1.0
        self.show_vectors = True
        self.vector_size = 2
        
        # Caching
        self.original_pixmap = None  # Base rendered image at 100%
        self.display_pixmap = None   # Currently displayed (zoomed) version
        self.needs_rerender = True   # Flag to track when we need to redraw
        
        # Animation
        self.animation_timer = QTimer()
        self.animation_phase = 0
        self.is_animating = False
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for controls
        control_panel = QWidget()
        control_panel.setFixedWidth(200)
        control_layout = QVBoxLayout(control_panel)
        
        self.btn_open = QPushButton("Open CCVI File")
        self.file_label = QLabel("No file loaded")
        self.file_label.setWordWrap(True)
        
        zoom_layout = QHBoxLayout()
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")
        self.btn_reset = QPushButton("1:1")
        self.zoom_label = QLabel("100%")
        zoom_layout.addWidget(self.btn_zoom_out)
        zoom_layout.addWidget(self.btn_reset)
        zoom_layout.addWidget(self.btn_zoom_in)
        zoom_layout.addWidget(self.zoom_label)
        
        self.coord_label = QLabel("Coordinates: (0, 0)")
        
        # Vector display controls
        self.vector_toggle = QCheckBox("Show Vectors")
        self.vector_toggle.setChecked(True)
        
        vector_size_layout = QHBoxLayout()
        vector_size_layout.addWidget(QLabel("Vector Size:"))
        self.vector_size_spin = QSpinBox()
        self.vector_size_spin.setRange(1, 10)
        self.vector_size_spin.setValue(2)
        vector_size_layout.addWidget(self.vector_size_spin)
        
        self.animate_toggle = QCheckBox("Animate Vectors")
        
        # Info display
        self.info_label = QLabel("Image info will appear here")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-family: monospace;")
        
        control_layout.addWidget(self.btn_open)
        control_layout.addWidget(self.file_label)
        control_layout.addLayout(zoom_layout)
        control_layout.addWidget(self.coord_label)
        control_layout.addStretch()
        control_layout.addWidget(self.vector_toggle)
        control_layout.addLayout(vector_size_layout)
        control_layout.addWidget(self.animate_toggle)
        control_layout.addStretch()
        control_layout.addWidget(self.info_label)
        
        # Image display area
        self.image_display = QLabel()
        self.image_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_display.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        self.image_display.setMinimumSize(400, 300)
        
        main_layout.addWidget(control_panel)
        main_layout.addWidget(self.image_display, 1)
    
    def setup_connections(self):
        self.btn_open.clicked.connect(self.open_file)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_reset.clicked.connect(self.reset_view)
        self.vector_toggle.toggled.connect(self.on_vector_toggle)
        self.vector_size_spin.valueChanged.connect(self.on_vector_size_change)
        self.animate_toggle.toggled.connect(self.on_animation_toggle)
        self.animation_timer.timeout.connect(self.on_animation_frame)
    
    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open CCVI File", "", "CCVI Files (*.ccvi)"
        )
        if file_path:
            self.load_ccvi_file(file_path)
    
    def load_ccvi_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                self.ccvi_data = json.load(f)
            
            self.file_label.setText(f"Loaded: {Path(file_path).name}")
            self.reset_view()
            self.update_info()
            # Force a full rerender
            self.needs_rerender = True
            self.render_image()
        except Exception as e:
            self.file_label.setText(f"Error loading file: {str(e)}")
    
    def update_info(self):
        if not self.ccvi_data:
            return
        
        total_vectors = sum(len(plane['vectors']) for plane in self.ccvi_data['planes'])
        info_text = f"""Dimensions: {self.ccvi_data['width']} x {self.ccvi_data['height']}
Planes: {len(self.ccvi_data['planes'])}
Vectors: {total_vectors}
Margin: {self.ccvi_data.get('margin_error', 'N/A')}"""
        self.info_label.setText(info_text)
    
    def render_image(self):
        """Smart rendering - only redraw base image if necessary, otherwise just scale"""
        if not self.ccvi_data:
            return
        
        # Only redraw the base image if something fundamental changed
        if self.needs_rerender or self.original_pixmap is None:
            self.render_base_image()
            self.needs_rerender = False
        
        # Apply zoom to create display pixmap (this is cheap)
        self.apply_zoom()
    
    def render_base_image(self):
        """Render the base image at 100% scale - this is the expensive operation"""
        width = self.ccvi_data['width']
        height = self.ccvi_data['height']
        
        # Create image
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background
        painter.fillRect(0, 0, width, height, QColor(240, 240, 240))
        
        # Draw color planes
        for plane in self.ccvi_data['planes']:
            color = QColor(*plane['color'])
            
            for vec in plane['vectors']:
                x, y = vec['x'], vec['y']
                alpha = int(vec.get('alpha', 1.0) * 255)
                color.setAlpha(alpha)
                
                if self.show_vectors:
                    # Draw vector points
                    size = self.vector_size
                    if self.is_animating:
                        # Subtle pulsing for animation
                        pulse = math.sin(self.animation_phase) * 0.3 + 0.7
                        animated_size = max(1, int(size * pulse))
                    else:
                        animated_size = size
                    
                    painter.setPen(QPen(color, 1))
                    painter.setBrush(color)
                    painter.drawEllipse(x - animated_size//2, y - animated_size//2, 
                                      animated_size, animated_size)
                else:
                    # Simple pixel
                    painter.setPen(color)
                    painter.drawPoint(x, y)
        
        painter.end()
        self.original_pixmap = QPixmap.fromImage(image)
    
    def apply_zoom(self):
        """Apply zoom transformation - this is cheap"""
        if self.original_pixmap is None:
            return
        
        if self.zoom_factor == 1.0:
            # No zoom, use original
            self.display_pixmap = self.original_pixmap
        else:
            # Scale the original pixmap
            scaled_width = int(self.original_pixmap.width() * self.zoom_factor)
            scaled_height = int(self.original_pixmap.height() * self.zoom_factor)
            self.display_pixmap = self.original_pixmap.scaled(
                scaled_width, scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        self.image_display.setPixmap(self.display_pixmap)
        self.zoom_label.setText(f"{int(self.zoom_factor * 100)}%")
    
    def zoom_in(self):
        self.zoom_factor = min(10.0, self.zoom_factor * 1.2)
        self.apply_zoom()  # Just apply zoom, no rerender needed
    
    def zoom_out(self):
        self.zoom_factor = max(0.1, self.zoom_factor / 1.2)
        self.apply_zoom()  # Just apply zoom, no rerender needed
    
    def reset_view(self):
        self.zoom_factor = 1.0
        self.apply_zoom()
    
    def on_vector_toggle(self, checked):
        self.show_vectors = checked
        self.needs_rerender = True  # Need to redraw base image
        self.render_image()
    
    def on_vector_size_change(self, size):
        self.vector_size = size
        self.needs_rerender = True  # Need to redraw base image
        self.render_image()
    
    def on_animation_toggle(self, checked):
        self.is_animating = checked
        if checked:
            self.animation_timer.start(100)  # 10 FPS - much gentler
        else:
            self.animation_timer.stop()
            # Only rerender if we were animating and now we're not
            if not checked:
                self.needs_rerender = True
                self.render_image()
    
    def on_animation_frame(self):
        """Animation frame - only update phase and rerender if needed"""
        self.animation_phase += 0.1
        if self.animation_phase > 2 * math.pi:
            self.animation_phase = 0
        
        if self.is_animating:
            self.needs_rerender = True
            self.render_image()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = CCVIViewer()
    viewer.show()
    sys.exit(app.exec())