import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import copy # Nesne kopyalamak için gerekli

# ==========================================
# 1. DATA STRUCTURES & LOGIC
# ==========================================

class Task:
    def __init__(self, name, release, execution, period, deadline, task_type):
        self.name = name
        self.release = float(release)
        self.execution = float(execution)
        self.period = float(period) if period else 0.0
        self.deadline = float(deadline) if deadline else 0.0
        self.task_type = task_type
        
        # Scheduling state management
        self.next_release = 0.0
        # Bu değerler artık instance (kopya) üzerinde takip edilecek
        self.current_job_rem = 0.0
        self.current_abs_deadline = 0.0
        self.instance_id = 0 # Görselleştirmede karışıklığı önlemek için

class Scheduler:
    def __init__(self):
        self.tasks = []
        self.step_size = 0.01 
        self.epsilon = 1e-5
        self.llf_threshold = 0.1 

    def parse_input(self, file_path):
        self.tasks = []
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            p_count = 1
            a_count = 1
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                type_char = parts[0]
                
                if type_char == 'P':
                    # P ri ei pi di
                    if len(parts) == 5:
                        t = Task(f"P{p_count}", parts[1], parts[2], parts[3], parts[4], 'Periodic')
                    elif len(parts) == 4:
                        t = Task(f"P{p_count}", parts[1], parts[2], parts[3], parts[3], 'Periodic')
                    elif len(parts) == 3:
                        t = Task(f"P{p_count}", 0.0, parts[1], parts[2], parts[2], 'Periodic')
                    self.tasks.append(t)
                    p_count += 1
                    
                elif type_char == 'D':
                    # D ei pi di -> Genelde r=0 kabul edilir
                    t = Task(f"P{p_count}", 0.0, parts[1], parts[2], parts[3], 'Periodic')
                    self.tasks.append(t)
                    p_count += 1
                    
                elif type_char == 'A':
                    t = Task(f"A{a_count}", parts[1], parts[2], 0.0, 99999.0, 'Aperiodic')
                    self.tasks.append(t)
                    a_count += 1

            return True, f"Loaded {len(self.tasks)} tasks."
        except Exception as e:
            return False, str(e)

    def run_simulation(self, algo, server_type, s_period, s_budget, sim_duration):
        time_log = [] 
        ready_queue = [] # Artık Task'ların KOPYALARINI (Instance) tutacak
        aperiodic_queue = []
        
        server = {
            'period': float(s_period),
            'budget': float(s_budget),
            'current_budget': float(s_budget) if server_type != 'Background' else 0.0,
            'deadline': float(s_period),
            'type': server_type,
            'next_replenishment': float(s_period)
        }
        
        # Task tanımlarını hazırla
        sim_tasks = []
        for t in self.tasks:
            new_t = Task(t.name, t.release, t.execution, t.period, t.deadline, t.task_type)
            if new_t.task_type == 'Periodic' and new_t.release == 0:
                new_t.next_release = 0.0
            else:
                new_t.next_release = new_t.release
            sim_tasks.append(new_t)

        current_time = 0.0
        last_task_name = None
        current_block_start = 0.0
        
        error_info = None 
        fail_time = 0.0
        
        previous_selected_task = None

        while current_time < sim_duration:
            
            # --- 1. DEADLINE CHECK ---
            # Kuyruktaki her işin kendi absolute deadline'ını kontrol et
            for job in ready_queue:
                if current_time > job.current_abs_deadline + self.epsilon:
                    error_info = f"DEADLINE MISSED!\nTask: {job.name}"
                    fail_time = current_time
                    break
            
            if error_info:
                if last_task_name is not None:
                    time_log.append((current_block_start, current_time, last_task_name))
                break 

            # --- 2. ARRIVALS (Multi-Instance Support) ---
            for t in sim_tasks:
                if t.task_type == 'Periodic':
                    # Release zamanı geldi mi? (Float toleransı ile)
                    if t.next_release <= current_time + self.epsilon:
                        
                        # YENİ MANTIK: Eski iş bitmese bile yeni iş eklenir (Overlap serbest)
                        # Görevin bir kopyasını oluştur (Job Instance)
                        new_job = copy.copy(t)
                        new_job.current_job_rem = t.execution
                        new_job.current_abs_deadline = t.next_release + t.deadline # Absolute Deadline = Release + Relative D
                        new_job.instance_id += 1
                        
                        ready_queue.append(new_job)
                        
                        # Bir sonraki periyodu ayarla
                        t.next_release += t.period
                
                elif t.task_type == 'Aperiodic':
                    if abs(current_time - t.release) < self.step_size:
                        t.current_job_rem = t.execution
                        if t not in aperiodic_queue:
                            aperiodic_queue.append(t)

            # --- 3. SERVER REPLENISHMENT ---
            if server_type != 'Background':
                if abs(current_time - server['next_replenishment']) < self.step_size:
                    server['current_budget'] = server['budget']
                    server['deadline'] = current_time + server['period']
                    server['next_replenishment'] += server['period']
                    if server_type == 'Poller' and not aperiodic_queue:
                         server['current_budget'] = 0.0

            # --- 4. SCHEDULING DECISION ---
            selected_task = None
            server_active = False

            candidates = list(ready_queue)
            
            if server_type != 'Background' and aperiodic_queue and server['current_budget'] > self.epsilon:
                server_dummy = Task("Server", 0, server['current_budget'], server['period'], server['period'], 'Server')
                server_dummy.current_abs_deadline = server['deadline']
                server_dummy.remaining_time = server['current_budget']
                candidates.append(server_dummy)

            if not candidates:
                if server_type == 'Background' and aperiodic_queue:
                    selected_task = aperiodic_queue[0]
                else:
                    selected_task = None
            else:
                if algo == 'Rate Monotonic (RM)':
                    # RM: Static Priority based on Period
                    candidates.sort(key=lambda x: x.period)
                    selected_task = candidates[0]
                    
                elif algo == 'Deadline Monotonic (DM)':
                    # DM: Static Priority based on Relative Deadline
                    candidates.sort(key=lambda x: x.deadline) 
                    selected_task = candidates[0]
                    
                elif algo == 'Earliest Deadline First (EDF)':
                    # EDF: Dynamic Priority based on Absolute Deadline
                    candidates.sort(key=lambda x: x.current_abs_deadline)
                    selected_task = candidates[0]
                    
                elif algo == 'Least Laxity First (LLF)':
                    def get_laxity(tsk):
                        rem = tsk.current_job_rem if tsk.name != "Server" else server['current_budget']
                        return tsk.current_abs_deadline - current_time - rem

                    candidates.sort(key=get_laxity)
                    best_candidate = candidates[0]

                    if previous_selected_task and previous_selected_task in candidates:
                        current_laxity = get_laxity(previous_selected_task)
                        best_laxity = get_laxity(best_candidate)
                        
                        if (current_laxity - best_laxity) < self.llf_threshold:
                            selected_task = previous_selected_task
                        else:
                            selected_task = best_candidate
                    else:
                        selected_task = best_candidate

                if selected_task and selected_task.name == "Server":
                    server_active = True
                    selected_task = aperiodic_queue[0] if aperiodic_queue else None

            # --- 5. EXECUTION ---
            task_name_to_log = "Idle"
            
            if selected_task:
                task_name_to_log = selected_task.name
                
                if server_active:
                    previous_selected_task = None 
                else:
                    previous_selected_task = selected_task

                decrement = self.step_size
                if selected_task.current_job_rem < decrement:
                    decrement = selected_task.current_job_rem

                selected_task.current_job_rem -= decrement
                
                if server_active:
                    server['current_budget'] -= decrement
                    if selected_task.current_job_rem <= self.epsilon:
                        aperiodic_queue.pop(0)
                        previous_selected_task = None 
                else:
                    if selected_task.current_job_rem <= self.epsilon:
                        # İş bitti, kuyruktan çıkar
                        if selected_task in ready_queue:
                            ready_queue.remove(selected_task)
                        elif server_type == 'Background' and selected_task in aperiodic_queue:
                            aperiodic_queue.remove(selected_task)
                        previous_selected_task = None 
            else:
                previous_selected_task = None

            # Log Optimization
            if task_name_to_log != last_task_name:
                if last_task_name is not None:
                    time_log.append((current_block_start, current_time, last_task_name))
                last_task_name = task_name_to_log
                current_block_start = current_time
            
            current_time += self.step_size

        if not error_info and last_task_name is not None:
            time_log.append((current_block_start, current_time, last_task_name))
            
        return time_log, sim_tasks, error_info, fail_time

# ==========================================
# 2. USER INTERFACE
# ==========================================

class ModernRTSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Real-Time Scheduling Simulator (Multi-Instance Support)")
        self.root.geometry("1100x700")
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.colors = {
            "bg": "#f4f6f9",
            "panel_bg": "#ffffff",
            "primary": "#3498db",
            "text": "#2c3e50",
            "accent": "#e74c3c"
        }
        self.root.configure(bg=self.colors["bg"])
        
        self.scheduler = Scheduler()
        self.file_path = None
        
        self.budget_options = [str(i) for i in range(1, 4)]
        self.period_options = [str(i) for i in range(5, 16)]

        self.setup_layout()

    def setup_layout(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left_panel = tk.Frame(self.root, bg=self.colors["panel_bg"], width=300, padx=20, pady=20)
        left_panel.grid(row=0, column=0, sticky="ns")
        left_panel.grid_propagate(False)

        lbl_title = tk.Label(left_panel, text="RTS Configurator", font=("Helvetica", 16, "bold"), 
                             bg=self.colors["panel_bg"], fg=self.colors["text"])
        lbl_title.pack(pady=(0, 20), anchor="w")

        self.create_section_header(left_panel, "1. Input Data")
        
        btn_browse = ttk.Button(left_panel, text="Load Input File (.txt)", command=self.load_file)
        btn_browse.pack(fill="x", pady=5)
        
        self.lbl_filename = tk.Label(left_panel, text="No file loaded", bg="#ecf0f1", fg="#7f8c8d", 
                                     font=("Consolas", 9), anchor="w", padx=5, pady=5)
        self.lbl_filename.pack(fill="x", pady=(0, 15))

        self.create_section_header(left_panel, "2. Scheduling Algorithm")
        self.combo_algo = ttk.Combobox(left_panel, state="readonly", values=[
            "Rate Monotonic (RM)", 
            "Deadline Monotonic (DM)", 
            "Earliest Deadline First (EDF)",
            "Least Laxity First (LLF)"
        ])
        self.combo_algo.current(0)
        self.combo_algo.pack(fill="x", pady=(0, 15))

        self.create_section_header(left_panel, "3. Server Settings")
        
        tk.Label(left_panel, text="Server Type:", bg=self.colors["panel_bg"]).pack(anchor="w")
        self.combo_server = ttk.Combobox(left_panel, state="readonly", values=["Background", "Poller", "Deferrable"])
        self.combo_server.current(0)
        self.combo_server.pack(fill="x", pady=5)
        self.combo_server.bind("<<ComboboxSelected>>", self.toggle_server_inputs)

        server_params_frame = tk.Frame(left_panel, bg=self.colors["panel_bg"])
        server_params_frame.pack(fill="x", pady=5)
        
        tk.Label(server_params_frame, text="Budget (Cs):", bg=self.colors["panel_bg"]).grid(row=0, column=0, sticky="w")
        self.combo_budget = ttk.Combobox(server_params_frame, state="readonly", values=self.budget_options, width=10)
        self.combo_budget.current(0)
        self.combo_budget.grid(row=0, column=1, padx=5, pady=2)
        
        tk.Label(server_params_frame, text="Period (Ts):", bg=self.colors["panel_bg"]).grid(row=1, column=0, sticky="w")
        self.combo_period = ttk.Combobox(server_params_frame, state="readonly", values=self.period_options, width=10)
        self.combo_period.current(0)
        self.combo_period.grid(row=1, column=1, padx=5, pady=2)
        
        self.toggle_server_inputs(None)

        self.create_section_header(left_panel, "4. Duration")
        self.entry_duration = ttk.Entry(left_panel)
        self.entry_duration.insert(0, "20")
        self.entry_duration.pack(fill="x", pady=(0, 20))

        style_btn = ttk.Style()
        style_btn.configure("Accent.TButton", font=("Helvetica", 10, "bold"), foreground="black")
        
        btn_run = ttk.Button(left_panel, text="RUN SIMULATION", style="Accent.TButton", command=self.run_sim)
        btn_run.pack(fill="x", pady=10, ipady=5)

        right_panel = tk.Frame(self.root, bg="white")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.figure, self.ax = plt.subplots(figsize=(8, 6))
        self.figure.patch.set_facecolor('white')
        self.canvas = FigureCanvasTkAgg(self.figure, master=right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        self.ax.text(0.5, 0.5, "Please load a file and run simulation", 
                     horizontalalignment='center', verticalalignment='center', transform=self.ax.transAxes,
                     color='gray', fontsize=12)
        self.ax.axis('off')
        self.canvas.draw()

    def create_section_header(self, parent, text):
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), 
                       fg=self.colors["primary"], bg=self.colors["panel_bg"])
        lbl.pack(anchor="w", pady=(10, 5))
        separator = ttk.Separator(parent, orient='horizontal')
        separator.pack(fill='x', pady=(0, 10))

    def toggle_server_inputs(self, event):
        val = self.combo_server.get()
        if val == "Background":
            self.combo_budget.config(state='disabled')
            self.combo_period.config(state='disabled')
        else:
            self.combo_budget.config(state='readonly')
            self.combo_period.config(state='readonly')

    def load_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if filename:
            self.file_path = filename
            display_name = filename.split("/")[-1]
            if len(display_name) > 25: display_name = display_name[:22] + "..."
            self.lbl_filename.config(text=display_name, fg="black")
            success, msg = self.scheduler.parse_input(filename)
            if not success:
                messagebox.showerror("Error", msg)

    def run_sim(self):
        if not self.file_path:
            messagebox.showwarning("Warning", "Please load an input file first.")
            return

        algo = self.combo_algo.get()
        server_type = self.combo_server.get()
        
        s_budget = 0.0
        s_period = 1.0 
        
        if server_type != "Background":
            try:
                s_budget = float(self.combo_budget.get())
                s_period = float(self.combo_period.get())
            except ValueError:
                messagebox.showerror("Input Error", "Server Budget or Period error.")
                return

        try:
            sim_dur = float(self.entry_duration.get())
        except ValueError:
            sim_dur = 50.0

        log, task_list, error_info, fail_time = self.scheduler.run_simulation(algo, server_type, s_period, s_budget, sim_dur)
        self.draw_gantt(log, task_list, sim_dur, error_info, fail_time)
        
        if error_info:
            messagebox.showerror("Scheduling Aborted", f"{error_info}\nTime: {fail_time:.2f}")

    def draw_gantt(self, log, task_list, duration, error_info, fail_time):
        self.ax.clear()
        self.ax.axis('on')
        
        unique_tasks = sorted(list(set([t.name for t in task_list])))
        colors = plt.cm.get_cmap('Pastel1', len(unique_tasks) + 1)
        
        y_pos = {name: i for i, name in enumerate(unique_tasks)}
        
        self.ax.grid(True, which='both', axis='x', linestyle='--', linewidth=0.5, color='gray', alpha=0.3)
        self.ax.set_axisbelow(True)

        for start, end, task_name in log:
            if task_name == "Idle":
                continue
            idx = y_pos[task_name]
            width = end - start
            
            self.ax.broken_barh([(start, width)], (idx - 0.3, 0.6), facecolors=colors(idx), edgecolor='none')

        if error_info:
            self.ax.axvline(x=fail_time, color='red', linestyle='-', linewidth=2.5)
            self.ax.annotate('DEADLINE MISS', xy=(fail_time, len(unique_tasks)-0.5), 
                             xytext=(fail_time, len(unique_tasks)+0.2),
                             color='red', fontweight='bold', ha='center',
                             arrowprops=dict(facecolor='red', shrink=0.05))

        self.ax.set_ylim(-1, len(unique_tasks))
        
        if error_info:
            self.ax.set_xlim(0, fail_time + 1.0)
        else:
            self.ax.set_xlim(0, duration)
        
        self.ax.set_xlabel('Time Units (s)', fontsize=10, fontweight='bold')
        self.ax.set_yticks(range(len(unique_tasks)))
        self.ax.set_yticklabels(unique_tasks, fontsize=10, fontweight='bold')
        
        title_str = f"Scheduling: {self.combo_algo.get()} | Server: {self.combo_server.get()}"
        if error_info:
            title_str += " [ABORTED]"
            
        self.ax.set_title(title_str, fontsize=12, pad=10, color='red' if error_info else self.colors["text"])
        
        self.figure.tight_layout()
        self.canvas.draw()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    app = ModernRTSApp(root)
    root.mainloop()