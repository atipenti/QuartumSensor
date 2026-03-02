import sys
import json
from stdatalog_core.HSD_link.HSDLink import HSDLink

def main():
    # 1. Initialize the HSDLink Factory
    # This creates the high-level manager that handles V1, V2, and Serial protocols
    hsd_factory = HSDLink()
    
    # 2. Establish connection to the USB device
    # 'st_hsd' is the standard high-speed datalog communication type
    hsd_link = hsd_factory.create_hsd_link(dev_com_type='st_hsd')

    if hsd_link is None:
        print("Error: No compatible ST USB devices found.")
        return

    # 3. Get list of connected devices and use the first one (ID 0)
    device_id = 0
    
    try:
        # 4. Call get_device_status()
        # This returns a dictionary containing the full PnPL (Plug and Play) status
        device_status = hsd_link.get_device_status(device_id)
        
        # 5. Navigate through the "nested" structure: devices -> components
        # As per the ST SDK structure: status["devices"][0]["components"]
        devices = device_status.get("devices", [])
        
        if not devices:
            print("No device information found in status.")
            return

        print(f"\n--- Device Identity: {hsd_link.get_device_alias(device_id)} ---")
        
        components = devices[0].get("components", [])
        print(f"Found {len(components)} components.\n")

        # 6. Walk through each component
        for index, component in enumerate(components):
            # The component is usually a dict where the key is the component name
            comp_name = list(component.keys())[0]
            comp_details = component[comp_name]
            
            # Extract common fields (Status, Type, etc.)
            comp_type = comp_details.get("c_type", "N/A")
            is_enabled = comp_details.get("enable", "N/A")
            
            print(f"[{index}] Component: {comp_name}")
            print(f"    - Type: {comp_type}")
            print(f"    - Enabled: {is_enabled}")
            
            # If it's a sensor, you might want to see ODR or Full Scale
            if "odr" in comp_details:
                print(f"    - ODR: {comp_details['odr']} Hz")
            
            print("-" * 30)

    except Exception as e:
        print(f"An error occurred during communication: {e}")

if __name__ == "__main__":
    main()