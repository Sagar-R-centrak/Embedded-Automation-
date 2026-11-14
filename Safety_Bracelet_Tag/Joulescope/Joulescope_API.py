import os
import time
import numpy as np
from pathlib import Path
from pyjoulescope_driver.__main__ import run as jsdrv_run
from pyjls import Reader


class JoulescopeAPI:
    def __init__(self, log_dir="logs", temp_filename="current_capture.jls"):
        """
        Initializes the API settings.
        :param log_dir: Folder where the JLS files will be stored.
        :param temp_filename: Name of the file used for the capture.
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.temp_path = str((self.log_dir / temp_filename).absolute())
        self.fs_hz = 5000  # 5 kHz as requested

    def read_current(self, duration_s):
        """
        Records current for duration_s and returns average current in mA (float).
        Returns None if the hardware is locked or fails.
        """
        # Cleanup old file to ensure fresh data
        if os.path.exists(self.temp_path):
            try:
                os.remove(self.temp_path)
            except PermissionError:
                print("Error: Previous file is still locked. Is a Reader open?")
                return None

        try:
            # The 'record' command performs the connect-stream-disconnect cycle
            jsdrv_run(args=[
                'record',
                '--frequency', str(self.fs_hz),
                '--duration', str(duration_s),
                '--signals', 'current',
                self.temp_path
            ])

            if not os.path.exists(self.temp_path):
                return None

            with Reader(self.temp_path) as r:
                signal = r.signal_lookup('current')
                if signal:
                    # Fetch all samples from the file
                    data = r.fsr(signal.signal_id, 0, signal.length)
                    avg_current = float(np.mean(data))
                    return float(f"{avg_current * 1000:.4f}")  # Return value in mA rounded to 4 decimals
                return None

        except Exception as e:
            print(f"Joulescope API Error: {e}")
            return None

    def close(self):
        """
        Releases file handles and deletes the temporary JLS file.
        """
        try:
            # Give the OS a moment to release file locks
            time.sleep(0.1)
            if os.path.exists(self.temp_path):
                os.remove(self.temp_path)
            print("Joulescope connection closed and cleaned.")
        except Exception as e:
            print(f"Cleanup Error: {e}")


