
# ******************************************************************************
# * @attention
# *
# * Copyright (c) 2022 STMicroelectronics.
# * All rights reserved.
# *
# * This software is licensed under terms that can be found in the LICENSE file
# * in the root directory of this software component.
# * If no LICENSE file comes with this software, it is provided AS-IS.
# *
# *
# ******************************************************************************
#

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
        
        # Clear PlotWidget inherited graphic elements (mantaining all attributes, functions and signals)
        for i in reversed(range(self.layout().count())): 
            self.contents_frame.layout().itemAt(i).widget().setParent(None)

        heatmaps_shape = (4,4) if plot_params.resolution == self.RESOLUTION_4x4 else (8,8) #0 = 4x4, 1 = 8x8

        self.t1_out = PlotHeatmapWidget(controller, comp_name, comp_display_name, heatmaps_shape, plot_label= "Target 1", p_id = p_id, parent=self)
        
        # Php 20260228: default rotatin mOdified from 180° (2) to 270° (3)
        # Rotation index: 0: 0°, 1: 90°, 2: 180°, 3: 270°
        self.t1_out.set_default_rotation(3)
        # 2. Adjust Horizontal Flip specifically
        # In ST's logic, x_flip controls the columns (horizontal axis)
        # 2. Mise à jour forcée de l'INTERFACE (le texte "Flipped")
        # On accède au cadre "rois_frame" qui contient les réglages
        self.t1_out.set_default_x_flip(True)
        self.t1_out.set_default_y_flip(False)
        
        # 3. Synchronisation visuelle de l'interface
        settings = self.t1_out.rois_frame 
        settings.flipped_x_status = True        # Etat interne
        settings.flip_x_label.setText("Flipped") # Label visuel
        # end of Php modification

        self.t1_out.title_frame.setVisible(False)
        # self.t2_out = PlotHeatmapWidget(controller, comp_name, comp_display_name, heatmaps_shape, plot_label= "Target 2", p_id = p_id, parent=self)
        self.heatmaps["target1"] = self.t1_out
        # self.heatmaps["target2"] = self.t2_out
        self.t1_out.setMinimumWidth(540)

        heatmaps_frame = QFrame()
        wdg_layout = QHBoxLayout()
        wdg_layout.addWidget(self.t1_out)
        # wdg_layout.addWidget(self.t2_out)
        heatmaps_frame.setLayout(wdg_layout)
        self.contents_frame.layout().addWidget(heatmaps_frame)
    
    @Slot(bool, int) #Override PlotLinesWavWidget s_is_logging
    def s_is_logging(self, status: bool, interface: int):
        if interface == 1:
            print("Sensor {} is logging via USB: {}".format(self.comp_name, status))
        super().s_is_logging(status, interface)
    
    def update_plot_characteristics(self, plot_params:PlotParams):
        heatmaps_shape = (4,4) if plot_params.resolution == self.RESOLUTION_4x4 else (8,8)
        self.t1_out.update_plot_characteristics(heatmaps_shape)
        # self.t2_out.update_plot_characteristics(heatmaps_shape)
        self.plot_params = plot_params
        self.output_format = self.plot_params.output_format

    def add_data(self, data): # Ligne 81
        # --- LOGIQUE ORIGINALE ST (Indentation : 8 espaces) ---
        if self.output_format:
            start_t1_dist_id = self.output_format.get("target_distance").get("start_id")
            start_t1_status_id = self.output_format.get("target_status").get("start_id")
            out_data_step = self.output_format.get("nof_outputs")
            t1_data = data[0][start_t1_dist_id::out_data_step]
            t1_status_mask = data[0][start_t1_status_id::out_data_step]
        else:
            start_t1_dist_id = 4
            t1_data = data[0][start_t1_dist_id::8]
            t1_status_mask = data[0][start_t1_status_id-1::8]

        # --- TON NOUVEAU BLOC UDP (Doit être aligné avec le "if self.output_format") ---
        if t1_data is not None and len(t1_data) > 0:
            try:
                import socket, json
                payload = {str(i): {"d": int(val)} for i, val in enumerate(t1_data)}
                msg = json.dumps(payload).encode()
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(msg, ("127.0.0.1", 5005))
            except Exception:
                pass

        # --- FIN DE LA FONCTION ---
        self.heatmaps["target1"].add_data((t1_data, t1_status_mask))

    