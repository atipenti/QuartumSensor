import socket
import json

class UDPBroadcaster:
    def __init__(self, app_cfg):
        self.app_cfg = app_cfg
        # We use a persistent socket to save CPU resources
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.ip = self.app_cfg.get("network_config", {}).get("ip", "127.0.0.1")

    def send_sensor_data(self, sensor_name, data):
        """Checks enabled status and sends data if True."""
        try:
            sensor_cfg = self.app_cfg.get("network_config", {}).get("sensors", {}).get(sensor_name)
            
            # THE KILL SWITCH: Only send if enabled in app_config.json
            if sensor_cfg and sensor_cfg.get("enabled", False):
                port = sensor_cfg.get("port")
                payload = {"s_id": sensor_name, "data": data.tolist() if hasattr(data, 'tolist') else data}
                msg = json.dumps(payload).encode()
                self.sock.sendto(msg, (self.ip, port))
        except Exception:
            pass # Stay silent to keep the ST GUI stable