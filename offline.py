import sys
import math
import json
import random
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QSlider,
    QListWidget,
    QMessageBox,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView

# ==========================================
# OFFLINE MAP HTML (No External Dependencies)
# ==========================================
HTML_CONTENT = """<!DOCTYPE html>
<html>
<head>
    <meta charset=\"utf-8\">
    <title>Mission Simulator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body { height: 100%; width: 100%; overflow: hidden; background: #1a1a2e; }
        #map {
            width: 100%; height: 100%;
            background: linear-gradient(135deg, #1a3a52 0%, #0d1b2a 50%, #1a1a2e 100%);
            position: relative;
        }
        .grid-line { position: absolute; border-color: rgba(0, 217, 255, 0.1); border-style: solid; }
        .path-point {
            position: absolute; width: 12px; height: 12px;
            background: cyan; border-radius: 50%;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 10px cyan;
        }
        .path-line {
            position: absolute;
            background: cyan;
            height: 3px;
            box-shadow: 0 0 5px cyan;
            transform-origin: 0 50%;
            z-index: 5;
        }
        .emitter-marker {
            position: absolute; width: 28px; height: 28px;
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
            transform: translate(-50%, -50%);
            cursor: move;
        }
        .aircraft-marker {
            position: absolute; width: 32px; height: 32px;
            background: url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"%23ffb703\"><path d=\"M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z\"/></svg>') no-repeat center;
            background-size: contain;
            transform: translate(-50%, -50%);
            transition: all 0.1s linear;
        }
        #live-coords {
            position: absolute;
            right: 14px;
            bottom: 14px;
            z-index: 30;
            background: rgba(10, 18, 32, 0.85);
            border: 1px solid rgba(0, 217, 255, 0.5);
            border-radius: 6px;
            color: #d9f7ff;
            font: 12px/1.4 monospace;
            padding: 8px 10px;
            min-width: 220px;
            text-align: left;
            box-shadow: 0 0 10px rgba(0, 217, 255, 0.2);
        }
        .emitter-id { color: #ffffff; font-weight: bold; }
        .lat-label { color: #8be9fd; }
        .lat-val { color: #00f5ff; font-weight: bold; }
        .lng-label { color: #fca5a5; margin-left: 6px; }
        .lng-val { color: #ff6b6b; font-weight: bold; }
    </style>
</head>
<body>
    <div id=\"map\"></div>
    <div id=\"live-coords\">Emitters: none</div>
    <script>
        var mapEl = document.getElementById('map');
        var coordsEl = document.getElementById('live-coords');
        var pathPoints = [];
        var emitters = {};
        var isDraggingEmitter = null;
        var dragOffset = {x: 0, y: 0};
        var EMITTER_COLORS = ['#ef476f', '#06d6a0', '#ffd166', '#118ab2', '#f3722c', '#9b5de5'];
        var EMITTER_ICON_TEMPLATES = [
            '<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 28 28\"><circle cx=\"14\" cy=\"14\" r=\"11\" fill=\"{color}\"/><circle cx=\"14\" cy=\"14\" r=\"4\" fill=\"#0b1320\"/></svg>',
            '<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 28 28\"><rect x=\"4\" y=\"4\" width=\"20\" height=\"20\" rx=\"3\" fill=\"{color}\"/><rect x=\"10\" y=\"10\" width=\"8\" height=\"8\" fill=\"#0b1320\"/></svg>',
            '<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 28 28\"><polygon points=\"14,2 26,14 14,26 2,14\" fill=\"{color}\"/><circle cx=\"14\" cy=\"14\" r=\"3.8\" fill=\"#0b1320\"/></svg>',
            '<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 28 28\"><polygon points=\"14,2 17.5,10 26,10.5 19.5,16 21.8,25 14,20.5 6.2,25 8.5,16 2,10.5 10.5,10\" fill=\"{color}\"/></svg>'
        ];

        function emitterIconDataUri(id) {
            var color = EMITTER_COLORS[(id - 1) % EMITTER_COLORS.length];
            var template = EMITTER_ICON_TEMPLATES[(id - 1) % EMITTER_ICON_TEMPLATES.length];
            var svg = template.replace('{color}', color);
            return \"url('data:image/svg+xml;utf8,\" + encodeURIComponent(svg) + \"')\";
        }

        function updateEmitterCoordsPanel() {
            var ids = Object.keys(emitters).sort(function(a, b) { return Number(a) - Number(b); });
            if (!ids.length) {
                coordsEl.innerHTML = 'Emitters: none';
                return;
            }
            var lines = ids.map(function(id) {
                var m = emitters[id];
                return (
                    '<span class=\"emitter-id\">E' + id + '</span> ' +
                    '<span class=\"lat-label\">Lat</span>: ' +
                    '<span class=\"lat-val\">' + Number(m.dataset.lat).toFixed(6) + '</span> ' +
                    '<span class=\"lng-label\">Lng</span>: ' +
                    '<span class=\"lng-val\">' + Number(m.dataset.lng).toFixed(6) + '</span>'
                );
            });
            coordsEl.innerHTML = lines.join('<br>');
        }

        // Convert lat/lng to pixel (simple projection)
        function latLngToPixel(lat, lng) {
            var x = (lng + 180) * (mapEl.offsetWidth / 360);
            var y = ((90 - lat) * (mapEl.offsetHeight / 180));
            return {x: x, y: y};
        }

        // Convert pixel to lat/lng
        function pixelToLatLng(x, y) {
            var lng = (x / (mapEl.offsetWidth / 360)) - 180;
            var lat = 90 - (y / (mapEl.offsetHeight / 180));
            return {lat: lat, lng: lng};
        }

        // Right click to add path point
        mapEl.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            var rect = mapEl.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var y = e.clientY - rect.top;
            pathPoints.push({x: x, y: y});
            renderPath();
        });

        // Render path
        function renderPath() {
            document.querySelectorAll('.path-point').forEach(el => el.remove());
            document.querySelectorAll('.path-line').forEach(el => el.remove());

            if (pathPoints.length > 1) {
                for (var i = 0; i < pathPoints.length - 1; i++) {
                    var line = document.createElement('div');
                    line.className = 'path-line';
                    var p1 = pathPoints[i];
                    var p2 = pathPoints[i + 1];
                    var length = Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
                    var angle = Math.atan2(p2.y - p1.y, p2.x - p1.x) * 180 / Math.PI;
                    line.style.left = p1.x + 'px';
                    line.style.top = p1.y + 'px';
                    line.style.width = length + 'px';
                    line.style.height = '3px';
                    line.style.background = 'cyan';
                    line.style.boxShadow = '0 0 5px cyan';
                    line.style.transformOrigin = '0 50%';
                    line.style.transform = 'rotate(' + angle + 'deg)';
                    line.style.zIndex = '5';
                    mapEl.appendChild(line);
                }
            }

            pathPoints.forEach(function(p) {
                var point = document.createElement('div');
                point.className = 'path-point';
                point.style.left = p.x + 'px';
                point.style.top = p.y + 'px';
                point.style.zIndex = '10';
                mapEl.appendChild(point);
            });
        }

        // Add emitter
        function addEmitter(id, lat, lng) {
            var pos = latLngToPixel(lat, lng);
            var marker = document.createElement('div');
            marker.className = 'emitter-marker';
            marker.id = 'emitter-' + id;
            marker.style.backgroundImage = emitterIconDataUri(Number(id));
            marker.style.left = pos.x + 'px';
            marker.style.top = pos.y + 'px';
            marker.style.zIndex = '15';
            marker.dataset.id = id;
            marker.dataset.lat = lat;
            marker.dataset.lng = lng;

            marker.addEventListener('mousedown', function(e) {
                isDraggingEmitter = id;
                var rect = mapEl.getBoundingClientRect();
                var currentX = parseFloat(marker.style.left);
                var currentY = parseFloat(marker.style.top);
                dragOffset.x = e.clientX - rect.left - currentX;
                dragOffset.y = e.clientY - rect.top - currentY;
            });

            mapEl.appendChild(marker);
            emitters[id] = marker;
            updateEmitterCoordsPanel();
        }

        // Mouse move for dragging
        document.addEventListener('mousemove', function(e) {
            if (isDraggingEmitter) {
                var rect = mapEl.getBoundingClientRect();
                var x = e.clientX - rect.left - dragOffset.x;
                var y = e.clientY - rect.top - dragOffset.y;

                var marker = emitters[isDraggingEmitter];
                marker.style.left = x + 'px';
                marker.style.top = y + 'px';

                var latlng = pixelToLatLng(x, y);
                marker.dataset.lat = latlng.lat;
                marker.dataset.lng = latlng.lng;
                updateEmitterCoordsPanel();
            }
        });

        // Mouse up
        document.addEventListener('mouseup', function() {
            if (isDraggingEmitter) {
                isDraggingEmitter = null;
            }
        });

        // Move aircraft
        function moveAircraft(lat, lng, bearing) {
            var pos = latLngToPixel(lat, lng);
            var marker = document.getElementById('aircraft-marker');
            if (!marker) {
                marker = document.createElement('div');
                marker.id = 'aircraft-marker';
                marker.className = 'aircraft-marker';
                marker.style.zIndex = '20';
                mapEl.appendChild(marker);
            }
            marker.style.left = pos.x + 'px';
            marker.style.top = pos.y + 'px';
            marker.style.transform = 'translate(-50%, -50%) rotate(' + bearing + 'deg)';
        }

        // Clear map
        function clearMapData() {
            pathPoints = [];
            document.querySelectorAll('.path-point').forEach(el => el.remove());
            document.querySelectorAll('.path-line').forEach(el => el.remove());
            var aircraft = document.getElementById('aircraft-marker');
            if (aircraft) aircraft.remove();
        }

        // Remove all emitters
        function removeAllEmitters() {
            for (var id in emitters) {
                emitters[id].remove();
            }
            emitters = {};
            updateEmitterCoordsPanel();
        }

        // Get path points as lat/lng
        function getPathPoints() {
            var latlngs = pathPoints.map(function(p) {
                return pixelToLatLng(p.x, p.y);
            });
            return JSON.stringify(latlngs);
        }

        // Generate grid
        function generateGrid() {
            var w = mapEl.offsetWidth;
            var h = mapEl.offsetHeight;

            for (var i = 0; i <= 6; i++) {
                var vLine = document.createElement('div');
                vLine.className = 'grid-line';
                vLine.style.left = (i * w / 6) + 'px';
                vLine.style.top = '0px';
                vLine.style.width = '1px';
                vLine.style.height = h + 'px';
                mapEl.appendChild(vLine);

                var hLine = document.createElement('div');
                hLine.className = 'grid-line';
                hLine.style.left = '0px';
                hLine.style.top = (i * h / 6) + 'px';
                hLine.style.width = w + 'px';
                hLine.style.height = '1px';
                mapEl.appendChild(hLine);
            }
        }

        generateGrid();
        console.log('MAP_READY');
    </script>
</body>
</html>
"""


class MissionSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mission Simulator - Offline")
        self.setGeometry(100, 100, 1400, 800)
        self.setStyleSheet("background-color: #1a1a2e;")

        # Data
        self.path_coords = []
        self.emitters = {}
        self.emitter_id_counter = 1
        self.is_playing = False
        self.current_path_index = 0
        self.segment_index = 0
        self.segment_progress_km = 0.0
        self.current_position = None
        self.aircraft_bearing = 0
        self.time_acceleration = 200000.0
        self.page_loaded = False

        # Timer for simulation
        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self.update_simulation)

        self.init_ui()

        # WebView for map
        self.web_view = QWebEngineView()
        self.web_view.setHtml(HTML_CONTENT)
        self.web_view.loadFinished.connect(self.on_load_finished)

        # Layout
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        main_layout.addWidget(self.left_panel, 1)
        main_layout.addWidget(self.web_view, 4)

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def init_ui(self):
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("background-color: #1a1a2e; color: white; border-right: 2px solid #0f3460;")
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 20)

        # Title
        title = QLabel("MISSION SIMULATOR")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #00d9ff; margin-bottom: 15px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Status
        self.status_label = QLabel("Loading map...")
        self.status_label.setStyleSheet("color: yellow; font-size: 12px; padding: 5px; background: #16213e; border-radius: 3px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Instructions
        info = QLabel(
            "INSTRUCTIONS:\n\n"
            "1. RIGHT-CLICK on map to draw path\n\n"
            "2. Click 'Add Emitter' to place radar\n\n"
            "3. Drag emitters on map to reposition\n\n"
            "4. Adjust speed and press PLAY"
        )
        info.setStyleSheet("background-color: #16213e; padding: 12px; border-radius: 5px; font-size: 11px; line-height: 1.8;")
        layout.addWidget(info)

        # Emitter Section
        lbl_emitter = QLabel("RADAR EMITTERS")
        lbl_emitter.setStyleSheet("font-weight: bold; color: #e94560; font-size: 14px;")
        layout.addWidget(lbl_emitter)

        self.btn_add_emitter = QPushButton("+ Add Radar Emitter")
        self.btn_add_emitter.setStyleSheet("""
            background-color: #0f3460;
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-weight: bold;
        """)
        self.btn_add_emitter.clicked.connect(self.add_emitter)
        layout.addWidget(self.btn_add_emitter)

        input_row = QHBoxLayout()
        self.input_lat = QLineEdit()
        self.input_lat.setPlaceholderText("Latitude (-90 to 90)")
        self.input_lat.setStyleSheet(
            "background-color: #16213e; color: #8be9fd; border: 1px solid #0f3460; border-radius: 4px; padding: 6px;"
        )
        input_row.addWidget(self.input_lat)

        self.input_lng = QLineEdit()
        self.input_lng.setPlaceholderText("Longitude (-180 to 180)")
        self.input_lng.setStyleSheet(
            "background-color: #16213e; color: #ff9f9f; border: 1px solid #0f3460; border-radius: 4px; padding: 6px;"
        )
        input_row.addWidget(self.input_lng)
        layout.addLayout(input_row)

        self.emitter_list = QListWidget()
        self.emitter_list.setStyleSheet("""
            background-color: #16213e;
            color: white;
            border-radius: 5px;
            border: 1px solid #0f3460;
        """)
        self.emitter_list.setMaximumHeight(120)
        layout.addWidget(self.emitter_list)

        # Speed
        lbl_speed = QLabel("SPEED CONTROL")
        lbl_speed.setStyleSheet("font-weight: bold; color: #e94560; font-size: 14px; margin-top: 15px;")
        layout.addWidget(lbl_speed)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(1)
        self.speed_slider.setMaximum(50)
        self.speed_slider.setValue(10)
        self.speed_slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #16213e; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #00d9ff; width: 18px; margin: -5px 0; border-radius: 9px; }
        """)
        self.speed_slider.valueChanged.connect(self.update_speed_label)
        layout.addWidget(self.speed_slider)

        self.lbl_speed = QLabel("Speed: 10 km/h")
        self.lbl_speed.setStyleSheet("color: #00d9ff; font-weight: bold; text-align: center; font-size: 14px;")
        self.lbl_speed.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_speed)

        layout.addStretch()

        # Buttons
        self.btn_play = QPushButton("PLAY")
        self.btn_play.setStyleSheet("""
            background-color: #00d9ff;
            color: #1a1a2e;
            font-weight: bold;
            padding: 15px;
            border-radius: 8px;
            font-size: 16px;
        """)
        self.btn_play.clicked.connect(self.toggle_play)
        layout.addWidget(self.btn_play)

        self.btn_delete = QPushButton("RESET ALL")
        self.btn_delete.setStyleSheet("""
            background-color: #e94560;
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            margin-top: 10px;
        """)
        self.btn_delete.clicked.connect(self.reset_simulation)
        layout.addWidget(self.btn_delete)

        self.left_panel.setLayout(layout)

    def on_load_finished(self, ok):
        if ok:
            self.status_label.setText("Map ready")
            self.status_label.setStyleSheet("color: #00ff9c; font-size: 12px;")
            self.page_loaded = True

    # ---------------------------
    # UI Callbacks
    # ---------------------------

    def update_speed_label(self, value):
        self.lbl_speed.setText(f"Speed: {value} km/h")

    def _simulation_interval_ms(self):
        # Use a fixed tick for smooth movement; speed controls distance per tick.
        return 50

    @staticmethod
    def _haversine_km(p1, p2):
        r = 6371.0
        lat1 = math.radians(p1["lat"])
        lat2 = math.radians(p2["lat"])
        d_lat = lat2 - lat1
        d_lng = math.radians(p2["lng"] - p1["lng"])
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
        )
        return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def _bearing_deg(p1, p2):
        dy = p2["lat"] - p1["lat"]
        dx = p2["lng"] - p1["lng"]
        return math.degrees(math.atan2(dx, dy))

    @staticmethod
    def _interpolate(p1, p2, t):
        return {
            "lat": p1["lat"] + (p2["lat"] - p1["lat"]) * t,
            "lng": p1["lng"] + (p2["lng"] - p1["lng"]) * t,
        }

    def add_emitter(self):
        if not self.page_loaded:
            return

        emitter_id = self.emitter_id_counter
        self.emitter_id_counter += 1

        lat_text = self.input_lat.text().strip()
        lng_text = self.input_lng.text().strip()
        if not lat_text and not lng_text:
            lat = random.uniform(-30, 30)
            lng = random.uniform(-60, 60)
        else:
            try:
                lat = float(lat_text)
                lng = float(lng_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Input", "Latitude/Longitude must be numeric values.")
                return
            if not (-90 <= lat <= 90):
                QMessageBox.warning(self, "Invalid Latitude", "Latitude must be between -90 and 90.")
                return
            if not (-180 <= lng <= 180):
                QMessageBox.warning(self, "Invalid Longitude", "Longitude must be between -180 and 180.")
                return

        self.emitters[emitter_id] = {"lat": lat, "lng": lng}
        self.emitter_list.addItem(f"Emitter {emitter_id}  ({lat:.4f}, {lng:.4f})")
        self.input_lat.clear()
        self.input_lng.clear()

        js = f"addEmitter({emitter_id}, {lat}, {lng});"
        self.web_view.page().runJavaScript(js)

    def toggle_play(self):
        if not self.is_playing:
            self.start_simulation()
        else:
            self.stop_simulation()

    def start_simulation(self):
        if not self.page_loaded:
            QMessageBox.warning(self, "Error", "Map not ready")
            return

        def receive_path(data):
            self.path_coords = json.loads(data)
            if len(self.path_coords) < 2:
                QMessageBox.warning(self, "Error", "Draw a path with at least 2 points")
                return

            self.current_path_index = 0
            self.segment_index = 0
            self.segment_progress_km = 0.0
            self.current_position = {
                "lat": self.path_coords[0]["lat"],
                "lng": self.path_coords[0]["lng"],
            }
            self.aircraft_bearing = self._bearing_deg(
                self.path_coords[0], self.path_coords[1]
            )
            self.is_playing = True
            self.btn_play.setText("PAUSE")
            self.web_view.page().runJavaScript(
                f"moveAircraft({self.current_position['lat']}, {self.current_position['lng']}, {self.aircraft_bearing});"
            )
            self.sim_timer.start(self._simulation_interval_ms())

        self.web_view.page().runJavaScript("getPathPoints();", receive_path)

    def stop_simulation(self):
        self.is_playing = False
        self.sim_timer.stop()
        self.btn_play.setText("PLAY")

    def reset_simulation(self):
        self.stop_simulation()
        self.path_coords.clear()
        self.emitters.clear()
        self.emitter_list.clear()
        self.emitter_id_counter = 1
        self.segment_index = 0
        self.segment_progress_km = 0.0
        self.current_position = None

        self.web_view.page().runJavaScript(
            """
            clearMapData();
            removeAllEmitters();
            """
        )

        self.status_label.setText("Reset complete")
        self.status_label.setStyleSheet("color: yellow; font-size: 12px;")

    # ---------------------------
    # Simulation Engine
    # ---------------------------

    def update_simulation(self):
        if not self.is_playing or not self.path_coords:
            return

        if self.segment_index >= len(self.path_coords) - 1:
            self.stop_simulation()
            return

        dt_hours = self._simulation_interval_ms() / 3_600_000.0
        remaining_km = self.speed_slider.value() * dt_hours * self.time_acceleration
        reached_final = False

        while remaining_km > 0 and self.segment_index < len(self.path_coords) - 1:
            start = self.path_coords[self.segment_index]
            end = self.path_coords[self.segment_index + 1]
            seg_len = max(self._haversine_km(start, end), 1e-9)
            seg_left = seg_len - self.segment_progress_km
            self.aircraft_bearing = self._bearing_deg(start, end)

            if remaining_km >= seg_left:
                remaining_km -= seg_left
                self.segment_index += 1
                self.segment_progress_km = 0.0
                self.current_position = {"lat": end["lat"], "lng": end["lng"]}
                if self.segment_index >= len(self.path_coords) - 1:
                    reached_final = True
                    break
            else:
                self.segment_progress_km += remaining_km
                t = self.segment_progress_km / seg_len
                self.current_position = self._interpolate(start, end, t)
                remaining_km = 0

        if not self.current_position:
            return

        js = (
            f"moveAircraft({self.current_position['lat']}, "
            f"{self.current_position['lng']}, {self.aircraft_bearing});"
        )
        self.web_view.page().runJavaScript(js)

        if reached_final:
            self.stop_simulation()


# ==========================
# APPLICATION ENTRY POINT
# ==========================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MissionSimulator()
    window.show()
    sys.exit(app.exec_())
