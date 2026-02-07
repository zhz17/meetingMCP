import tkinter as tk
from tkinter import ttk, messagebox
import backend
from datetime import datetime, timedelta

class MeetingSchedulerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Meeting Scheduler")
        self.root.geometry("1000x800")
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' usually allows for easier color customization than 'vista'
        self.configure_styles()

        # Canvas for scrolling if needed, but we'll try to fit it nicely
        self.main_frame = ttk.Frame(root, padding="20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Data Storage ---
        self.search_results = {} # { "YYYY-MM-DD": [(start, end), ...] }
        self.selected_start_dt = None
        self.selected_end_dt = None

        # --- Section 1: Inputs ---
        self.create_input_section()
        
        # --- Section 2: Results Display (7 Columns) ---
        self.create_results_section()

        # --- Section 3: Booking Controls ---
        self.booking_frame = ttk.Frame(self.main_frame, padding="10 20 10 0")
        self.booking_frame.pack(fill=tk.X, pady=10)
        self.create_booking_section()

    def configure_styles(self):
        # Colors
        bg_color = "#f5f5f5"
        accent_color = "#0078d4" # Microsoft Blue-ish
        text_color = "#333333"
        
        self.root.configure(bg=bg_color)
        
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=text_color, font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=6)
        
        # Custom button style
        self.style.map("TButton",
            background=[('active', '#005a9e'), ('!disabled', accent_color)],
            foreground=[('!disabled', 'white')]
        )
        
        self.style.configure("TEntry", padding=5, font=("Segoe UI", 10))

    def create_input_section(self):
        input_frame = ttk.Frame(self.main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 20))

        # Grid layout for inputs
        input_frame.columnconfigure(1, weight=1)

        # My Email
        ttk.Label(input_frame, text="My Email:", style="Header.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.my_email_var = tk.StringVar()
        self.my_email_entry = ttk.Entry(input_frame, textvariable=self.my_email_var)
        self.my_email_entry.grid(row=0, column=1, sticky=tk.EW, padx=(10, 0), pady=5)

        # Participants
        ttk.Label(input_frame, text="Participates (semi-colon separated):", style="Header.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.participants_var = tk.StringVar()
        self.participants_entry.grid(row=1, column=1, sticky=tk.EW, padx=(10, 0), pady=5)
        
        # Working Hours Checkbox
        self.working_hours_var = tk.BooleanVar(value=False)
        self.working_hours_chk = ttk.Checkbutton(input_frame, text="Working Hours (9:00-17:00)", variable=self.working_hours_var)
        self.working_hours_chk.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # Submit Button
        self.submit_btn = ttk.Button(input_frame, text="Search Availability", command=self.on_submit)
        self.submit_btn.grid(row=2, column=1, pady=(5, 0), sticky=tk.E)

    def create_results_section(self):
        self.results_frame = ttk.Frame(self.main_frame)
        self.results_frame.pack(fill=tk.BOTH, expand=True)
        
        self.day_columns = []
        for i in range(7):
            col_frame = ttk.Frame(self.results_frame, relief="flat", borderwidth=1)
            col_frame.grid(row=0, column=i, sticky=tk.NSEW, padx=2)
            self.results_frame.columnconfigure(i, weight=1)
            
            # Header Label
            header_lbl = ttk.Label(col_frame, text=f"Day {i+1}", style="Header.TLabel", anchor="center")
            header_lbl.pack(fill=tk.X, pady=(0, 5))
            
            # Listbox/Text box to show times
            # Using Listbox for simplicity
            lb = tk.Listbox(col_frame, font=("Segoe UI", 9), height=15, borderwidth=0, highlightthickness=0, bg="white")
            lb.pack(fill=tk.BOTH, expand=True)
            
            self.day_columns.append({"frame": col_frame, "header": header_lbl, "list": lb})

    def create_booking_section(self):
        # Booking controls are hidden initially
        # Start Time
        self.start_label = ttk.Label(self.booking_frame, text="Start Time:", state="disabled")
        self.start_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.start_combo = ttk.Combobox(self.booking_frame, state="disabled", width=25, font=("Segoe UI", 10))
        self.start_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.start_combo.bind("<<ComboboxSelected>>", self.on_start_time_selected)

        # End Time
        self.end_label = ttk.Label(self.booking_frame, text="End Time:", state="disabled")
        self.end_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.end_combo = ttk.Combobox(self.booking_frame, state="disabled", width=15, font=("Segoe UI", 10))
        self.end_combo.pack(side=tk.LEFT, padx=(0, 20))
        self.end_combo.bind("<<ComboboxSelected>>", self.on_end_time_selected)

        # Reserve Button
        self.reserve_btn = ttk.Button(self.booking_frame, text="Reserve Meeting", state="disabled", command=self.on_reserve)
        self.reserve_btn.pack(side=tk.RIGHT)

    def on_submit(self):
        my_email = self.my_email_var.get()
        participants_str = self.participants_var.get()
        participants = [p.strip() for p in participants_str.split(";") if p.strip()]
        
        if not my_email:
            messagebox.showwarning("Input Error", "Please enter your email.")
            return

        # Disable button while searching
        self.submit_btn.config(state="disabled")
        self.root.update()

        # Call Backend
        daily_slots, error = backend.find_free_slots_next_7_working_days(
            my_email, 
            participants, 
            working_hours_only=self.working_hours_var.get()
        )
        
        self.submit_btn.config(state="normal")
        
        if error:
            messagebox.showerror("Error", error)
            return
        
        self.search_results = daily_slots
        self.display_results()
        self.enable_booking_controls()

    def display_results(self):
        # Clear previous
        for col in self.day_columns:
            col["list"].delete(0, tk.END)
            col["header"].config(text="")
        
        sorted_dates = sorted(self.search_results.keys())
        
        for i, date_str in enumerate(sorted_dates):
            if i >= 7: break
            
            slots = self.search_results[date_str]
            weekday_name = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %m/%d")
            
            self.day_columns[i]["header"].config(text=weekday_name)
            
            if not slots:
                self.day_columns[i]["list"].insert(tk.END, "No free time")
            else:
                for start, end in slots:
                    time_str = f"{start.strftime('%H:%M')} - {end.strftime('%H:%M')}"
                    self.day_columns[i]["list"].insert(tk.END, time_str)

    def enable_booking_controls(self):
        self.start_label.config(state="normal")
        self.start_combo.config(state="readonly")
        
        # Populate Start Combobox with all 30-min intervals found
        start_options = []
        
        # We need to map the string back to the actual datetime objects easily
        self.start_time_map = {} 
        
        sorted_dates = sorted(self.search_results.keys())
        for date_str in sorted_dates:
            slots = self.search_results[date_str]
            for start, end in slots:
                # Generate 30 min intervals within this slot
                curr = start
                while curr < end:
                    # Format: "Mon 10/27 10:00"
                    fmt_str = curr.strftime("%a %m/%d %H:%M")
                    start_options.append(fmt_str)
                    self.start_time_map[fmt_str] = (curr, end) # Store the current start and the max end of this block
                    curr += timedelta(minutes=30)
        
        self.start_combo['values'] = start_options
        self.start_combo.set('')
        
        # Reset End Time interaction
        self.end_label.config(state="disabled")
        self.end_combo.config(state="disabled")
        self.end_combo.set('')
        self.reserve_btn.config(state="disabled")

    def on_start_time_selected(self, event):
        selected_str = self.start_combo.get()
        if not selected_str:
            return
        
        start_dt, max_end_dt = self.start_time_map[selected_str]
        self.selected_start_dt = start_dt
        
        # Populate End Time
        # Must be same day, continuous
        # We start from start_dt + 30 mins
        # And go up to max_end_dt
        
        end_options = []
        self.end_time_map = {}
        
        curr = start_dt + timedelta(minutes=30)
        while curr <= max_end_dt:
            fmt_str = curr.strftime("%H:%M")
            end_options.append(fmt_str)
            self.end_time_map[fmt_str] = curr
            curr += timedelta(minutes=30)
            
        self.end_label.config(state="normal")
        self.end_combo.config(state="readonly")
        self.end_combo['values'] = end_options
        self.end_combo.set('')
        self.reserve_btn.config(state="disabled")

    def on_end_time_selected(self, event):
        selected_str = self.end_combo.get()
        if not selected_str:
            return
        
        self.selected_end_dt = self.end_time_map[selected_str]
        self.reserve_btn.config(state="normal")

    def on_reserve(self):
        if not self.selected_start_dt or not self.selected_end_dt:
            return
            
        participants_str = self.participants_var.get()
        participants = [p.strip() for p in participants_str.split(";") if p.strip()]
        
        # Subject and Body hardcoded for now or we could add inputs
        subject = "Meeting Request"
        body = "Hi, \n I am scheduling this meeting for the purpose of ... \n Thanks, "
        
        success, msg = backend.create_outlook_meeting(
            subject, 
            body, 
            participants, 
            self.selected_start_dt, 
            self.selected_end_dt
        )
        
        if success:
            # Maybe clear selection?
            pass
        else:
            messagebox.showerror("Booking Error", msg)

if __name__ == "__main__":
    root = tk.Tk()
    app = MeetingSchedulerApp(root)
    root.mainloop()
