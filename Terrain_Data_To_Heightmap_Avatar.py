import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import io
import os
import glob
from PIL import Image

class TerrainViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Terrain Sector Viewer with Measurements")
        self.root.geometry("1200x850")
        
        self.grid_size = 65
        self.sectors_data = {}
        self.current_directory = ""
        self.max_sectors = 0
        self.show_sector_numbers = tk.BooleanVar(value=True)
        self.current_combined_map = None  # Store current map for export
        
        # Measurement settings - default scale (1 coordinate = 1 meter)
        # Adjust this based on your game's actual scale
        self.meters_per_coordinate = tk.DoubleVar(value=1.0)
        self.unit_system = tk.StringVar(value="Metric")
        
        # Measurement line storage
        self.measurement_line = None
        self.measurement_start = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Directory selection
        dir_frame = ttk.Frame(control_frame)
        dir_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(dir_frame, text="Directory:").pack(side=tk.LEFT)
        self.dir_label = ttk.Label(dir_frame, text="No directory selected", foreground="gray")
        self.dir_label.pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Button(dir_frame, text="Browse", command=self.browse_directory).pack(side=tk.RIGHT)
        
        # Sector grid controls
        grid_frame = ttk.Frame(control_frame)
        grid_frame.pack(fill=tk.X, pady=(0, 10))
        
        # X sectors
        ttk.Label(grid_frame, text="Sectors X:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.sectors_x = tk.IntVar(value=8)
        
        # X Entry field
        self.x_entry = ttk.Entry(grid_frame, textvariable=self.sectors_x, width=8)
        self.x_entry.grid(row=0, column=1, padx=(0, 10))
        self.x_entry.bind('<Return>', self.on_entry_change)
        self.x_entry.bind('<FocusOut>', self.on_entry_change)
        
        # X Scale
        self.x_scale = ttk.Scale(
            grid_frame, 
            from_=1, 
            to=100, 
            variable=self.sectors_x, 
            orient=tk.HORIZONTAL, 
            length=200
        )
        self.x_scale.grid(row=0, column=2, padx=(0, 10))
        
        # Y sectors
        ttk.Label(grid_frame, text="Sectors Y:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.sectors_y = tk.IntVar(value=8)
        
        # Y Entry field
        self.y_entry = ttk.Entry(grid_frame, textvariable=self.sectors_y, width=8)
        self.y_entry.grid(row=1, column=1, padx=(0, 10))
        self.y_entry.bind('<Return>', self.on_entry_change)
        self.y_entry.bind('<FocusOut>', self.on_entry_change)
        
        # Y Scale
        self.y_scale = ttk.Scale(
            grid_frame, 
            from_=1, 
            to=100, 
            variable=self.sectors_y, 
            orient=tk.HORIZONTAL, 
            length=200
        )
        self.y_scale.grid(row=1, column=2, padx=(0, 10))
        
        # Measurement Settings Frame
        measurement_frame = ttk.LabelFrame(control_frame, text="Measurement Settings", padding=5)
        measurement_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Scale setting
        scale_frame = ttk.Frame(measurement_frame)
        scale_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(scale_frame, text="Meters per coordinate:").pack(side=tk.LEFT, padx=(0, 5))
        scale_entry = ttk.Entry(scale_frame, textvariable=self.meters_per_coordinate, width=10)
        scale_entry.pack(side=tk.LEFT, padx=(0, 10))
        scale_entry.bind('<Return>', lambda e: self.update_display())
        
        ttk.Button(scale_frame, text="Set Scale", command=self.update_display).pack(side=tk.LEFT, padx=(0, 10))
        
        # Unit system selection
        ttk.Label(scale_frame, text="Unit System:").pack(side=tk.LEFT, padx=(10, 5))
        unit_combo = ttk.Combobox(
            scale_frame, 
            textvariable=self.unit_system,
            values=["Metric", "Imperial", "Both"],
            state="readonly",
            width=10
        )
        unit_combo.pack(side=tk.LEFT)
        unit_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        # Map size display
        self.map_size_label = ttk.Label(measurement_frame, text="Map Size: Not calculated", foreground="blue", font=('TkDefaultFont', 9, 'bold'))
        self.map_size_label.pack(fill=tk.X, pady=(5, 0))
        
        # Display options
        options_frame = ttk.Frame(control_frame)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Sector numbers toggle
        self.show_numbers_check = ttk.Checkbutton(
            options_frame, 
            text="Show Sector Numbers", 
            variable=self.show_sector_numbers,
            command=self.update_display
        )
        self.show_numbers_check.pack(side=tk.LEFT)
        
        # Export options
        export_frame = ttk.Frame(options_frame)
        export_frame.pack(side=tk.RIGHT)
        
        ttk.Label(export_frame, text="Height Scale:").pack(side=tk.LEFT, padx=(20, 5))
        self.height_scale_var = tk.StringVar(value="16-bit (0-65535)")
        self.height_scale_combo = ttk.Combobox(
            export_frame, 
            textvariable=self.height_scale_var,
            values=["8-bit (0-255)", "16-bit (0-65535)"],
            state="readonly",
            width=15
        )
        self.height_scale_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(export_frame, text="Export Heightmap", command=self.export_heightmap).pack(side=tk.LEFT)
        
        # Info and refresh
        info_frame = ttk.Frame(control_frame)
        info_frame.pack(fill=tk.X)
        
        self.info_label = ttk.Label(info_frame, text="No sectors loaded")
        self.info_label.pack(side=tk.LEFT)
        
        self.display_info = ttk.Label(info_frame, text="")
        self.display_info.pack(side=tk.LEFT, padx=(20, 0))
        
        ttk.Button(info_frame, text="Refresh", command=self.load_sectors).pack(side=tk.RIGHT)
        
        # Matplotlib canvas
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events for measurements
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        
        # Bind slider changes using trace method
        self.sectors_x.trace('w', self.on_value_change)
        self.sectors_y.trace('w', self.on_value_change)
        
    def browse_directory(self):
        directory = filedialog.askdirectory(title="Select directory containing .csdat files")
        if directory:
            self.current_directory = directory
            self.dir_label.config(text=os.path.basename(directory), foreground="black")
            self.load_sectors()
    
    def on_entry_change(self, event):
        """Handle when entry values are changed"""
        try:
            # Validate and clamp values
            x_val = max(1, min(100, self.sectors_x.get()))
            y_val = max(1, min(100, self.sectors_y.get()))
            
            # Update variables if they were clamped
            if x_val != self.sectors_x.get():
                self.sectors_x.set(x_val)
            if y_val != self.sectors_y.get():
                self.sectors_y.set(y_val)
                
        except tk.TclError:
            # If invalid input, reset to previous valid values
            self.sectors_x.set(max(1, min(100, 8)))  # Default fallback
            self.sectors_y.set(max(1, min(100, 8)))
    
    def load_single_sector(self, file_path):
        """Load height map data from a single .csdat file"""
        try:
            height_map = {}
            
            with open(file_path, 'rb') as f:
                f.seek(708)
                terrain_data = io.BytesIO(f.read(16900))
            
            for y in range(self.grid_size):
                row = []
                for x in range(self.grid_size):
                    data = terrain_data.read(2)
                    if len(data) < 2:
                        break
                    height = int.from_bytes(data, 'little') / 128
                    row.append(height)
                    terrain_data.read(2)  # skip unknown data or flags
                height_map[y] = row
            
            # Convert to numpy array for easier manipulation
            height_array = np.array([height_map[y] for y in range(self.grid_size)])
            return height_array
            
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return None
    
    def load_sectors(self):
        """Load all available .csdat files from the selected directory"""
        if not self.current_directory:
            return
        
        self.sectors_data = {}
        pattern = os.path.join(self.current_directory, "sd*.csdat")
        files = glob.glob(pattern)
        
        loaded_count = 0
        sector_numbers = []
        
        for file_path in files:
            filename = os.path.basename(file_path)
            # Extract sector number from filename (sd0.csdat -> 0)
            try:
                sector_num = int(filename[2:-6])  # Remove 'sd' and '.csdat'
                height_data = self.load_single_sector(file_path)
                if height_data is not None:
                    self.sectors_data[sector_num] = height_data
                    sector_numbers.append(sector_num)
                    loaded_count += 1
            except ValueError:
                continue
        
        # Update max sectors and suggest grid size
        if sector_numbers:
            self.max_sectors = max(sector_numbers) + 1
            # Suggest a good grid size based on available sectors
            import math
            suggested_size = math.ceil(math.sqrt(loaded_count))
            if suggested_size <= 100:
                self.sectors_x.set(suggested_size)
                self.sectors_y.set(math.ceil(loaded_count / suggested_size))
        
        self.info_label.config(text=f"Loaded {loaded_count} sectors (0-{max(sector_numbers) if sector_numbers else 0})")
        self.update_display()
    
    def on_value_change(self, *args):
        """Handle when slider values change"""
        # Update the display
        self.update_display()
    
    def format_distance(self, distance_coordinates):
        """Format distance in appropriate units"""
        distance_meters = distance_coordinates * self.meters_per_coordinate.get()
        
        unit_sys = self.unit_system.get()
        
        if unit_sys == "Metric":
            if distance_meters >= 1000:
                return f"{distance_meters/1000:.2f} km"
            else:
                return f"{distance_meters:.2f} m"
        elif unit_sys == "Imperial":
            distance_feet = distance_meters * 3.28084
            distance_miles = distance_feet / 5280
            if distance_miles >= 1:
                return f"{distance_miles:.2f} miles"
            else:
                return f"{distance_feet:.2f} ft"
        else:  # Both
            km = distance_meters / 1000
            miles = distance_meters * 0.000621371
            if distance_meters >= 1000:
                return f"{km:.2f} km / {miles:.2f} miles"
            else:
                feet = distance_meters * 3.28084
                return f"{distance_meters:.2f} m / {feet:.2f} ft"
    
    def calculate_map_size(self):
        """Calculate and display total map dimensions"""
        sectors_x = self.sectors_x.get()
        sectors_y = self.sectors_y.get()
        
        # Calculate total dimensions in coordinates
        total_width_coordinates = sectors_x * self.grid_size
        total_height_coordinates = sectors_y * self.grid_size
        
        # Calculate diagonal
        diagonal_coordinates = np.sqrt(total_width_coordinates**2 + total_height_coordinates**2)
        
        # Format dimensions
        width_str = self.format_distance(total_width_coordinates)
        height_str = self.format_distance(total_height_coordinates)
        diagonal_str = self.format_distance(diagonal_coordinates)
        
        # Calculate area
        area_m2 = (total_width_coordinates * self.meters_per_coordinate.get()) * (total_height_coordinates * self.meters_per_coordinate.get())
        area_km2 = area_m2 / 1_000_000
        area_mi2 = area_km2 * 0.386102
        
        if self.unit_system.get() == "Imperial":
            area_str = f"{area_mi2:.2f} mi²"
        elif self.unit_system.get() == "Both":
            area_str = f"{area_km2:.2f} km² / {area_mi2:.2f} mi²"
        else:
            area_str = f"{area_km2:.2f} km²"
        
        # Update label
        size_text = f"Map Size: {width_str} × {height_str} (diagonal: {diagonal_str}) | Area: {area_str} | Resolution: {total_width_coordinates}×{total_height_coordinates} coordinates"
        self.map_size_label.config(text=size_text)
    
    def on_mouse_press(self, event):
        """Handle mouse press for measurement tool"""
        if event.inaxes != self.ax or event.button != 1:  # Left click only
            return
        
        self.measurement_start = (event.xdata, event.ydata)
        
    def on_mouse_move(self, event):
        """Handle mouse movement for measurement preview"""
        if event.inaxes != self.ax or self.measurement_start is None:
            return
        
        # Remove previous measurement line
        if self.measurement_line:
            try:
                self.measurement_line.remove()
            except:
                pass
            self.measurement_line = None
        
        # Remove previous text
        if hasattr(self, 'measurement_text') and self.measurement_text:
            try:
                self.measurement_text.remove()
            except:
                pass
            self.measurement_text = None
        
        # Draw measurement line
        x_start, y_start = self.measurement_start
        x_end, y_end = event.xdata, event.ydata
        
        self.measurement_line, = self.ax.plot([x_start, x_end], [y_start, y_end], 
                                               'r-', linewidth=2, alpha=0.7)
        
        # Calculate distance
        dx = x_end - x_start
        dy = y_end - y_start
        distance_coordinates = np.sqrt(dx**2 + dy**2)
        
        distance_str = self.format_distance(distance_coordinates)
        
        # Add text annotation
        mid_x = (x_start + x_end) / 2
        mid_y = (y_start + y_end) / 2
        
        self.measurement_text = self.ax.text(mid_x, mid_y, distance_str,
                                             bbox=dict(boxstyle='round,pad=0.5', 
                                                      facecolor='yellow', alpha=0.8),
                                             ha='center', va='center', fontsize=10)
        
        self.canvas.draw_idle()
    
    def on_mouse_release(self, event):
        """Handle mouse release"""
        self.measurement_start = None
        # Clean up measurement visuals
        if self.measurement_line:
            try:
                self.measurement_line.remove()
            except:
                pass
            self.measurement_line = None
        if hasattr(self, 'measurement_text') and self.measurement_text:
            try:
                self.measurement_text.remove()
            except:
                pass
            self.measurement_text = None
        self.canvas.draw_idle()
    
    def export_heightmap(self):
        """Export the current terrain view as a heightmap image"""
        if self.current_combined_map is None:
            messagebox.showwarning("No Data", "No terrain data to export. Please load sectors first.")
            return
        
        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            title="Save Heightmap",
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("TIFF files", "*.tiff"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            # Get the height scaling option
            is_16bit = "16-bit" in self.height_scale_var.get()
            
            # Copy the current map
            height_data = self.current_combined_map.copy()
            
            # Find min and max heights for scaling
            min_height = np.min(height_data)
            max_height = np.max(height_data)
            
            if max_height == min_height:
                # Avoid division by zero if all heights are the same
                scaled_data = np.zeros_like(height_data)
            else:
                # Normalize to 0-1 range first
                normalized_data = (height_data - min_height) / (max_height - min_height)
                
                if is_16bit:
                    # Scale to 16-bit range (0-65535)
                    scaled_data = (normalized_data * 65535).astype(np.uint16)
                    mode = "I;16"  # 16-bit grayscale
                else:
                    # Scale to 8-bit range (0-255)
                    scaled_data = (normalized_data * 255).astype(np.uint8)
                    mode = "L"  # 8-bit grayscale
            
            # Create PIL Image
            image = Image.fromarray(scaled_data, mode=mode)
            
            # Save the image
            image.save(file_path)
            
            # Calculate map dimensions for export info
            height, width = scaled_data.shape
            width_meters = width * self.meters_per_coordinate.get()
            height_meters = height * self.meters_per_coordinate.get()
            
            # Show success message with info
            sectors_x = self.sectors_x.get()
            sectors_y = self.sectors_y.get()
            bit_depth = "16-bit" if is_16bit else "8-bit"
            
            messagebox.showinfo(
                "Export Successful", 
                f"Heightmap exported successfully!\n\n"
                f"File: {os.path.basename(file_path)}\n"
                f"Size: {width}x{height} coordinates\n"
                f"Real Dimensions: {width_meters:.0f}m × {height_meters:.0f}m\n"
                f"Sectors: {sectors_x}x{sectors_y}\n"
                f"Bit Depth: {bit_depth}\n"
                f"Height Range: {min_height:.2f} to {max_height:.2f}\n"
                f"Scaled Range: 0 to {65535 if is_16bit else 255}"
            )
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export heightmap:\n{str(e)}")
    
    def update_display(self):
        """Update the terrain display based on current settings"""
        if not self.sectors_data:
            return
        
        sectors_x = self.sectors_x.get()
        sectors_y = self.sectors_y.get()
        
        # Calculate total grid size
        total_width = sectors_x * self.grid_size
        total_height = sectors_y * self.grid_size
        
        # Create combined height map
        combined_map = np.zeros((total_height, total_width))
        
        # Track which sectors are displayed and missing
        displayed_sectors = []
        missing_sectors = []
        
        # Fill the grid with sectors - bottom-left is sector 0
        for display_row in range(sectors_y):
            for col in range(sectors_x):
                # Convert display row to sector row (flip Y axis)
                # Bottom row (display_row = sectors_y - 1) should be sector row 0
                sector_row = sectors_y - 1 - display_row
                
                # Calculate sector index: row * width + col (bottom-left is 0)
                sector_index = sector_row * sectors_x + col
                
                if sector_index in self.sectors_data:
                    # Calculate position in combined map
                    start_y = display_row * self.grid_size
                    end_y = start_y + self.grid_size
                    start_x = col * self.grid_size
                    end_x = start_x + self.grid_size
                    
                    # FLIP THE SECTOR DATA VERTICALLY (upside down)
                    flipped_sector = np.flipud(self.sectors_data[sector_index])
                    
                    # Place flipped sector data
                    combined_map[start_y:end_y, start_x:end_x] = flipped_sector
                    displayed_sectors.append(sector_index)
                else:
                    missing_sectors.append(sector_index)
        
        # Store current map for export
        self.current_combined_map = combined_map.copy()
        
        # Update display info
        total_slots = sectors_x * sectors_y
        displayed_count = len(displayed_sectors)
        missing_count = len(missing_sectors)
        
        if missing_count > 0:
            self.display_info.config(
                text=f"Showing {displayed_count}/{total_slots} sectors | Missing: {missing_count}",
                foreground="orange"
            )
        else:
            self.display_info.config(
                text=f"Showing {displayed_count}/{total_slots} sectors",
                foreground="green"
            )
        
        # Clear the entire figure to avoid colorbar issues
        self.fig.clear()
        
        # Create new axes
        self.ax = self.fig.add_subplot(111)
        
        # Plot the terrain
        im = self.ax.imshow(combined_map, cmap='terrain', origin='upper', interpolation='bilinear')
        self.ax.set_title(f"Terrain Map ({sectors_x}x{sectors_y} sectors) - Click and drag to measure distances")
        self.ax.set_xlabel(f"X coordinate (coordinates) | Scale: {self.meters_per_coordinate.get()} m/coord")
        self.ax.set_ylabel(f"Y coordinate (coordinates)")
        
        # Add colorbar
        self.fig.colorbar(im, ax=self.ax, label='Height')
        
        # Draw grid lines to show sector boundaries
        for i in range(1, sectors_x):
            self.ax.axvline(i * self.grid_size - 0.5, color='white', alpha=0.5, linewidth=1)
        for i in range(1, sectors_y):
            self.ax.axhline(i * self.grid_size - 0.5, color='white', alpha=0.5, linewidth=1)
        
        # Add sector numbers as text overlays (only if enabled)
        if self.show_sector_numbers.get():
            for display_row in range(sectors_y):
                for col in range(sectors_x):
                    # Convert display row to sector row (flip Y axis)
                    sector_row = sectors_y - 1 - display_row
                    sector_index = sector_row * sectors_x + col
                    
                    center_x = col * self.grid_size + self.grid_size // 2
                    center_y = display_row * self.grid_size + self.grid_size // 2
                    
                    if sector_index in self.sectors_data:
                        # Green text for existing sectors
                        self.ax.text(center_x, center_y, str(sector_index), 
                                   color='lime', fontsize=8, ha='center', va='center',
                                   bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
                    else:
                        # Red text for missing sectors
                        self.ax.text(center_x, center_y, f"{sector_index}\n(missing)", 
                                   color='red', fontsize=6, ha='center', va='center',
                                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
        
        # Calculate and display map size
        self.calculate_map_size()
        
        # Adjust layout and redraw
        self.fig.tight_layout()
        self.canvas.draw()

def main():
    root = tk.Tk()
    app = TerrainViewer(root)
    root.mainloop()

if __name__ == "__main__":
    main()