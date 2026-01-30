import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from idlelib.tooltip import Hovertip
import pyvisa
import time
import threading
import csv
import os
from datetime import datetime

class VisaLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Power Supply & DMM Controller")
        self.root.geometry("600x750")

        # Default variable values
        self.start_voltage = tk.DoubleVar(value=0.0)
        self.stop_voltage = tk.DoubleVar(value=5.0)
        self.step_voltage = tk.DoubleVar(value=0.5)
        self.current_limit = tk.DoubleVar(value=1.0) # Amps
        self.settle_time = tk.DoubleVar(value=0.5) # Seconds
        self.psu_address = tk.StringVar()
        self.dmm_address = tk.StringVar()
        self.output_file = tk.StringVar(value="measurements")
        self.psu_channel = tk.StringVar(value="1 - Yellow")
        self.high_impedance_mode = tk.BooleanVar(value=True)
        
        # Tuning factor for time estimation (seconds per step for VISA comms overhead)
        self.overhead_per_step = 0.9

        self.is_running = False
        self.rm = pyvisa.ResourceManager()
        self.active_psu = None
        self.active_dmm = None

        self._create_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_ui(self):
        # Resource Selection Frame
        resource_frame = ttk.LabelFrame(self.root, text="Instrument Connection", padding=10)
        resource_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(resource_frame, text="PSU Address:").grid(row=0, column=0, sticky="w")
        self.psu_combo = ttk.Combobox(resource_frame, textvariable=self.psu_address, width=50)
        self.psu_combo.grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(resource_frame, text="PSU Channel:").grid(row=1, column=0, sticky="w")
        
        # Channel selection with color box
        chan_frame = ttk.Frame(resource_frame)
        chan_frame.grid(row=1, column=1, sticky="w", padx=5)
        
        self.chan_combo = ttk.Combobox(chan_frame, textvariable=self.psu_channel, width=15, state="readonly")
        self.chan_combo['values'] = ("1 - Yellow", "2 - Green", "3 - Blue")
        self.chan_combo.pack(side="left")
        self.chan_combo.bind("<<ComboboxSelected>>", self.update_channel_color)
        
        self.chan_color_lbl = tk.Label(chan_frame, width=4, bg="#FFD700", relief="solid")
        self.chan_color_lbl.pack(side="left", padx=5)

        ttk.Label(resource_frame, text="DMM Address:").grid(row=2, column=0, sticky="w")
        self.dmm_combo = ttk.Combobox(resource_frame, textvariable=self.dmm_address, width=50)
        self.dmm_combo.grid(row=2, column=1, padx=5, pady=2)
        
        # High-Z mode checkbox
        self.high_imp_check = ttk.Checkbutton(
            resource_frame, 
            text="Enable DMM Auto High-Z Mode",
            variable=self.high_impedance_mode
        )
        self.high_imp_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        
        # Add tooltip with detailed information
        Hovertip(self.high_imp_check, 
                 "When enabled, the DMM automatically uses 10GΩ input impedance on 100mV and 1V ranges\n"
                 "and 10MΩ input impedance for all other ranges. When disabled, the DMM uses a fixed 10MΩ\n"
                 "input impedance for all ranges.")
        
        ttk.Button(resource_frame, text="Scan for Instruments", command=self.scan_resources).grid(row=4, column=1, sticky="e", pady=5)

        # Parameters Frame
        param_frame = ttk.LabelFrame(self.root, text="Measurement Parameters", padding=10)
        param_frame.pack(fill="x", padx=10, pady=5)

        self._add_param(param_frame, "Start Voltage (V):", self.start_voltage, 0)
        self._add_param(param_frame, "Stop Voltage (V):", self.stop_voltage, 1)
        self._add_param(param_frame, "Step Size (V):", self.step_voltage, 2)
        self._add_param(param_frame, "Current Limit (A):", self.current_limit, 3)
        self._add_param(param_frame, "Settle Time (s):", self.settle_time, 4)

        # Estimates
        ttk.Separator(param_frame, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky="ew", pady=5)
        self.est_steps_label = ttk.Label(param_frame, text="Total Steps: --")
        self.est_steps_label.grid(row=6, column=0, sticky="w", padx=5)
        self.est_total_time_label = ttk.Label(param_frame, text="Est. Total Time: --:--")
        self.est_total_time_label.grid(row=6, column=1, sticky="w", padx=5)

        # Bind traces
        for var in [self.start_voltage, self.stop_voltage, self.step_voltage, self.settle_time]:
            var.trace_add("write", self.calculate_estimates)
        
        # Initial calculation
        self.root.after(100, self.calculate_estimates)

        # Output Frame
        file_frame = ttk.LabelFrame(self.root, text="CSV File Output Name", padding=10)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Entry(file_frame, textvariable=self.output_file, width=50).pack(side="left", fill="x", expand=True)
        ttk.Button(file_frame, text="Browse...", command=self.browse_file).pack(side="right", padx=5)

        # Status & Controls
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill="x", padx=10, pady=5)

        self.start_btn = ttk.Button(control_frame, text="Start Measurement", command=self.start_process)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="Stop", command=self.stop_process, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        # Progress
        progress_frame = ttk.LabelFrame(self.root, text="Progress", padding=10)
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x", pady=5)

        self.time_label = ttk.Label(progress_frame, text="Estimated Time Remaining: --:--")
        self.time_label.pack(side="left", padx=(0, 20))

        self.duration_label = ttk.Label(progress_frame, text="Duration: 00:00")
        self.duration_label.pack(side="left")
        
        self.status_label = ttk.Label(progress_frame, text="Status: Ready")
        self.status_label.pack(side="left", fill="x", expand=True, padx=20)

        # Log Text Box
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, width=60, state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text['yscrollcommand'] = scroll.set

    def _add_param(self, parent, text, variable, row):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Entry(parent, textvariable=variable, width=15).grid(row=row, column=1, sticky="w", padx=5, pady=2)

    def update_channel_color(self, event=None):
        val = self.psu_channel.get()
        if "1" in val:
            self.chan_color_lbl.config(bg="#FFD700") # Yellow
        elif "2" in val:
            self.chan_color_lbl.config(bg="#32CD32") # Green
        elif "3" in val:
            self.chan_color_lbl.config(bg="#1E90FF") # Blue

    def calculate_estimates(self, *args):
        try:
            start = self.start_voltage.get()
            stop = self.stop_voltage.get()
            step_size = self.step_voltage.get()
            settle = self.settle_time.get()
            
            if step_size <= 0:
                raise ValueError("Step size must be positive")

            # Logic matches run_sequence
            steps = int(abs(stop - start) / step_size) + 1
            
            total_seconds = steps * (settle + self.overhead_per_step) # Use overhead tuning factor
            
            mins, secs = divmod(int(total_seconds), 60)
            
            self.est_steps_label.config(text=f"Total Steps: {steps}")
            self.est_total_time_label.config(text=f"Est. Total Time: {mins:02d}:{secs:02d}")
            
        except (tk.TclError, ValueError):
            # User is typing invalid params
            self.est_steps_label.config(text="Total Steps: --")
            self.est_total_time_label.config(text="Est. Total Time: --:--")

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def scan_resources(self):
        self.log("Scanning for instruments (this may take a while)...")
        # Run scan in a separate thread to not freeze UI if timeouts occur
        threading.Thread(target=self._scan_resources_thread, daemon=True).start()

    def _scan_resources_thread(self):
        try:
            raw_resources = self.rm.list_resources()
            friendly_list = []
            
            for res in raw_resources:
                try:
                    with self.rm.open_resource(res) as instr:
                        instr.timeout = 1000
                        # Ask for IDN
                        idn = instr.query("*IDN?").strip()
                        # Clean up IDN string
                        # Typical IDN: Manufacturer,Model,Serial,Firmware
                        parts = idn.split(',')
                        if len(parts) >= 2:
                             # Display: "Model (Serial) - ResourceID"
                             # e.g. "E36313A (MY12345) - USB0::..."
                            manufacturer = parts[0].strip()
                            model = parts[1].strip()
                            friendly_name = f"{manufacturer} {model} - {res}"
                        else:
                            friendly_name = f"{idn} - {res}"
                        friendly_list.append(friendly_name)
                except Exception:
                    # If can't open or query, just list the resource ID
                    friendly_list.append(res)

            # Update UI on main thread
            self.root.after(0, self._update_resource_list, friendly_list)
            self.root.after(0, self.log, f"Scan complete. Found {len(friendly_list)} instruments.")
            
        except Exception as e:
            self.root.after(0, self.log, f"Error scanning resources: {e}")
            self.root.after(0, messagebox.showerror, "Error", f"Failed to list VISA resources: {e}")

    def _update_resource_list(self, resource_list):
        self.psu_combo['values'] = resource_list
        self.dmm_combo['values'] = resource_list
        if resource_list:
            # Auto-select if we can guess based on model names
            for i, name in enumerate(resource_list):
                # Match general prefixes
                if "E363" in name:
                    self.psu_combo.current(i)
                if "EDU344" in name:
                    self.dmm_combo.current(i)

    def browse_file(self):
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filename:
            self.output_file.set(filename)

    def start_process(self):
        if not self.psu_address.get() or not self.dmm_address.get():
            messagebox.showwarning("Warning", "Please select VISA addresses for both instruments.")
            return

        # Ensure .csv extension
        output_path = self.output_file.get().strip()
        if not output_path.lower().endswith(".csv"):
            output_path += ".csv"

        if os.path.exists(output_path):
            if not messagebox.askyesno("Overwrite File?", f"The file '{output_path}' already exists.\nDo you want to overwrite it?"):
                return

        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.progress_var.set(0)
        self.log("Starting measurement sequence...")
        
        # Start background thread
        self.thread = threading.Thread(target=self.run_sequence)
        self.thread.daemon = True
        self.thread.start()

    def stop_process(self):
        self.is_running = False
        self.log("Stop requested. Finishing current step...")
        self.stop_btn.config(state="disabled")

    def _get_resource_from_selection(self, selection):
        # Extract VISA address from "Friendly Name - VISA_ADDRESS" format
        if " - " in selection:
            return selection.split(" - ")[-1].strip()
        return selection.strip()

    def run_sequence(self):
        self.active_psu = None
        self.active_dmm = None
        try:
            # Connect Instruments
            try:
                psu_addr = self._get_resource_from_selection(self.psu_address.get())
                dmm_addr = self._get_resource_from_selection(self.dmm_address.get())
                
                self.active_psu = self.rm.open_resource(psu_addr)
                self.active_dmm = self.rm.open_resource(dmm_addr)
                
                # Check IDs
                psu_idn = self.active_psu.query("*IDN?").strip()
                dmm_idn = self.active_dmm.query("*IDN?").strip()
                self.root.after(0, self.log, f"Connected to PSU: {psu_idn}")
                self.root.after(0, self.log, f"Connected to DMM: {dmm_idn}")
                
            except Exception as e:
                self.root.after(0, self.log, f"Connection Failed: {e}")
                raise e

            # Setup measurement parameters
            start_v = self.start_voltage.get()
            stop_v = self.stop_voltage.get()
            step_v = self.step_voltage.get()
            settle_t = self.settle_time.get()
            current_lim = self.current_limit.get()
            
            # Parse Channel ID from string "1 - Yellow"
            raw_channel = self.psu_channel.get()
            channel = int(raw_channel.split(' - ')[0])

            # Generate voltage points
            # Handle direction (up or down)
            if start_v <= stop_v:
                steps = int((stop_v - start_v) / step_v) + 1
                voltages = [start_v + i * step_v for i in range(steps)]
            else:
                steps = int((start_v - stop_v) / step_v) + 1
                voltages = [start_v - i * step_v for i in range(steps)]
            
            total_time = len(voltages) * (settle_t + self.overhead_per_step) 
            
            # Configure instruments
            # PSU Setup (Keysight E36313A)
            self.active_psu.write(f"INST:NSEL {channel}") # Select Channel
            self.active_psu.write(f"VOLT {start_v}")
            self.active_psu.write(f"CURR {current_lim}")
            
            # DMM Setup (Keysight EDU34450A)
            # Default is SLOW 5.5 digit mode
            self.active_dmm.write("CONF:VOLT:DC")
            
            # Configure High-Z mode
            if self.high_impedance_mode.get():
                self.active_dmm.write("VOLT:IMP:AUTO ON")
                self.root.after(0, self.log, "High-Z mode enabled (10GΩ for 100mV/1V ranges)")
            else:
                self.active_dmm.write("VOLT:IMP:AUTO OFF")
                self.root.after(0, self.log, "High-Z mode disabled (using standard impedance)") 

            # Create CSV (Ensure extension)
            file_name = self.output_file.get().strip()
            if not file_name.lower().endswith(".csv"):
                file_name += ".csv"

            with open(file_name, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Timestamp", "Set Voltage (V)", "Measured Voltage (V)"])

                # Turn on output
                self.root.after(0, self.log, f"Enabling Output on Channel {channel}")
                self.active_psu.write("OUTP ON")

                start_time_process = time.time()

                for idx, v_set in enumerate(voltages):
                    if not self.is_running:
                        break

                    # Set Voltage
                    self.active_psu.write(f"VOLT {v_set}")
                    
                    # Settle
                    self.root.after(0, self.status_label.config, {"text": f"Status: Setting {v_set:.3f}V & Settling..."})
                    time.sleep(settle_t)

                    # Measure
                    # READ? configures and measures. MEAS? is higher level.
                    v_read_str = self.active_dmm.query("READ?")
                    try:
                        v_read = float(v_read_str)
                    except:
                        v_read = float('nan')

                    writer.writerow([datetime.now().isoformat(), v_set, v_read])

                    # Update UI
                    elapsed = time.time() - start_time_process
                    avg_time_per_step = elapsed / (idx + 1)
                    remaining_steps = len(voltages) - (idx + 1)
                    time_left = remaining_steps * avg_time_per_step
                    
                    percent = ((idx + 1) / len(voltages)) * 100
                    
                    # Use lambda to ensure values are passed correctly
                    self.root.after(0, lambda p=percent, t=time_left, vs=v_set, vr=v_read, e=elapsed: 
                                      self.update_progress(p, t, vs, vr, e))

            # Calculate final duration
            total_elapsed = time.time() - start_time_process
            d_mins, d_secs = divmod(int(total_elapsed), 60)
            self.root.after(0, self.log, f"Measurement Complete. Total Duration: {d_mins:02d}:{d_secs:02d}")

        except Exception as e:
            self.root.after(0, self.log, f"Error during sequence: {e}")
            self.root.after(0, messagebox.showerror, "Error", str(e))

        finally:
            # Cleanup
            if self.active_psu:
                try:
                    self.root.after(0, self.log, "Turning off PSU Output...")
                    self.active_psu.write("OUTP OFF")
                    self.active_psu.close()
                except:
                    pass
            if self.active_dmm:
                try:
                    self.active_dmm.close()
                except:
                    pass
            
            self.active_psu = None
            self.active_dmm = None
            self.is_running = False
            self.root.after(0, self.reset_ui_state)

    def update_progress(self, percent, time_left, v_set, v_read, elapsed):
        try:
            self.progress_var.set(percent)
            
            # Safe conversion to handle potential float/string mixups if passed via Tcl
            mins, secs = divmod(int(float(time_left)), 60)
            self.time_label.config(text=f"Estimated Time Remaining: {mins:02d}:{secs:02d}")
            
            d_mins, d_secs = divmod(int(float(elapsed)), 60)
            self.duration_label.config(text=f"Duration: {d_mins:02d}:{d_secs:02d}")
            
            self.log(f"Set: {v_set:.3f}V | Meas: {v_read:.6f}V")
        except Exception as e:
            print(f"UI Update Error: {e}")

    def reset_ui_state(self):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Status: Idle")

    def on_closing(self):
        if self.is_running:
            if messagebox.askokcancel("Quit", "Measurement is running. Do you want to stop and quit?"):
                self.stop_process()
                # Give a moment for thread stop signal
                # this blocks main thread, but better than instant kill
                self._force_cleanup() # Try to force cleanup
                self.root.destroy()
        else:
            self.root.destroy()

    def _force_cleanup(self):
        # Last attempt to close instruments if app is closing
        if self.active_psu:
            try:
                self.active_psu.write("OUTP OFF")
                self.active_psu.close()
            except:
                pass
        if self.active_dmm:
            try:
                self.active_dmm.close()
            except:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = VisaLoggerApp(root)
    root.mainloop()
