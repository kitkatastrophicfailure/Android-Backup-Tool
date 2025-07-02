import tkinter
from tkinter import filedialog
import customtkinter
import subprocess
import os
import threading
import queue
import sys
import re
import time

# --- Configuration ---
if getattr(sys, 'frozen', False):
    script_dir = sys._MEIPASS
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))

ADB_PATH = os.path.join(script_dir, "adb.exe")
DOCUMENTS_PATH = os.path.join(os.path.expanduser("~"), "Documents")
BACKUP_DIR = os.path.join(DOCUMENTS_PATH, "AndroidBackup")
ASSUMED_MB_PER_SECOND = 15


def format_bytes(size):
    """Converts bytes to a human-readable format (KB, MB, GB)."""
    if size is None:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power and n < len(power_labels):
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def format_seconds(seconds):
    """Converts seconds into a human-readable string (minutes, seconds)."""
    if seconds < 60:
        return f"less than a minute"
    minutes = int(seconds / 60)
    if minutes == 1:
        return f"about 1 minute"
    return f"about {minutes} minutes"


# --- Main Application Class ---
class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Android Backup & Restore Tool")
        self.geometry("950x850") 
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- App State Variables ---
        self.device_id = None
        self.is_operation_running = False
        self.folder_stats = {}
        self.folder_checkboxes = {}
        
        # --- Queues for thread communication ---
        self.log_queue = queue.Queue()
        self.scan_results_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        # --- FIX: Added a dedicated queue for UI state changes ---
        self.ui_queue = queue.Queue()

        # --- UI Elements ---
        self.create_widgets()
        
        # --- Initial Device Check ---
        self.log_message("Welcome! Checking for connected devices...")
        self.log_message(f"Looking for ADB at: {ADB_PATH}")
        self.log_message(f"Backups will be saved to: {BACKUP_DIR}")
        self.check_device_thread()
        
        # --- Start the queue checkers ---
        self.after(100, self.process_log_queue)
        self.after(100, self.process_scan_results_queue)
        self.after(100, self.process_progress_queue)
        self.after(100, self.process_ui_queue)

    def create_widgets(self):
        """Creates and arranges all the UI elements in the window."""
        
        self.tab_view = customtkinter.CTkTabview(self, corner_radius=10)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.tab_view.add("Backup Tool")
        self.tab_view.add("How to Use")

        backup_tab_container = self.tab_view.tab("Backup Tool")
        backup_tab_container.grid_columnconfigure(0, weight=1)
        backup_tab_container.grid_rowconfigure(1, weight=2) 
        backup_tab_container.grid_rowconfigure(3, weight=1) 

        self.main_frame = customtkinter.CTkFrame(backup_tab_container, corner_radius=15)
        self.main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        self.title_label = customtkinter.CTkLabel(self.main_frame, text="Android Backup Tool", font=customtkinter.CTkFont(size=20, weight="bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(20, 10))

        self.status_label = customtkinter.CTkLabel(self.main_frame, text="Status: No Device Connected", text_color="orange", font=customtkinter.CTkFont(size=14))
        self.status_label.grid(row=1, column=0, columnspan=2, padx=20, pady=5)

        self.refresh_button = customtkinter.CTkButton(self.main_frame, text="Refresh Connection", command=self.check_device_thread)
        self.refresh_button.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="ew")

        self.scan_button = customtkinter.CTkButton(self.main_frame, text="Scan Device & Select Folders", command=lambda: self.start_operation(self.scan_device_for_files))
        self.scan_button.grid(row=2, column=1, padx=(10, 20), pady=10, sticky="ew")

        self.backup_selected_button = customtkinter.CTkButton(self.main_frame, text="Backup Selected Folders", command=lambda: self.start_operation(self.backup_selected_folders))
        self.backup_selected_button.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.backup_apps_button = customtkinter.CTkButton(self.main_frame, text="Full App Backup (Advanced)", command=lambda: self.start_operation(self.backup_all_apps))
        self.backup_apps_button.grid(row=4, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.restore_apps_button = customtkinter.CTkButton(self.main_frame, text="Restore Full App Backup", fg_color="#28a745", hover_color="#218838", command=self.handle_restore_button_click)
        self.restore_apps_button.grid(row=5, column=0, columnspan=2, padx=20, pady=10, sticky="ew")

        self.selection_frame = customtkinter.CTkScrollableFrame(backup_tab_container, label_text="Scan Results - Select Folders to Backup")
        self.selection_frame.grid(row=1, column=0, padx=0, pady=10, sticky="nsew")

        self.progress_frame = customtkinter.CTkFrame(backup_tab_container, fg_color="transparent")
        self.progress_frame.grid(row=2, column=0, padx=0, pady=5, sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_frame.grid_columnconfigure(1, weight=0) 

        self.progress_label = customtkinter.CTkLabel(self.progress_frame, text="Progress:")
        self.progress_bar = customtkinter.CTkProgressBar(self.progress_frame)
        self.time_label = customtkinter.CTkLabel(self.progress_frame, text="Time remaining: calculating...")
        
        self.progress_label.grid_remove()
        self.progress_bar.grid_remove()
        self.time_label.grid_remove()

        self.log_textbox = customtkinter.CTkTextbox(backup_tab_container, state="disabled", corner_radius=15, font=("Consolas", 12))
        self.log_textbox.grid(row=3, column=0, padx=0, pady=(10, 0), sticky="nsew")

        self.create_instructions_tab()

    def create_instructions_tab(self):
        """Creates the content for the 'How to Use' tab."""
        instructions_tab = self.tab_view.tab("How to Use")
        instructions_tab.grid_columnconfigure(0, weight=1)
        instructions_tab.grid_rowconfigure(0, weight=1)

        instructions_frame = customtkinter.CTkScrollableFrame(instructions_tab)
        instructions_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        instructions_frame.grid_columnconfigure(0, weight=1)

        def create_text_block(parent, text, font_size=14, is_bold=False, wrap=True):
            font_weight = "bold" if is_bold else "normal"
            label = customtkinter.CTkLabel(parent, text=text, font=customtkinter.CTkFont(size=font_size, weight=font_weight), justify="left", anchor="w")
            if wrap:
                label.bind('<Configure>', lambda e: label.configure(wraplength=label.winfo_width() - 20))
            return label

        welcome_label = create_text_block(instructions_frame, "Welcome to the Android Backup Tool!", 18, True, False)
        welcome_label.pack(anchor="w", padx=10, pady=(10, 5))
        desc_label = create_text_block(instructions_frame, "This tool helps you back up important files and application data from your Android device to your computer.")
        desc_label.pack(anchor="w", fill="x", padx=10, pady=(0, 20))

        step1_title = create_text_block(instructions_frame, "Step 1: Enable USB Debugging on Your Phone", 16, True, False)
        step1_title.pack(anchor="w", padx=10, pady=(10, 5))
        step1_desc = create_text_block(instructions_frame, "This is the most important step. The tool cannot see your phone without it.")
        step1_desc.pack(anchor="w", fill="x", padx=10, pady=(0, 10))
        step1_instructions = [
            "1. Open Settings on your Android device.", "2. Scroll to the bottom and tap on \"About phone\".",
            "3. Find the \"Build number\" and tap on it 7 times in a row. You will see a message saying \"You are now a developer!\".",
            "4. Go back to the main Settings screen.", "5. Find and open the new \"Developer options\" menu (it might be under a \"System\" or \"Advanced\" submenu).",
            "6. Inside Developer options, find and turn ON the switch for \"USB debugging\"."
        ]
        for instruction in step1_instructions:
            label = create_text_block(instructions_frame, instruction)
            label.pack(anchor="w", fill="x", padx=20, pady=2)

        step2_title = create_text_block(instructions_frame, "Step 2: Connect Your Phone", 16, True, False)
        step2_title.pack(anchor="w", padx=10, pady=(20, 5))
        step2_instructions = [
            "1. Connect your phone to your computer using a USB cable.", "2. A pop-up will appear on your phone asking to \"Allow USB debugging?\".",
            "3. Check the box that says \"Always allow from this computer\" and tap \"Allow\".",
            "4. Click the \"Refresh Connection\" button in the \"Backup Tool\" tab. The status should turn green and show \"Connected\"."
        ]
        for instruction in step2_instructions:
            label = create_text_block(instructions_frame, instruction)
            label.pack(anchor="w", fill="x", padx=20, pady=2)
            
        step3_title = create_text_block(instructions_frame, "Step 3: Backing Up Your Data", 16, True, False)
        step3_title.pack(anchor="w", padx=10, pady=(20, 5))
        step3_instructions = [
            "1. Scan: Click \"Scan Device & Select Folders\". This will list all the main folders on your device with a checkbox.",
            "2. Select: Check the boxes next to the folders you want to save.",
            "3. Backup Folders: Click \"Backup Selected Folders\". A progress bar and estimated time remaining will show the status.",
            "4. Backup Apps: For app data and settings, click \"Full App Backup (Advanced)\". You will need to look at your phone screen to approve this."
        ]
        for instruction in step3_instructions:
            label = create_text_block(instructions_frame, instruction)
            label.pack(anchor="w", fill="x", padx=20, pady=2)

        step4_title = create_text_block(instructions_frame, "Step 4: Restoring an App Backup", 16, True, False)
        step4_title.pack(anchor="w", padx=10, pady=(20, 5))
        step4_instructions = [
            "1. Click the \"Restore Full App Backup\" button.",
            "2. A file browser window will open. Navigate to the timestamped backup folder you wish to restore from.",
            "3. Select the \"full_backup.ab\" file and click \"Open\".",
            "4. Look at your phone to approve the restore operation."
        ]
        for instruction in step4_instructions:
            label = create_text_block(instructions_frame, instruction)
            label.pack(anchor="w", fill="x", padx=20, pady=2)


        final_note = create_text_block(instructions_frame, "All your backed-up files will be saved in a timestamped folder inside your computer's \"Documents/AndroidBackup\" folder.", 14, True)
        final_note.pack(anchor="w", fill="x", padx=10, pady=(20, 10))

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple) and message[0] == 'status':
                    _, text, color = message
                    self.status_label.configure(text=text, text_color=color)
                else:
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.insert("end", str(message) + "\n")
                    self.log_textbox.configure(state="disabled")
                    self.log_textbox.see("end")
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_log_queue)

    def process_scan_results_queue(self):
        try:
            self.folder_stats = self.scan_results_queue.get_nowait()
            for widget in self.selection_frame.winfo_children(): widget.destroy()
            self.folder_checkboxes.clear()
            
            if not self.folder_stats: return

            sorted_results = sorted(self.folder_stats.items(), key=lambda item: item[1]['size'], reverse=True)

            for i, (folder, data) in enumerate(sorted_results):
                label_text = f"{folder:<25} | Files: {data['count']:<8} | Size: {format_bytes(data['size'])}"
                checkbox = customtkinter.CTkCheckBox(self.selection_frame, text=label_text, font=("Consolas", 12))
                checkbox.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
                self.folder_checkboxes[folder] = checkbox

        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_scan_results_queue)

    def process_progress_queue(self):
        try:
            while True:
                message = self.progress_queue.get_nowait()
                if isinstance(message, str):
                    if message.startswith("Time:"):
                        self.time_label.configure(text=message)
                    elif message == "start_determinate":
                        self.progress_label.grid(row=0, column=0, padx=5, sticky="w")
                        self.progress_bar.grid(row=1, column=0, padx=5, sticky="ew")
                        self.time_label.grid(row=1, column=1, padx=10, sticky="e")
                        self.progress_bar.configure(mode="determinate")
                        self.progress_bar.set(0)
                    elif message == "start_indeterminate":
                        self.progress_label.grid(row=0, column=0, padx=5, sticky="w")
                        self.progress_bar.grid(row=1, column=0, columnspan=2, padx=5, sticky="ew")
                        self.progress_bar.configure(mode="indeterminate")
                        self.progress_bar.start()
                    elif message == "stop":
                        self.progress_bar.stop()
                        self.progress_label.grid_remove()
                        self.progress_bar.grid_remove()
                        self.time_label.grid_remove()
                    else:
                        self.progress_label.configure(text=message)
                elif isinstance(message, float):
                    self.progress_bar.set(message)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_progress_queue)
            
    # --- FIX: New queue processor for thread-safe UI updates ---
    def process_ui_queue(self):
        try:
            while True:
                message = self.ui_queue.get_nowait()
                if message == 'enable':
                    self.set_ui_state(True)
                elif message == 'disable':
                    self.set_ui_state(False)
        except queue.Empty:
            pass
        finally:
            self.after(100, self.process_ui_queue)

    def log_message(self, message):
        self.log_queue.put(message)

    def set_ui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.refresh_button.configure(state=state)
        self.scan_button.configure(state=state)
        self.backup_selected_button.configure(state=state)
        self.backup_apps_button.configure(state=state)
        self.restore_apps_button.configure(state=state)
        self.is_operation_running = not enabled

    def start_operation(self, target_function, args=()):
        if self.is_operation_running:
            self.log_message("Error: An operation is already in progress.")
            return
        if not self.device_id and target_function != self.check_device:
            self.log_message("Error: No device connected. Please refresh.")
            return
        # --- FIX: Use the queue to disable UI from the main thread ---
        self.ui_queue.put('disable')
        thread = threading.Thread(target=target_function, args=args)
        thread.daemon = True
        thread.start()

    def check_device_thread(self):
        if self.is_operation_running: return
        self.start_operation(self.check_device)

    def check_device(self):
        try:
            if not os.path.exists(ADB_PATH):
                self.log_queue.put(('status', "Status: ADB not found!", "red"))
                self.log_message(f"CRITICAL ERROR: ADB not found at: {ADB_PATH}")
                self.device_id = None
                return
            result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1 and "device" in lines[1]:
                self.device_id = lines[1].split()[0]
                self.log_queue.put(('status', f"Status: Connected to {self.device_id}", "green"))
                self.log_message(f"Success: Device '{self.device_id}' connected.")
            else:
                self.device_id = None
                self.log_queue.put(('status', "Status: No Authorized Device Found", "orange"))
        except subprocess.TimeoutExpired:
            self.device_id = None
            self.log_queue.put(('status', "Status: ADB command timed out", "red"))
            self.log_message("Error: 'adb devices' command took too long to respond. Is the phone connected properly?")
        except Exception as e:
            self.device_id = None
            self.log_queue.put(('status', "Status: Error", "red"))
            self.log_message(f"An error occurred during device check: {e}")
        finally:
            # --- FIX: Use the queue to re-enable the UI ---
            self.ui_queue.put('enable')

    def run_adb_command(self, command_list, return_output=False):
        try:
            process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            stdout_output = []
            if return_output:
                for line in iter(process.stdout.readline, ''): stdout_output.append(line)
            else:
                for line in iter(process.stdout.readline, ''): self.log_message(f"ADB: {line.strip()}")
            for line in iter(process.stderr.readline, ''): self.log_message(f"ADB ERROR: {line.strip()}")
            process.wait()
            if process.returncode == 0: return "".join(stdout_output) if return_output else True
            return None if return_output else False
        except Exception as e:
            self.log_message(f"An unexpected error occurred while running ADB: {e}")
            return None if return_output else False

    def scan_device_for_files(self):
        try:
            self.log_message("--- Starting Device Scan ---")
            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Scanning device... this may take a while.")
            self.scan_results_queue.put({}) 
            command = [ADB_PATH, "shell", "ls", "-lR", "/sdcard/"]
            output = self.run_adb_command(command, return_output=True)
            if output:
                self.log_message("Scan complete. Parsing results...")
                self.progress_queue.put("Parsing results...")
                parsed_stats = self.parse_ls_output(output)
                self.scan_results_queue.put(parsed_stats)
                self.log_message("--- Scan Analysis Finished ---")
            else:
                self.log_message("--- Scan Failed: No data received. ---")
        except Exception as e:
            self.log_message(f"An error occurred during scan: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def parse_ls_output(self, output):
        stats = {}
        current_dir = ""
        file_regex = re.compile(r"^-.*?\s+\d+\s+\w+\s+\w+\s+(\d+)\s+[\d-]+\s+[\d:]+\s+(.+?)\r?$")
        for line in output.splitlines():
            line = line.strip()
            if not line: continue
            if line.startswith('/sdcard/') and line.endswith(':'):
                current_dir = line[:-1]
                continue
            match = file_regex.match(line)
            if match and current_dir:
                try:
                    size = int(match.group(1))
                    relative_path = os.path.relpath(current_dir, "/sdcard")
                    top_folder = relative_path.split(os.path.sep)[0]
                    if top_folder == ".": top_folder = "Internal Storage (Root)"
                    if top_folder not in stats:
                        stats[top_folder] = {'size': 0, 'count': 0}
                    stats[top_folder]['size'] += size
                    stats[top_folder]['count'] += 1
                except (ValueError, IndexError): pass
        return stats

    def backup_selected_folders(self):
        try:
            self.log_message("--- Starting Selected Folder Backup ---")
            
            selected_folders = [folder for folder, checkbox in self.folder_checkboxes.items() if checkbox.get() == 1]

            if not selected_folders:
                self.log_message("No folders selected. Nothing to back up.")
                self.ui_queue.put('enable')
                return

            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            current_backup_path = os.path.join(BACKUP_DIR, timestamp)
            self.log_message(f"Creating new backup in: {current_backup_path}")

            self.progress_queue.put("start_determinate")
            os.makedirs(current_backup_path, exist_ok=True)
            
            total_size = sum(self.folder_stats.get(f, {}).get('size', 0) for f in selected_folders)
            backed_up_size = 0
            
            if total_size > 0:
                estimated_seconds = total_size / (ASSUMED_MB_PER_SECOND * 1024 * 1024)
                self.progress_queue.put(f"Time: ~{format_seconds(estimated_seconds)} remaining")

            for folder in selected_folders:
                self.progress_queue.put(f"Backing up {folder}...")
                dest_path = os.path.join(current_backup_path, folder)
                os.makedirs(dest_path, exist_ok=True)
                
                source_path = f"/sdcard/{folder}" if folder != "Internal Storage (Root)" else "/sdcard/"
                self.run_adb_command([ADB_PATH, "pull", source_path, dest_path])
                
                if total_size > 0:
                    backed_up_size += self.folder_stats.get(folder, {}).get('size', 0)
                    progress = backed_up_size / total_size
                    self.progress_queue.put(progress)
                    
                    remaining_size = total_size - backed_up_size
                    estimated_seconds_left = remaining_size / (ASSUMED_MB_PER_SECOND * 1024 * 1024)
                    self.progress_queue.put(f"Time: ~{format_seconds(estimated_seconds_left)} remaining")

            self.log_message(f"--- Selected Folder Backup Finished. ---")
        except Exception as e:
            self.log_message(f"An error occurred during folder backup: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def backup_all_apps(self):
        try:
            self.log_message("--- Starting Full App Backup ---")
            
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
            current_backup_path = os.path.join(BACKUP_DIR, timestamp)
            self.log_message(f"Creating new app backup in: {current_backup_path}")

            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Performing full app backup... Please check your phone to confirm.")
            os.makedirs(current_backup_path, exist_ok=True)
            backup_file = os.path.join(current_backup_path, "full_backup.ab")

            self.run_adb_command([ADB_PATH, "backup", "-apk", "-shared", "-all", "-f", backup_file])
            self.log_message(f"--- Full backup process complete. File at '{backup_file}' ---")
        except Exception as e:
            self.log_message(f"An error occurred during app backup: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')

    def handle_restore_button_click(self):
        if self.is_operation_running:
            self.log_message("Error: An operation is already in progress.")
            return

        backup_file = filedialog.askopenfilename(
            title="Select Android Backup File",
            initialdir=BACKUP_DIR,
            filetypes=(("Android Backup Files", "*.ab"), ("All files", "*.*"))
        )

        if backup_file:
            self.start_operation(self.restore_all_apps, args=(backup_file,))
        else:
            self.log_message("Restore canceled by user.")

    def restore_all_apps(self, backup_file):
        try:
            self.log_message("--- Starting Full App Restore ---")
            self.log_message(f"Selected backup file for restore: {backup_file}")
            self.progress_queue.put("start_indeterminate")
            self.progress_queue.put("Restoring... Please check your phone to confirm.")
            self.run_adb_command([ADB_PATH, "restore", backup_file])
            self.log_message("--- Full Restore Command Sent. ---")
        except Exception as e:
            self.log_message(f"An error occurred during restore: {e}")
        finally:
            self.progress_queue.put("stop")
            self.ui_queue.put('enable')


if __name__ == "__main__":
    customtkinter.set_appearance_mode("System")
    customtkinter.set_default_color_theme("blue")
    app = App()
    app.mainloop()
