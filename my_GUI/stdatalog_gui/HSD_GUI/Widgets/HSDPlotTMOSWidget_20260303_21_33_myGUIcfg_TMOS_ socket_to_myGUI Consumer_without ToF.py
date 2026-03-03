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
        # 2. THE FIX: Using the PlotLines extraction method
        if hasattr(self, 'broadcaster') and self.broadcaster is not None:
            try:
                # We create the payload by explicitly grabbing the FIRST SAMPLE 
                # from each data buffer, just like the Lines widget does.
                clean_payload = []
                for i in range(len(data)):
                    # data[i] is a buffer. data[i][0] is the ACTUAL FLOAT VALUE.
                    try:
                        val = float(data[i][0])
                        clean_payload.append(val)
                    except:
                        clean_payload.append(0.0)

                # --- START OF CHANGE ---
                # We "link" the software detection to the flags used by the broadcaster.
                # In ST TMOS data: 
                # Index 9 is Motion (Software Compensated)
                # Index 10 is Presence (Software Compensated)
                
                sw_pres = clean_payload[10]
                sw_mot = clean_payload[9]

                # If the Software Compensation detects something, force the flags to 1.0
                if sw_pres > 0: clean_payload[4] = 1.0
                if sw_mot > 0: clean_payload[6] = 1.0
                # --- END OF CHANGE -

                # Now indices 1, 4, and 6 will contain REAL numbers (e.g. -1614.0, 1.0, 0.0)
                obj_temp = clean_payload[1]
                pres_flag = clean_payload[4]
                mot_flag = clean_payload[6]

                print(f"BROADCAST REAL DATA -> ObjTemp: {obj_temp:.2f} | Pres: {pres_flag} | Mot: {mot_flag}")
                
                self.broadcaster.send_sensor_data(self.comp_name, clean_payload)
            except Exception as e:
                print(f"❌ Extraction Error: {e}")