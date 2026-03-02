import socket
import json
import os
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout

from stdatalog_gui.Utils.PlotParams import PlotParams
from stdatalog_gui.Widgets.Plots.PlotHeatmapWidget import PlotHeatmapWidget
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget

class HSDPlotToFWidget(PlotWidget):    
    def __init__(self, controller, comp_name, comp_display_name, plot_params, p_id=0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent)
        self.active_tags = dict()
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format
        self.heatmaps = {}
        self.RESOLUTION_4x4 = 0
        self.RESOLUTION_8x8 = 1
        
        # 1. Load Configuration from \Dev\my_GUI\app_config.json
        try:
            current_file = os.path.abspath(__file__)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            config_path = os.path.join(base_dir, 'app_config.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    self.app_cfg = json.load(f)
                
                # --- NEW DEBUG OUTPUT ---
                tof_cfg = self.app_cfg["network_config"]["sensors"]["VL53L8_ToF"]
                print(f"\n[STREAMER DEBUG] Config loaded from: {config_path}")
                print(f"[STREAMER DEBUG] Port: {tof_cfg['port']} | Rot: {tof_cfg['rotation']*90}°")
                print(f"[STREAMER DEBUG] FlipX: {tof_cfg['flip_x']} | FlipY: {tof_cfg['flip_y']}\n")
            else:
                print(f"[DEBUG] Config NOT FOUND at {config_path}. Using defaults.")
                self.app_cfg = {"network_config": {"sensors": {"VL53L8_ToF": {"port": 12345, "rotation":0, "flip_x":False, "flip_y":False}}}}
        except Exception as e:
            print(f"[DEBUG] Config load error: {e}")
            self.app_cfg = {"network_config": {"sensors": {"VL53L8_ToF": {"port": 12345, "rotation":0, "flip_x":False, "flip_y":False}}}}

        # Clear PlotWidget inherited graphic elements
        for i in reversed(range(self.layout().count())): 
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        heatmaps_shape = (4,4) if plot_params.resolution == self.RESOLUTION_4x4 else (8,8)
        self.t1_out = PlotHeatmapWidget(controller, comp_name, comp_display_name, heatmaps_shape, plot_label="Target 1", p_id=p_id, parent=self)
        
        # 2. DYNAMIC ORIENTATION: Read directly from app_cfg instead of hardcoding
        tof_settings = self.app_cfg["network_config"]["sensors"]["VL53L8_ToF"]
        
        self.t1_out.set_default_rotation(tof_settings.get("rotation", 0))
        self.t1_out.set_default_x_flip(tof_settings.get("flip_x", False))
        self.t1_out.set_default_y_flip(tof_settings.get("flip_y", False))
        
        # 3. VISUAL SYNC: Update the GUI buttons/labels to match the config
        settings = self.t1_out.rois_frame 
        settings.flipped_x_status = tof_settings.get("flip_x", False)
        settings.flipped_y_status = tof_settings.get("flip_y", False)
        
        # Update the button text based on the config labels
        settings.flip_x_label.setText(tof_settings.get("label_x", "Normal"))
        settings.flip_y_label.setText(tof_settings.get("label_y", "Normal"))

        self.t1_out.title_frame.setVisible(False)
        self.heatmaps["target1"] = self.t1_out
        self.t1_out.setMinimumWidth(540)
        
        # ... (rest of your existing layout code remains the same)
        heatmaps_frame = QFrame()
        wdg_layout = QHBoxLayout()
        wdg_layout.addWidget(self.t1_out)
        heatmaps_frame.setLayout(wdg_layout)
        self.contents_frame.layout().addWidget(heatmaps_frame)
    
    @Slot(bool, int) 
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1:
            print("Sensor {} is logging via USB: {}".format(self.comp_name, status))
        super().s_is_logging(status, interface)
    
    def update_plot_characteristics(self, plot_params:PlotParams):
        """ Prevents AttributeError and updates heatmap shape """
        heatmaps_shape = (4,4) if plot_params.resolution == self.RESOLUTION_4x4 else (8,8)
        self.t1_out.update_plot_characteristics(heatmaps_shape)
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format

    def add_data(self, data):
        """ Main data loop: Extraction + UDP + GUI Update """
        if data is None: return

        # --- DATA EXTRACTION ---
        try:
            if self.output_format:
                start_t1_dist_id = self.output_format.get("target_distance").get("start_id")
                start_t1_status_id = self.output_format.get("target_status").get("start_id")
                out_data_step = self.output_format.get("nof_outputs")
                
                t1_data = data[0][start_t1_dist_id::out_data_step]
                t1_status_mask = data[0][start_t1_status_id::out_data_step]
            else:
                # FIXED: Added missing variable definition in fallback mode
                start_t1_dist_id = 4
                start_t1_status_id = 5 # Standard ToF status offset
                t1_data = data[0][start_t1_dist_id::8]
                t1_status_mask = data[0][start_t1_status_id::8]

            # --- UDP STREAMING ---
            if t1_data is not None and len(t1_data) > 0:
                try:
                    # Optimized UDP: No re-importing every frame
                    payload = {"s_id": "VL53L8_ToF", "data": t1_data.tolist()}
                    msg = json.dumps(payload).encode()
                    # Using the port from config or default 5005
                    port = self.app_cfg["network_config"]["sensors"]["VL53L8_ToF"]["port"]
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                        sock.sendto(msg, ("127.0.0.1", port))
                except Exception:
                    pass

            # --- LOCAL GUI UPDATE ---
            # This must be called to see movement in ST GUI
            self.heatmaps["target1"].add_data((t1_data, t1_status_mask))
            
        except Exception as e:
            print(f"Error in add_data: {e}")