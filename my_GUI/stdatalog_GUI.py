# *****************************************************************************
#  * @file    stdatalog_GUI.py
#  * @author  SRA / Modified by PhP & A.P
# ******************************************************************************
# * @attention
# *
# * Copyright (c) 2022 STMicroelectronics.
# * All rights reserved.
# *
# * This software is licensed under terms that can be found in the LICENSE file
# * in the root directory of this software component.
# * If no LICENSE file comes with this software, it is provided AS-IS.
# ******************************************************************************

import sys
import os
import argparse
import logging

# Add the STDatalog SDK root directory to the sys.path to access the SDK packages
# Keeping your original working path logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from PySide6.QtWidgets import QApplication
from PySide6 import QtCore
from PySide6.QtCore import QTimer

from stdatalog_gui.HSD_GUI.HSD_MainWindow import HSD_MainWindow
import stdatalog_core.HSD_utils.logger as logger

# Initialize logger and force level to ERROR to suppress ST's verbose INFO/WARNING messages
log = logger.setup_applevel_logger(is_debug = False)
log.setLevel(logging.ERROR) 

def load_device_config_after_delay(main_window, config_path):
    """
    Injects the configuration file once the connection is established.
    Silences the communication logs to avoid 'PnPL Response' spam.
    """
    def load_config():
        # Use a flag to ensure injection only happens once
        if hasattr(main_window, '_config_applied') and main_window._config_applied:
            return

        try:
            # Check if the controller is ready
            if hasattr(main_window, 'controller') and main_window.controller is not None:
                if hasattr(main_window.controller, 'load_config'):
                    
                    # Target the specific ST logger that spams PnPL responses
                    st_link_logger = logging.getLogger("HSDatalogApp.stdatalog_core.HSD_link.communication.PnPL_HSD.hsd_dll")
                    prev_level = st_link_logger.level
                    st_link_logger.setLevel(logging.WARNING)

                    # Execute silent injection
                    main_window.controller.load_config(config_path)
                    
                    # Restore original logging level
                    st_link_logger.setLevel(prev_level)
                    
                    # Success message with the filename
                    print(f"Device configuration {config_path} successfully loaded")
                    
                    main_window._config_applied = True
                    return 
        except Exception:
            # Silently ignore temporary boot errors
            pass

        # Check every second until connected
        QTimer.singleShot(1000, load_config)

    QTimer.singleShot(1000, load_config)

def main():
    # Setup command line argument parsing
    parser = argparse.ArgumentParser(description='STDatalog GUI Application')
    parser.add_argument('config_file', nargs='?', help='Path to device configuration JSON file')
    args = parser.parse_args()
    
    # Required for high-performance plotting widgets (OpenGL)
    QApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    
    # Create the main window instance
    mainWindow = HSD_MainWindow(app)
    mainWindow.setAppTitle("STWIN.BOX sensor box Control Panel")
    mainWindow.setAppCredits("by A.P & PhP")
    mainWindow.setWindowTitle("STWIN.BOX with Streamer")
    mainWindow.setAppVersion("v1.0.0")
    mainWindow.setLogMsg("Device is logging --> Board Configuration has been disabled.\nNow you can label your acquisition using the [Tags Information] Component")
    mainWindow.showMaximized()
    
    # Start the auto-load process if a config file was provided
    if args.config_file:
        if os.path.exists(args.config_file):
            load_device_config_after_delay(mainWindow, args.config_file)
        else:
            print(f"CRITICAL: Device config file NOT FOUND: {args.config_file}")

    # Set standard DPI for cross-platform visual consistency
    app.setAttribute(QtCore.Qt.AA_Use96Dpi)
    app.exec()

if __name__ == "__main__":
    # Execute the application
    main()