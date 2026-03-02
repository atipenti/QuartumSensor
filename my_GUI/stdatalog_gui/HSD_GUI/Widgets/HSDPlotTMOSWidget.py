from stdatalog_gui.Utils.PlotParams import SensorPresenscePlotParams
from stdatalog_gui.Widgets.Plots.PlotWidget import PlotWidget
from stdatalog_gui.HSD_GUI.Widgets.HSDPlotLinesTMOSWidget import HSDPlotLinesTMOSWidget


# Php 20260301 - add for UDP broadcaster
import json
import os
try:
    from udp_broadcaster import UDPBroadcaster
except ImportError:
    UDPBroadcaster = None
#end of

class HSDPlotTMOSWidget(PlotWidget):
    def __init__(self, controller, comp_name, comp_display_name, plot_params, p_id = 0, parent=None):
        super().__init__(controller, comp_name, comp_display_name, p_id, parent, "")
        
        
        # --- ADD THIS DEBUG LINE HERE ---
        print(f"DEBUG1: The TMOS sensor name is: '{comp_name}'")
        # --------------------------------
        self.graph_curves = dict()
        self.one_t_interval_resampled = dict()

        self.graph_widget.deleteLater()

        self.plots_params = plot_params

        # Php 20260301 - add for UDP broadcaster
        # Load app_config for UDP port info
        try:
            current_file = os.path.abspath(__file__)
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
            config_path = os.path.join(base_dir, 'app_config.json')
            with open(config_path, 'r') as f:
                self.app_cfg = json.load(f)
                print(f"✅ [TMOS WIDGET] Loaded app_config from: {config_path}")
        except Exception as e:
      
            self.app_cfg = {}

        if UDPBroadcaster is not None:
            print(f"✅ [TMOS WIDGET] Broadcaster Class Loaded for {comp_name}")
            # FIX: Ensure this line has exactly 12 spaces (matching the print above)
            self.broadcaster = UDPBroadcaster(self.app_cfg)
        else:
            print(f"❌ [TMOS WIDGET] Broadcaster Class NOT FOUND for {comp_name}")
        #end of

        self.graph_widgets = {}
        
        for i, p in enumerate(plot_params.plots_params_dict):
            unit = self.plots_params.plots_params_dict[p].unit
            self.plots_params.plots_params_dict[p].unit = "{}".format(p,unit)
            pw = HSDPlotLinesTMOSWidget(self.controller, self.plots_params.plots_params_dict[p].comp_name, p, plot_params.plots_params_dict[p], i, self)
            self.graph_widgets[p] = pw

            # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
            for i in reversed(range(pw.layout().count())): 
                pw.layout().itemAt(i).widget().setParent(None)

            self.contents_frame.layout().addWidget(self.graph_widgets[p].graph_widget)
            self.contents_frame.layout().setSpacing(6)

        self.update_plot_characteristics(plot_params)

    def update_plot_characteristics(self, plot_params: SensorPresenscePlotParams):
        self.plots_params = plot_params
        for p in plot_params.plots_params_dict:
            p_enabled = plot_params.plots_params_dict[p].enabled
            self.graph_widgets[p].graph_widget.setVisible(p_enabled)
            self.graph_widgets[p].redraw_plot(plot_params.plots_params_dict[p])
        
        if self.app_qt is not None:
            self.app_qt.processEvents()
        
    # @Slot(bool)
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1 or interface == 3:
            print("Component {} is logging via USB: {}".format(self.comp_name,status))
            if status:
                #Get number of enabled fast telemetries
                self.ft_enabled_list = [ ft for ft in self.plots_params.plots_params_dict if self.plots_params.plots_params_dict[ft].enabled]
                self.update_plot_characteristics(self.plots_params)
            else:
                self.ft_enabled_list = []
    
    def update_plot(self):
        super().update_plot()

    def add_data(self, data):
        # 1. Standard ST GUI Plotting (DO NOT TOUCH)
        self.graph_widgets["Ambient"].add_data([data[0]]) 
        self.graph_widgets["Object"].add_data([data[1], data[2], data[7], data[8]]) 
        self.graph_widgets["Presence"].add_data([data[3], data[4], data[10]]) 
        self.graph_widgets["Motion"].add_data([data[5], data[6], data[9]]) 

        # 2. CORRECTED BROADCAST (Php 20260301)
        if hasattr(self, 'broadcaster') and self.broadcaster is not None:
            try:
                # We extract the actual numbers by reaching into the arrays
                # ST data format: data[1] is [value], not just value.
                obj_val = float(data[1][0]) if hasattr(data[1], "__len__") else float(data[1])
                pres_val = float(data[4][0]) if hasattr(data[4], "__len__") else float(data[4])
                mot_val = float(data[6][0]) if hasattr(data[6], "__len__") else float(data[6])
                
                # Build a clean float list for the 11 expected values
                clean_payload = []
                for item in data:
                    if hasattr(item, "__len__"):
                        clean_payload.append(float(item[0]))
                    else:
                        clean_payload.append(float(item))

                # DEBUG: This will now show -3000.0 instead of 1.0
                print(f"BROADCAST -> ObjTemp: {obj_val:.2f} | Pres: {pres_val} | Mot: {mot_val}")
                
                self.broadcaster.send_sensor_data(self.comp_name, clean_payload)
            except Exception as e:
                # If a specific index fails, we catch it here
                print(f"❌ Broadcast Data Extraction Fail: {e}")