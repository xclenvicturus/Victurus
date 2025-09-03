# Complete docking system test - simulates a full station interaction
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QTextEdit
from ui.widgets.actions_panel import ActionsPanel
from ui.dialogs.station_comm_dialog import StationCommDialog
from game import player_status
from data import db

class FullDockingTest(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Complete Docking System Test")
        self.resize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Status display
        self.status_label = QLabel("System Status")
        layout.addWidget(self.status_label)
        
        # Control buttons
        button_layout = QVBoxLayout()
        
        self.find_station_btn = QPushButton("1. Find Station with Facilities")
        self.find_station_btn.clicked.connect(self.find_station)
        button_layout.addWidget(self.find_station_btn)
        
        self.travel_btn = QPushButton("2. Travel to Station")
        self.travel_btn.clicked.connect(self.travel_to_station)
        self.travel_btn.setEnabled(False)
        button_layout.addWidget(self.travel_btn)
        
        self.dock_btn = QPushButton("3. Request Docking (Full Comm Sequence)")
        self.dock_btn.clicked.connect(self.request_docking)
        self.dock_btn.setEnabled(False)
        button_layout.addWidget(self.dock_btn)
        
        layout.addLayout(button_layout)
        
        # Actions panel
        layout.addWidget(QLabel("Available Actions:"))
        self.actions_panel = ActionsPanel()
        self.actions_panel.action_triggered.connect(self.on_action_triggered)
        layout.addWidget(self.actions_panel)
        
        # Log output
        layout.addWidget(QLabel("Activity Log:"))
        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(150)
        layout.addWidget(self.log_output)
        
        # Test data
        self.current_station = None
        self.station_facilities = []
        
        # Initialize
        self.update_status()
        self.log("🔄 Docking system test initialized")
    
    def log(self, message: str):
        """Add message to log output"""
        self.log_output.append(message)
        print(message)  # Also print to console
    
    def update_status(self):
        """Update status display"""
        try:
            status = player_status.get_status_snapshot()
            if status:
                status_text = f"""
Current Status: {status.get('status', 'Unknown')}
Location: {status.get('display_location', 'Unknown')}
System: {status.get('system_name', 'Unknown')}
Location ID: {status.get('location_id', 'None')}
"""
                self.status_label.setText(status_text)
                self.actions_panel.refresh()
            else:
                self.status_label.setText("No status available")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
    
    def find_station(self):
        """Find a station with interesting facilities"""
        try:
            conn = db.get_connection()
            
            # Find stations with the most facilities
            station_data = conn.execute("""
                SELECT l.location_id, l.location_name, l.system_id,
                       COUNT(f.facility_id) as facility_count,
                       GROUP_CONCAT(f.facility_type) as facility_types
                FROM locations l
                LEFT JOIN facilities f ON l.location_id = f.location_id
                WHERE l.location_type = 'station'
                GROUP BY l.location_id
                HAVING facility_count > 0
                ORDER BY facility_count DESC
                LIMIT 5
            """).fetchall()
            
            if not station_data:
                self.log("❌ No stations with facilities found")
                return
            
            # Pick the first one
            self.current_station = station_data[0]
            
            # Get detailed facility info
            facilities = conn.execute("""
                SELECT facility_type, notes
                FROM facilities
                WHERE location_id = ?
            """, (self.current_station['location_id'],)).fetchall()
            
            self.station_facilities = [{'type': f['facility_type'], 'notes': f['notes']} for f in facilities]
            
            station_name = self.current_station['location_name']
            facility_list = [f['facility_type'] for f in facilities]
            
            self.log(f"🎯 Found station: {station_name}")
            self.log(f"   Facilities: {', '.join(facility_list)}")
            
            self.travel_btn.setEnabled(True)
            
        except Exception as e:
            self.log(f"❌ Error finding station: {e}")
    
    def travel_to_station(self):
        """Simulate traveling to the station"""
        if not self.current_station:
            return
        
        try:
            location_id = self.current_station['location_id']
            station_name = self.current_station['location_name']
            
            # Set player location to orbit the station
            player_status.enter_orbit(location_id)
            
            self.log(f"🚀 Traveled to {station_name}")
            self.log(f"   Status: Now orbiting station")
            
            self.update_status()
            self.dock_btn.setEnabled(True)
            
        except Exception as e:
            self.log(f"❌ Error traveling: {e}")
    
    def request_docking(self):
        """Request docking with full communication sequence"""
        if not self.current_station:
            return
        
        try:
            station_name = self.current_station['location_name']
            location_id = self.current_station['location_id']
            
            self.log(f"📡 Requesting docking at {station_name}...")
            
            # Prepare station data for communication dialog
            station_data = {
                'location_id': location_id,
                'facilities': self.station_facilities
            }
            
            # Show communication dialog
            comm_dialog = StationCommDialog(station_name, station_data, self)
            comm_dialog.docking_approved.connect(self.handle_docking_approved)
            comm_dialog.docking_denied.connect(self.handle_docking_denied)
            
            result = comm_dialog.exec()
            
        except Exception as e:
            self.log(f"❌ Error requesting docking: {e}")
    
    def handle_docking_approved(self):
        """Handle successful docking"""
        try:
            if not self.current_station:
                self.log("❌ No current station data")
                return
                
            location_id = self.current_station['location_id']
            station_name = self.current_station['location_name']
            
            # Complete docking in game state
            player_status.dock_at_location(location_id)
            
            self.log(f"✅ Successfully docked at {station_name}")
            self.log(f"   Status: Now docked - station services available")
            
            # Show available facilities
            facility_types = [f['type'] for f in self.station_facilities]
            self.log(f"   Available services: {', '.join(facility_types)}")
            
            self.update_status()
            
        except Exception as e:
            self.log(f"❌ Error completing docking: {e}")
    
    def handle_docking_denied(self, reason: str):
        """Handle docking denial"""
        self.log(f"❌ Docking denied: {reason}")
    
    def on_action_triggered(self, action_name: str, action_data: dict):
        """Handle action triggered from actions panel"""
        context = action_data.get('context', {})
        location_name = context.get('location_name', 'Unknown')
        current_status = context.get('current_status', 'unknown')
        
        self.log(f"⚡ Action: {action_name}")
        self.log(f"   Context: {current_status} at {location_name}")
        
        # Handle specific actions
        if action_name == 'undock':
            try:
                location_id = context.get('location_id')
                if location_id:
                    player_status.enter_orbit(location_id)
                    self.log(f"🚀 Undocked - now orbiting {location_name}")
                    self.update_status()
            except Exception as e:
                self.log(f"❌ Error undocking: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FullDockingTest()
    window.show()
    
    print("Complete Docking System Test")
    print("Follow the numbered buttons to test the full sequence")
    
    app.exec()
