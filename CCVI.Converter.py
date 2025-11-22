import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QFileDialog,
    QLineEdit, QVBoxLayout, QHBoxLayout, QSlider
)
from PyQt6.QtCore import Qt
from PIL import Image
import numpy as np

def get_default_save_path(input_path, output_path=None, ext=".ccvi"):
    if output_path:
        return Path(output_path)
    else:
        home = Path.home()
        photos = home / "Pictures"
        os.makedirs(photos, exist_ok=True)
        return photos / (Path(input_path).stem + ext)

def convert_to_ccvi(img_path, save_path=None, margin_error=0.1):
    """
    Simplified gradient vector approximation.
    margin_error: 0.0 -> perfect fidelity, 1.0 -> extreme lossiness
    """
    img = Image.open(img_path).convert("RGBA")
    arr = np.array(img)
    
    colors = np.unique(arr.reshape(-1, arr.shape[2]), axis=0)
    planes = []
    
    for color in colors:
        mask = np.all(arr[:, :, :3] == color[:3], axis=2)
        if not np.any(mask):
            continue
        mask_indices = np.argwhere(mask)
        num_vectors = max(1, int(len(mask_indices) * (1 - margin_error)))
        sampled_indices = mask_indices[::max(1, len(mask_indices)//num_vectors)]
        
        vectors = []
        for y, x in sampled_indices:
            height = arr[y, x, :3].mean() / 255.0  
            saturation = (np.max(arr[y, x, :3]) - np.min(arr[y, x, :3])) / 255.0
            alpha = arr[y, x, 3] / 255.0
            vectors.append({
                "x": int(x),
                "y": int(y),
                "height": float(height),
                "saturation": float(saturation),
                "alpha": float(alpha)
            })
        
        planes.append({
            "color": color[:3].tolist(),
            "vectors": vectors
        })
    
    ccvi_data = {
        "width": img.width,
        "height": img.height,
        "planes": planes,
        "margin_error": margin_error
    }
    
    save_path = get_default_save_path(img_path, save_path, ext=".ccvi")
    with open(save_path, "w") as f:
        json.dump(ccvi_data, f)
    return save_path

def convert_from_ccvi(ccvi_path, save_path=None):
    with open(ccvi_path, "r") as f:
        data = json.load(f)
    
    width, height = data["width"], data["height"]
    canvas = np.zeros((height, width, 4), dtype=np.uint8)
    
    for plane in data["planes"]:
        color = plane["color"]
        for vec in plane["vectors"]:
            x, y = vec["x"], vec["y"]
            canvas[y, x, :3] = color
            canvas[y, x, 3] = int(vec["alpha"] * 255)
    
    if np.any(canvas[:, :, 3] < 255):
        ext = "png"
        img = Image.fromarray(canvas, "RGBA")
    else:
        ext = "jpeg"
        img = Image.fromarray(canvas, "RGBA").convert("RGB")
    
    save_path = get_default_save_path(ccvi_path, save_path, ext=f".{ext}")
    img.save(save_path)
    return save_path

class CCVIConverterUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CCVI Converter")
        self.resize(600, 200)
        
        self.input_file = None
        self.output_path = None
        self.margin_error = 0.1
        
        self.label_file = QLabel("No file selected")
        self.btn_choose = QPushButton("Choose File")
        self.label_output = QLabel("Save location (optional)")
        self.line_output = QLineEdit()
        self.btn_convert = QPushButton("Convert")
        self.status_label = QLabel("")
        self.label_slider = QLabel("Margin of Error: DEVOURER OF DRIVES")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(10)
        
        layout = QVBoxLayout()
        layout.addWidget(self.label_file)
        layout.addWidget(self.btn_choose)
        layout.addWidget(self.label_output)
        layout.addWidget(self.line_output)
        layout.addWidget(self.label_slider)
        layout.addWidget(self.slider)
        layout.addWidget(self.btn_convert)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        
        self.btn_choose.clicked.connect(self.choose_file)
        self.btn_convert.clicked.connect(self.convert)
        self.slider.valueChanged.connect(self.update_slider_label)
    
    def choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image or CCVI file", "", "Images (*.png *.jpg *.jpeg *.bmp);;CCVI (*.ccvi)"
        )
        if file_path:
            self.input_file = file_path
            self.label_file.setText(f"Selected: {file_path}")
    
    def update_slider_label(self):
        val = self.slider.value()
        self.margin_error = val / 100.0
        if val < 25:
            text = "DEVOURER OF DRIVES"
        elif val < 75:
            text = "POBODY'S NERFECT"
        else:
            text = "MUDDLED HELL"
        self.label_slider.setText(f"Margin of Error: {text}")
    
    def convert(self):
        if not self.input_file:
            self.status_label.setText("No file selected!")
            return
        self.output_path = self.line_output.text() or None
        try:
            ext = Path(self.input_file).suffix.lower()
            if ext == ".ccvi":
                saved = convert_from_ccvi(self.input_file, self.output_path)
            else:
                saved = convert_to_ccvi(self.input_file, self.output_path, self.margin_error)
            self.status_label.setText(f"Saved: {saved}")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

# -------------------
# Run App
# -------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CCVIConverterUI()
    window.show()
    sys.exit(app.exec())
