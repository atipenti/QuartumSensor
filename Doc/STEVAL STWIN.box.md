

MY TODO LIST: why: to take the python test environment to develop a test python PC application to connect to STWIN.BOX via USB, config the selected sensors and extract the sensor data with a SW Python get_sensor_array (4x4) or (8x8) with the motion and detection processing for each array "segment"
* Guideline for STDATALOG-PYSDK installation from clone github --recursive,
* Be clear when to use venv
* Ensure the "nested" folders stdatalog_core, _gui _pnpl, _dtk are reachable in the editable approach : pip install -e .
* test the GUI application HSDatalog2: see Start_ST_Datalog.bat on Desktop

* create a /DEV/mySTDATALOG-APP/ environment to test the first examples for connecting to USB, STWIN.BOX . 
* Always activate the SDK venv!!! for STDATALOG-PYSDK
	*   ".venv\Scripts\activate.bat"
* then, in the consolde, stay in the venv environment and go up with cd to mySTDATALOG-APP folder, and run my app scripts, with >python name_of_script.py     Because i did pip install -e .   in _core, _dtk_, _pnpl, _gui    inside that venv, import stdatalog_core, etc, ... will work from **from any folder** as long as that venv is active
!!!! I must remember to activate the SDK venv beofre running your app scripts !!!!



* take cli_command example and other in order not to start from scratch the python code
	


User account at ST:

	Antonio Penti
		atipenti@hotmail.com

1) Installation STWIN.box
	* FP-SNS-DATALOG2
	* STM32Cube Programmer
	* UNICO (evaluate MEMS sensor and for advanced configuration ML Core)
	* SD Card FOrmatter 
	* Notepad++
	* Python


https://www.youtube.com/watch?v=GZs-QbSrbBQ


![[Pasted image 20260214094517.png]]![[Pasted image 20260214110323.png]]


This manual captures the exact sequence and technical "fixes" we used to successfully launch the **STWIN.box** High-Speed Datalogger interface using **Python 3.13**.

---

# User Manual: ST High-Speed Datalogger GUI Installation

**Target Hardware:** STWIN.box (SensorTile.box Pro)

**Software Stack:** STM32CubeFunctionPack_DATALOG2_V3.2.0

**Environment:** Windows 10/11, Python 3.13 (64-bit)

---

## 1. Environment Preparation

The ST toolset requires a specific set of Python libraries. To ensure compatibility with version 1.3.0, follow these steps:

### A. Python Verification

Ensure Python 3.13 is installed and added to your Windows Path. Verify with:

`py -3.13 --version`

See specific part for next steps.

## 2. Hardware Connectivity

1. **Firmware:** Ensure the STWIN.box is flashed with the **DATALOG2** firmware (from the `STM32CubeFunctionPack_DATALOG2_V3.2.0` folder) ***???  !!!! it should be the DTECT_release.bin image***
    
2. **USB Connection:** Connect the board to your PC. Windows should recognize it as a "High Speed Datalogger" or a Virtual
3. 
4. 
5. COM Port.
    

---

## 3. Creating the One-Click Launcher

Because the standard `st_hsdatalog_gui` command may not link correctly on all systems, you must create a manual batch file to handle the GUI's "Event Loop" and passing the `app` argument.

1. Right-click your **Desktop** > **New** > **Text Document**.
    
2. Paste the following code:
    
    Fragmento de código
    
    ```
    @echo off
    echo Starting ST High Speed Datalogger GUI...
    py -3.13 -c "import sys; from PySide6.QtWidgets import QApplication; from stdatalog_gui.HSD_GUI.HSD_MainWindow import HSD_MainWindow; app = QApplication(sys.argv); window = HSD_MainWindow(app); window.show(); sys.exit(app.exec())"
    pause
    ```
    
3. **Rename the file:** Save it as `Start_ST_Datalog.bat`.
    
    - _Warning:_ Ensure the extension is `.bat`. If it is `Start_ST_Datalog.bat.txt`, enable "File name extensions" in File Explorer and remove the `.txt`.
        

---

## 4. Operational Workflow

1. **Launch:** Double-click `Start_ST_Datalog.bat`.
    
2. **Detection:** In the **Connection** box, select `STWIN_BOX_001` from the dropdown.
    
3. **Handshake:** Click the green **Connect** button.
    
4. **Configuration:** Use the Sidebar icons to toggle sensors:
    
    - **IIS3DWB:** High-performance vibration sensor (ideal for AI).
        
    - **IMP23ABSU:** Analog Microphone.
        
    - **ISM330DHCX:** 6-axis IMU.
        
5. **Visualization:** Click the **Flask (Beaker)** icon to view real-time data plots.
    

---

## 5. Critical Troubleshooting

|**Error**|**Cause**|**Solution**|
|---|---|---|
|**"Error in Communication Engine"**|The USB port is held open by a previous crashed session.|Unplug USB, wait 5 seconds, replug, and restart the .bat file.|
|**"TypeError: ... missing 1 required positional argument: 'app'"**|The Python script called the Window without the Application controller.|Ensure your .bat file uses `HSD_MainWindow(app)` and not `HSD_MainWindow()`.|
|**"No module named stdatalog_gui"**|The libraries were installed to a different Python version.|Re-run the pip install command specifically using the `py -3.13` prefix.|

---

**Would you like me to add a final section on how to export these data logs for use in NanoEdge AI Studio?**


** INSTALL THE STDATALOG-PYSDK from ST github **
### 1. Recap: What you have done so far

- **Cloned the Repo:** You used `--recursive` to pull the main repository and all sub-modules (`core`, `dtk`, `pnpl`, etc.).
    
- **Ran the Batch File:** You ran `stdatalog_install.bat`. This typically tries to install dependencies and set up the environment, but it clearly didn't "link" the modules to your Python path in a way your shell recognizes.
    
- **Verified JSONs:** You confirmed `device_config.json` is present.
    
- **Identified Import Errors:** You discovered that Python cannot see `stdatalog_core` because it isn't in Python's `site-packages` yet.
    
---

### 2. The Guideline for Option 1

#### **Step A: The "Where" (Virtual Environment)**

**Yes, use a venv.** It keeps your base Windows Python clean and prevents version conflicts.

1. Open your terminal/command prompt.
    
2. Navigate to your main project folder: `cd C:\...\STDATALOG-PYSDK`
    
3. Create the venv: `python -m venv venv`
    
4. Activate it:
    
    - **Windows:** `venv\Scripts\activate`
        
    - _(You should see `(venv)` appear at the start of your command line)._
        

#### **Step B: The "How" (The Editable Install)**

Inside that same terminal, while the `(venv)` is active, run the following commands one by one. This tells Python to "map" these local folders as official libraries.

Bash

```
# Install the core first (The Engine)
pip install -e ./stdatalog_core

# Install the PnPL manager (The Command Translator)
pip install -e ./stdatalog_pnpl

# Install the Data Toolkit (The Data Processor)
pip install -e ./stdatalog_dtk

# Optional: Install the GUI components
pip install -e ./stdatalog_gui
```

#### **Step C: The "Test"**

Now, while still in that terminal with the `(venv)` active, enter the Python shell:

1. Type: `python`
    
2. Inside the `>>>` prompt, try:
    
    Python
    
    ```
    from stdatalog_core.HSD_link.HSDLink import HSDLink
    print("Success! Path resolved.")
    ```
    

---




***_____ OLD _____***
# STWIN.box: Module 4 - Capturing sensor data over USB

Config device file
![[Pasted image 20260214111723.png]]

I need to install the Python STDATALOG from git. With older version of Python 3.13 instead of 3.14
You can certainly use **Python 3.13**, and it is much more likely to work than 3.14. However, you don't necessarily need to uninstall 3.14, you just need to ensure your terminal is talking to 3.13.

The easiest way to do this without messing with complex Path variables is to use the **Python Launcher** (`py`).

### Step 1: Verify 3.13 is accessible

Open a new terminal and type:

PowerShell

```
py -3.13 --version
```

If it returns `Python 3.13.2`, you are in business.

### Step 2: Install using the 3.13 "Launcher"

Instead of just typing `pip`, use `py -3.13 -m pip`. This forces the computer to install the packages specifically for version 3.13, ignoring 3.14 entirely.

Run these four commands:

1. **PNPL:**
    
    PowerShell
    
    ```
    py -3.13 -m pip install git+https://github.com/STMicroelectronics/stdatalog-pysdk.git#subdirectory=stdatalog_pnpl
    ```
    
2. **CORE:**
    
    PowerShell
    
    ```
    py -3.13 -m pip install git+https://github.com/STMicroelectronics/stdatalog-pysdk.git#subdirectory=stdatalog_core
    ```
    
3. **DTK:**
    
    PowerShell
    
    ```
    py -3.13 -m pip install git+https://github.com/STMicroelectronics/stdatalog-pysdk.git#subdirectory=stdatalog_dtk
    ```
    
4. **GUI:**
    
    PowerShell
    
    ```
    py -3.13 -m pip install git+https://github.com/STMicroelectronics/stdatalog-pysdk.git#subdirectory=stdatalog_gui
    ```
    

---

### Why this should work

- **PySide6:** Supports 3.13, so the error about "No matching distribution" should disappear.
    
- **Rust/Tsdownsample:** 3.13 has been out long enough that there should be pre-compiled "wheels" available, so it shouldn't ask you for the Rust compiler anymore.
    

### One potential "Gotcha"

If the **DTK** command still fails with a "Python < 3.14" error, it means the ST SDK has a very strict internal check. If that happens, you really will have to uninstall 3.14, because the installer sees it exists on your system and gets confused.

**Try the first command (`py -3.13 -m pip...`)—does it complete successfully without the "Defaulting to user installation" warning?**



SETUP and Orientation: WRONG PICTURE !!!!!
![[Pasted image 20260215181707.png]]
	![[Pasted image 20260215182005.png]]	

Correct coordinates

![[Pasted image 20260215182418.png]]



 I recorded the session with this settings, and files are under Desktop/20260215_18_41_33:

i have recorded a motion path, moving inside a zone area (0,0) - (3,3); following a coordinate system and changing position every 5sec (approximately). I started at (3,3), then (3,2), then (3,1), then (3,0), then (2,0), then (1,0), then (0,0), then (0,1), then (0,2), then (0,3), then (1,3), then (2,3), then (2,2), then (2,1), then (1,1), then finishing at (1,2). Analyse the corresponding recorded data, and make the correlation between raw signals and zone coordinate i was moving around





![[Pasted image 20260215191334.png]]


### 1. Data Correlation Summary

The recording lasts approximately **80 seconds**. Based on the 16-step path you described (5 seconds per station), the sensors show a clear "U-shaped" then "Spiral" progression.

| **Time (Approx)** | **Target Zone**   | **Sensor Observation**                                                   |
| ----------------- | ----------------- | ------------------------------------------------------------------------ |
| **0-5s**          | **(3,3)**         | High signal in the bottom-right corner. Distance drops to ~600-800mm.    |
| **15-20s**        | **(3,0)**         | Signal shifts to the top-right corner.                                   |
| **30-35s**        | **(0,0)**         | Signal reaches the top-left corner (completion of the first outer edge). |
| **50-55s**        | **(0,3)**         | Signal reaches the bottom-left corner.                                   |
| **70-80s**        | **(1,1) / (1,2)** | Signal stabilizes in the center-left zones (finishing the spiral).       |


I have aligned your 16-station path (approx. 5s per station) with the distance drops in the `.dat` file:

|**Time**|**Station**|**Target (x,y)**|**Target Index**|**Raw Signal Observed**|
|---|---|---|---|---|
|**0-5s**|1|**(3,3)**|**15**|Distance drops from ~3000mm to **~750mm** in Index 15.|
|**5-10s**|2|**(3,2)**|**11**|Signal moves vertically up one cell.|
|**10-15s**|3|**(3,1)**|**7**||
|**15-20s**|4|**(3,0)**|**3**|Signal hits the Top-Right corner.|
|**20-25s**|5|**(2,0)**|**2**|Signal moves left along the top row.|
|**30-35s**|7|**(0,0)**|**0**|**Peak Activity:** Lowest distance recorded in Index 0.|
|**45-50s**|10|**(0,3)**|**12**|Signal hits the Bottom-Left corner.|
|**75-80s**|16|**(1,2)**|**9**|Final position: Stable at center-left.|