import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Polygon
from matplotlib.collections import PolyCollection
import numpy as np
import io
import os
import glob
import tempfile
import struct
import re
from PIL import Image

class WaterData:
    """Container for water information from a sector"""
    def __init__(self, sector_num):
        self.sector_num = sector_num
        self.material_path = None
        self.has_water = False
        self.water_height = 0.0
        self.file_path = None
        self.file_name = None
        self.hex_offset_material = None
        self.hex_offset_height = None
        
    def __repr__(self):
        if not self.has_water:
            return f"Sector {self.sector_num}: No water"
        
        info = f"Sector {self.sector_num}: Water present\n"
        info += f"  File: {self.file_name}\n"
        if self.material_path:
            info += f"  Material: {self.material_path}\n"
        if self.hex_offset_material is not None:
            info += f"  Material Hex Offset: 0x{self.hex_offset_material:X}\n"
        info += f"  Water Height: {self.water_height:.2f}\n"
        if self.hex_offset_height is not None:
            info += f"  Height Hex Offset: 0x{self.hex_offset_height:X}\n"
        
        return info

class TerrainViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Avatar Terrain & Water Viewer")
        self.root.geometry("1400x900")
        
        self.grid_size = 65
        self.sectors_data = {}
        self.water_data = {}  # sector_num -> WaterData
        self.sectors_textures = {}  # Store texture data
        self.atlas_mapping = {}  # Map sector numbers to actual atlas files
        self.current_directory = ""
        self.max_sectors = 0
        self.show_sector_numbers = tk.BooleanVar(value=True)
        self.current_combined_map = None  # Store current map for export
        
        # Water visualization options
        self.show_water = tk.BooleanVar(value=True)
        self.water_opacity = tk.DoubleVar(value=0.6)
        self.water_color = tk.StringVar(value="Blue")
        
        # Map rotation (default to 90° CCW/270° for sector maps)
        self.map_rotation = tk.IntVar(value=270)  # 0, 90, 180, 270 degrees
        
        # Seam blending options - overlap sectors to align repeated edge features
        self.enable_seam_blending = tk.BooleanVar(value=False)
        self.seam_overlap_pixels = tk.IntVar(value=2)  # Number of pixels to overlap at edges
        self.seam_blend_mode = tk.StringVar(value="Smooth Feather")  # Blending algorithm
        
        # Visual options
        self.show_grid_lines = tk.BooleanVar(value=True)
        
        # Sector ordering configuration
        self.sector_order_pattern = tk.StringVar(value="Avatar Game Layout (2x2 blocks, vertical)")
        
        # Atlas subsector arrangement (how the 4 sectors are arranged in each 2x2 atlas)
        self.atlas_subsector_pattern = tk.StringVar(value="Standard [0=TL, 1=TR, 2=BL, 3=BR]")
        
        # Measurement settings - default scale (1 coordinate = 1 meter)
        # Adjust this based on your game's actual scale
        self.meters_per_coordinate = tk.DoubleVar(value=1.0)
        self.unit_system = tk.StringVar(value="Metric")
        
        # Measurement line storage
        self.measurement_line = None
        self.measurement_start = None

        # Export mode for sector map
        self.export_mode = tk.StringVar(value="Combined PNG")
        
        # Apply pattern to heightmap toggle
        self.apply_pattern_to_heightmap = tk.BooleanVar(value=False)
        
        # Texture layer selection (color, diffuse, mask, shadow)
        self.texture_layer = tk.StringVar(value="color")
        
        # Shadow texture loading options
        self.shadow_folder = ""  # Folder containing converted shadow textures
        self.shadow_format = tk.StringVar(value="dds")  # Format of shadow textures
        
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
        
        # Texture overlay option
        texture_frame = ttk.LabelFrame(control_frame, text="Texture Options", padding=5)
        texture_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.enable_textures = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            texture_frame, 
            text="Show Textures", 
            variable=self.enable_textures,
            command=self.load_sectors
        ).pack(side=tk.LEFT)
        
        # Texture layer selection
        ttk.Label(texture_frame, text="Layer:").pack(side=tk.LEFT, padx=(10, 5))
        layer_combo = ttk.Combobox(
            texture_frame,
            textvariable=self.texture_layer,
            values=["color", "diffuse", "mask", "shadow"],
            state="readonly",
            width=10
        )
        layer_combo.pack(side=tk.LEFT)
        layer_combo.bind('<<ComboboxSelected>>', lambda e: self.reload_textures())
        
        # Display mode selection
        ttk.Label(texture_frame, text="Mode:").pack(side=tk.LEFT, padx=(20, 5))
        self.texture_mode = tk.StringVar(value="Replace")
        mode_combo = ttk.Combobox(
            texture_frame,
            textvariable=self.texture_mode,
            values=["Replace", "Blend", "Side-by-Side"],
            state="readonly",
            width=12
        )
        mode_combo.pack(side=tk.LEFT)
        mode_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        # Brightness boost
        self.enable_brightness = tk.BooleanVar(value=False)
        brightness_check = ttk.Checkbutton(
            texture_frame,
            text="Brightness Boost:",
            variable=self.enable_brightness,
            command=self.update_display
        )
        brightness_check.pack(side=tk.LEFT, padx=(20, 5))
        
        self.texture_brightness = tk.DoubleVar(value=2.5)
        brightness_scale = ttk.Scale(
            texture_frame,
            from_=1.0,
            to=5.0,
            variable=self.texture_brightness,
            orient=tk.HORIZONTAL,
            length=100
        )
        brightness_scale.pack(side=tk.LEFT)
        brightness_scale.bind('<ButtonRelease-1>', lambda e: self.update_display())
        
        # Opacity slider (only for Blend mode)
        self.texture_opacity = tk.DoubleVar(value=0.7)
        ttk.Label(texture_frame, text="Opacity:").pack(side=tk.LEFT, padx=(10, 5))
        opacity_scale = ttk.Scale(
            texture_frame,
            from_=0.0,
            to=1.0,
            variable=self.texture_opacity,
            orient=tk.HORIZONTAL,
            length=100
        )
        opacity_scale.pack(side=tk.LEFT)
        opacity_scale.bind('<ButtonRelease-1>', lambda e: self.update_display())
        
        # Shadow texture loading frame
        shadow_frame = ttk.LabelFrame(control_frame, text="Shadow Texture Loading", padding=5)
        shadow_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(shadow_frame, text="Shadow Folder:").pack(side=tk.LEFT, padx=(0, 5))
        self.shadow_folder_label = ttk.Label(shadow_frame, text="Not selected", foreground="gray")
        self.shadow_folder_label.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(shadow_frame, text="Browse Shadow Folder", command=self.browse_shadow_folder).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(shadow_frame, text="Format:").pack(side=tk.LEFT, padx=(10, 5))
        shadow_format_combo = ttk.Combobox(
            shadow_frame,
            textvariable=self.shadow_format,
            values=["dds", "png"],
            state="readonly",
            width=8
        )
        shadow_format_combo.pack(side=tk.LEFT)
        
        ttk.Label(shadow_frame, text="(Use dropdown for default XBT method)", foreground="gray", font=('TkDefaultFont', 8, 'italic')).pack(side=tk.LEFT, padx=(10, 0))
        
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
        
        # Map transformation options
        transform_frame = ttk.LabelFrame(control_frame, text="Map Rotation", padding=5)
        transform_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Rotation controls
        ttk.Label(transform_frame, text="Rotate sector map:").pack(side=tk.LEFT, padx=(0, 10))
        rotation_options = [("0°", 0), ("90° CW", 90), ("180°", 180), ("90° CCW", 270)]
        for label, value in rotation_options:
            ttk.Radiobutton(
                transform_frame,
                text=label,
                variable=self.map_rotation,
                value=value,
                command=self.update_display
            ).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(transform_frame, text="(only rotates texture display, not terrain heightmap)", foreground="gray", font=('TkDefaultFont', 8, 'italic')).pack(side=tk.LEFT, padx=(10, 0))
        
        # Seam blending options
        seam_frame = ttk.LabelFrame(control_frame, text="Seam Blending (2x2 Grid Transitions)", padding=5)
        seam_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            seam_frame,
            text="Enable Seam Blending",
            variable=self.enable_seam_blending,
            command=self.update_display
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(seam_frame, text="Blend Mode:").pack(side=tk.LEFT, padx=(0, 5))
        blend_mode_combo = ttk.Combobox(
            seam_frame,
            textvariable=self.seam_blend_mode,
            values=["Linear", "Smooth Feather", "Gaussian"],
            state="readonly",
            width=13
        )
        blend_mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        blend_mode_combo.bind('<<ComboboxSelected>>', lambda e: self.on_blend_setting_changed())
        
        ttk.Label(seam_frame, text="Overlap Pixels:").pack(side=tk.LEFT, padx=(0, 5))
        overlap_spinbox = ttk.Spinbox(
            seam_frame,
            from_=1,
            to=10,
            textvariable=self.seam_overlap_pixels,
            width=5,
            command=self.on_blend_setting_changed
        )
        overlap_spinbox.pack(side=tk.LEFT, padx=(0, 5))
        overlap_spinbox.bind('<Return>', lambda e: self.on_blend_setting_changed())
        overlap_spinbox.bind('<FocusOut>', lambda e: self.on_blend_setting_changed())
        
        ttk.Label(seam_frame, text="(overlaps sectors to align repeated edge features)", foreground="gray", font=('TkDefaultFont', 8, 'italic')).pack(side=tk.LEFT, padx=(10, 0))
        
        # Sector ordering options
        ordering_frame = ttk.LabelFrame(control_frame, text="Sector Ordering", padding=5)
        ordering_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ordering_frame, text="Pattern:").pack(side=tk.LEFT, padx=(0, 5))
        order_combo = ttk.Combobox(
            ordering_frame,
            textvariable=self.sector_order_pattern,
            values=[
                "Avatar Game Layout (2x2 blocks, vertical)",
                "Avatar Game Layout - Horizontal",
                "Avatar Game Layout - No Swap",
                "Avatar Game Layout - Swap 0↔3",
                "Bottom-Left Sequential",
                "Top-Left Sequential",
                "Bottom-Right Sequential",
                "Top-Right Sequential",
                "Bottom-Left by Column",
                "Top-Left by Column"
            ],
            state="readonly",
            width=40
        )
        order_combo.pack(side=tk.LEFT)
        order_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        # Add toggle for applying pattern to heightmap
        ttk.Checkbutton(
            ordering_frame,
            text="Apply to Heightmap",
            variable=self.apply_pattern_to_heightmap,
            command=self.update_display
        ).pack(side=tk.LEFT, padx=(10, 0))
        
        ttk.Label(ordering_frame, text="|").pack(side=tk.LEFT, padx=(10, 10))
        ttk.Label(ordering_frame, text="Sector 0 Position:", font=('TkDefaultFont', 9, 'bold')).pack(side=tk.LEFT)
        self.sector_zero_label = ttk.Label(ordering_frame, text="Bottom-Left", foreground="blue")
        self.sector_zero_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Export mode selection
        ttk.Label(ordering_frame, text=" | Export Mode:").pack(side=tk.LEFT, padx=(10, 5))
        self.export_mode_combo = ttk.Combobox(
            ordering_frame,
            textvariable=self.export_mode,
            values=["Combined PNG", "Individual PNGs", "Diagnostic PNG"],
            state="readonly",
            width=15
        )
        self.export_mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(ordering_frame, text="Export Sector Map", command=self.export_sector_diagnostic).pack(side=tk.LEFT)
        
        # Atlas subsector pattern
        atlas_frame = ttk.LabelFrame(control_frame, text="Atlas 2x2 Subsector Arrangement", padding=5)
        atlas_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(atlas_frame, text="Pattern:").pack(side=tk.LEFT, padx=(0, 5))
        atlas_combo = ttk.Combobox(
            atlas_frame,
            textvariable=self.atlas_subsector_pattern,
            values=[
                "Standard [0=TL, 1=TR, 2=BL, 3=BR]",
                "Rotated CW [0=TR, 1=BR, 2=TL, 3=BL]",
                "Rotated CCW [0=BL, 1=TL, 2=BR, 3=TR]",
                "Rotated 180° [0=BR, 1=BL, 2=TR, 3=TL]",
                "Flipped H [0=TR, 1=TL, 2=BR, 3=BL]",
                "Flipped V [0=BL, 1=BR, 2=TL, 3=TR]",
                "By Column [0=TL, 1=BL, 2=TR, 3=BR]",
                "By Column Rev [0=BL, 1=TL, 2=BR, 3=TR]"
            ],
            state="readonly",
            width=35
        )
        atlas_combo.pack(side=tk.LEFT)
        atlas_combo.bind('<<ComboboxSelected>>', lambda e: self.reload_textures())
        
        ttk.Label(atlas_frame, text="|").pack(side=tk.LEFT, padx=(10, 10))
        ttk.Button(atlas_frame, text="Test All Patterns", command=self.test_all_atlas_patterns).pack(side=tk.LEFT)
        
        # Water visualization options
        water_frame = ttk.LabelFrame(control_frame, text="Water Visualization", padding=5)
        water_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Checkbutton(
            water_frame,
            text="Show Water",
            variable=self.show_water,
            command=self.update_display
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(water_frame, text="Color:").pack(side=tk.LEFT, padx=(0, 5))
        water_color_combo = ttk.Combobox(
            water_frame,
            textvariable=self.water_color,
            values=["Blue", "Cyan", "Aqua", "Turquoise", "Light Blue"],
            state="readonly",
            width=12
        )
        water_color_combo.pack(side=tk.LEFT, padx=(0, 10))
        water_color_combo.bind('<<ComboboxSelected>>', lambda e: self.update_display())
        
        ttk.Label(water_frame, text="Opacity:").pack(side=tk.LEFT, padx=(10, 5))
        water_opacity_scale = ttk.Scale(
            water_frame,
            from_=0.0,
            to=1.0,
            variable=self.water_opacity,
            orient=tk.HORIZONTAL,
            length=100
        )
        water_opacity_scale.pack(side=tk.LEFT)
        water_opacity_scale.bind('<ButtonRelease-1>', lambda e: self.update_display())
        
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
        
        # Grid lines toggle
        self.show_grid_check = ttk.Checkbutton(
            options_frame,
            text="Show Grid Lines",
            variable=self.show_grid_lines,
            command=self.update_display
        )
        self.show_grid_check.pack(side=tk.LEFT, padx=(20, 0))
        
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
        
        ttk.Label(export_frame, text="Color:").pack(side=tk.LEFT, padx=(5, 5))
        self.heightmap_color_mode = tk.StringVar(value="Grayscale")
        self.heightmap_color_combo = ttk.Combobox(
            export_frame,
            textvariable=self.heightmap_color_mode,
            values=["Grayscale", "Terrain Colors"],
            state="readonly",
            width=13
        )
        self.heightmap_color_combo.pack(side=tk.LEFT, padx=(0, 10))
        
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
    
    def browse_shadow_folder(self):
        """Browse for folder containing converted shadow textures (DDS or PNG)"""
        directory = filedialog.askdirectory(title="Select folder containing converted shadow textures")
        if directory:
            self.shadow_folder = directory
            self.shadow_folder_label.config(text=os.path.basename(directory), foreground="black")
            print(f"Shadow folder set to: {directory}")
            # Automatically reload textures if shadow layer is currently selected and textures are enabled
            if self.texture_layer.get() == "shadow" and self.enable_textures.get():
                print("Reloading shadow textures from custom folder...")
                self.load_sectors()
            else:
                print("Tip: Select 'shadow' from Layer dropdown and enable 'Show Textures' to load shadows")
    
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
    
    def load_xbt_as_dds(self, xbt_path):
        """Load .xbt file by extracting DDS data after the header"""
        try:
            with open(xbt_path, 'rb') as f:
                # Read the first 4 bytes to verify it's an XBT file
                magic = f.read(4)
                if magic != b'TBX\x00':
                    return None
                
                # Skip the XBT header (32 bytes total)
                # Format: TBX\x00 + 28 bytes of header data
                f.seek(32)
                
                # Read the rest as DDS data
                dds_data = f.read()
                
                # Verify it starts with DDS magic
                if not dds_data.startswith(b'DDS '):
                    return None
                
                # Load DDS using PIL
                # We need to save to a temporary in-memory file
                from io import BytesIO
                dds_buffer = BytesIO(dds_data)
                
                # PIL can read DDS directly (if it has the plugin)
                try:
                    img = Image.open(dds_buffer)
                    img.load()  # Force load the image
                    return img
                except Exception as e:
                    print(f"PIL couldn't load DDS from {xbt_path}: {e}")
                    # Try alternative: save to temp file and load
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix='.dds', delete=False) as tmp:
                        tmp.write(dds_data)
                        tmp_path = tmp.name
                    try:
                        img = Image.open(tmp_path)
                        img.load()
                        os.unlink(tmp_path)
                        return img
                    except Exception as e2:
                        os.unlink(tmp_path)
                        print(f"Failed to load DDS: {e2}")
                        return None
        except Exception as e:
            print(f"Error reading XBT file {xbt_path}: {e}")
            return None
    
    def build_atlas_mapping(self):
        """Build correct mapping between atlas files and sectors.
        
        Standard mapping: Each atlas contains 4 sectors in sequential order.
        Atlas N contains 4 sectors arranged in a 2x2 grid:
        
        Grid layout in each atlas image:
        [0][1]  (top row)
        [2][3]  (bottom row)
        
        For example:
        - atlas0 contains sectors 0,1,2,3
        - atlas2 (atlas index 1) contains sectors 4,5,6,7
        - atlas4 (atlas index 2) contains sectors 8,9,10,11
        
        The Avatar-specific swap is handled in the "Avatar Game Layout" sector ordering pattern.
        """
        if not self.current_directory:
            return
        
        self.atlas_mapping = {}
        self.sector_to_path = {}
        
        texture_layer = self.texture_layer.get()
        
        # Handle shadow layer differently (individual files)
        if texture_layer == "shadow":
            # If shadow folder is set, use that folder
            if self.shadow_folder:
                shadow_dir = self.shadow_folder
                format_ext = self.shadow_format.get()
                print(f"\nLoading shadows from custom folder: {shadow_dir}")
                print(f"Shadow format: {format_ext}")
                
                # Find shadow files in the specified format
                # Look for patterns: sd0_shadow.ext, sd1_shadow.ext, etc.
                shadow_files = glob.glob(os.path.join(shadow_dir, f"sd*_shadow.{format_ext}"))
                # Also try without _shadow suffix: sd0.ext, sd1.ext, etc.
                if not shadow_files:
                    shadow_files = glob.glob(os.path.join(shadow_dir, f"sd*.{format_ext}"))
                    print(f"Using naming pattern: sd*.{format_ext}")
                else:
                    print(f"Using naming pattern: sd*_shadow.{format_ext}")
                
                for filepath in shadow_files:
                    filename = os.path.basename(filepath)
                    try:
                        # Parse sd{num}_shadow.ext or sd{num}.ext
                        if filename.startswith("sd"):
                            if "_shadow" in filename:
                                num_str = filename[2:filename.find('_shadow')]
                            else:
                                # Extract number from sd123.ext
                                num_str = filename[2:filename.rfind('.')]
                            sector = int(num_str)
                            self.sector_to_path[sector] = filepath
                            print(f"  Mapped sector {sector} -> {filename}")
                    except (ValueError, IndexError) as e:
                        print(f"  Skipped {filename}: {e}")
                        continue
                
                print(f"\nFound {len(self.sector_to_path)} {format_ext} shadow files")
                if self.sector_to_path:
                    print(f"Sector range: {min(self.sector_to_path.keys())} to {max(self.sector_to_path.keys())}")
            else:
                # Use default method (XBT from current directory)
                print("Loading shadows using default XBT method from current directory")
                shadow_files = glob.glob(os.path.join(self.current_directory, "sd*_shadow.xbt"))
                shadow_files_dds = glob.glob(os.path.join(self.current_directory, "sd*_shadow.dds"))
                shadow_files.extend(shadow_files_dds)
                
                for filepath in shadow_files:
                    filename = os.path.basename(filepath)
                    try:
                        # Parse sd{num}_shadow.ext
                        if filename.startswith("sd") and "_shadow" in filename:
                            num_str = filename[2:filename.find('_shadow')]
                            sector = int(num_str)
                            self.sector_to_path[sector] = filepath
                    except (ValueError, IndexError):
                        continue
                
                print(f"Found {len(self.sector_to_path)} shadow files for sectors: {sorted(self.sector_to_path.keys())[:10]}..." if len(self.sector_to_path) > 10 else f"Found {len(self.sector_to_path)} shadow files")
            return
        
        # Find all atlas files for the selected layer
        atlas_files = []
        suffix = f"_{texture_layer}"
        if texture_layer == "mask":
            suffix = "_mask"
        
        for ext in ['.xbt', '.dds', '.png', '.tga']:
            pattern = f'atlas*{suffix}{ext}'
            files = glob.glob(os.path.join(self.current_directory, pattern))
            atlas_files.extend(files)
        
        # Extract unique atlas numbers and sort them
        atlas_numbers = set()
        for filepath in atlas_files:
            filename = os.path.basename(filepath)
            # Extract number from "atlas123_color.xbt" -> 123
            try:
                parts = filename.split('_')[0]  # "atlas123"
                num = int(parts.replace('atlas', ''))
                atlas_numbers.add(num)
            except (ValueError, IndexError):
                continue
        
        atlas_numbers = sorted(list(atlas_numbers))
        
        print(f"\nFound {len(atlas_numbers)} {texture_layer} atlas files: {atlas_numbers[:10]}..." if len(atlas_numbers) > 10 else f"\nFound {len(atlas_numbers)} {texture_layer} atlas files: {atlas_numbers}")
        
        # Map each atlas to its 4 sectors (standard sequential mapping)
        for atlas_index, atlas_num in enumerate(atlas_numbers):
            base_sector = atlas_index * 4  # Each atlas covers 4 sectors sequentially
            for sub_sector in range(4):
                sector_num = base_sector + sub_sector
                self.atlas_mapping[sector_num] = (atlas_num, sub_sector)
        
        print(f"Mapped {len(self.atlas_mapping)} sectors to atlas files")
        if self.atlas_mapping:
            sample_sectors = sorted(self.atlas_mapping.keys())[:8]
            print(f"Sample mapping (sector → [atlas, sub-texture]):")
            for s in sample_sectors:
                atlas, sub = self.atlas_mapping[s]
                print(f"  sector {s} → atlas{atlas} sub-texture {sub}")
    
    def get_atlas_subsector_coords(self, sub_sector, half_h, half_w, height, width):
        """Get the coordinates for extracting a subsector from an atlas based on the pattern."""
        pattern = self.atlas_subsector_pattern.get()
        
        # Define quadrant positions
        # TL = Top-Left, TR = Top-Right, BL = Bottom-Left, BR = Bottom-Right
        quadrants = {
            'TL': (0, half_h, 0, half_w),
            'TR': (0, half_h, half_w, width),
            'BL': (half_h, height, 0, half_w),
            'BR': (half_h, height, half_w, width)
        }
        
        # Map sub_sector (0-3) to quadrant based on pattern
        if "Standard" in pattern:
            # Standard extraction from atlas file
            # [0][1]  top row
            # [2][3]  bottom row
            mapping = ['TL', 'TR', 'BL', 'BR']
        elif "Rotated CW" in pattern:
            # Rotated 90° clockwise
            mapping = ['TR', 'BR', 'TL', 'BL']
        elif "Rotated CCW" in pattern:
            # Rotated 90° counter-clockwise
            mapping = ['BL', 'TL', 'BR', 'TR']
        elif "Rotated 180" in pattern:
            # Rotated 180°
            mapping = ['BR', 'BL', 'TR', 'TL']
        elif "Flipped H" in pattern:
            # Flipped horizontally
            mapping = ['TR', 'TL', 'BR', 'BL']
        elif "Flipped V" in pattern:
            # Flipped vertically
            mapping = ['BL', 'BR', 'TL', 'TR']
        elif "By Column Rev" in pattern:
            # By column, bottom to top
            mapping = ['BL', 'TL', 'BR', 'TR']
        elif "By Column" in pattern:
            # By column, top to bottom
            mapping = ['TL', 'BL', 'TR', 'BR']
        else:
            mapping = ['TL', 'TR', 'BL', 'BR']
        
        quadrant = mapping[sub_sector]
        return quadrants[quadrant]
    
    def load_sector_texture(self, sector_num):
        """Try to load texture for a sector using the atlas mapping or individual files"""
        if not self.current_directory:
            return None
        
        texture_layer = self.texture_layer.get()
        
        # Handle shadow layer (individual files)
        if texture_layer == "shadow":
            if sector_num in self.sector_to_path:
                path = self.sector_to_path[sector_num]
                try:
                    if path.endswith('.xbt'):
                        # XBT method
                        img = self.load_xbt_as_dds(path)
                        if img is None:
                            print(f"Failed to load XBT shadow: {path}")
                            return None
                    elif path.endswith('.dds'):
                        # Direct DDS loading
                        print(f"Loading DDS shadow: {path}")
                        img = Image.open(path)
                    elif path.endswith('.png'):
                        # PNG loading
                        print(f"Loading PNG shadow: {path}")
                        img = Image.open(path)
                    else:
                        print(f"Unknown shadow format: {path}")
                        return None
                    
                    # Convert to RGB
                    img = img.convert('RGB')
                    # Resize to match sector grid size
                    sub_img = img.resize((self.grid_size, self.grid_size), Image.Resampling.LANCZOS)
                    print(f"Successfully loaded shadow for sector {sector_num}")
                    return np.array(sub_img)
                except Exception as e:
                    print(f"Error loading shadow texture {path}: {e}")
                    import traceback
                    traceback.print_exc()
            return None
        
        # Check if we have a mapping for this sector (atlas-based)
        if sector_num not in self.atlas_mapping:
            # No atlas available for this sector
            return None
        
        atlas_num, sub_sector = self.atlas_mapping[sector_num]
        
        # Build patterns for the selected layer
        suffix = f"_{texture_layer}"
        if texture_layer == "mask":
            suffix = "_mask"
        
        patterns = [
            f"atlas{atlas_num}{suffix}.xbt",
            f"atlas{atlas_num}{suffix}.dds",
            f"atlas{atlas_num}{suffix}.png",
            f"atlas{atlas_num}{suffix}.tga",
        ]
        
        for pattern in patterns:
            texture_path = os.path.join(self.current_directory, pattern)
            if os.path.exists(texture_path):
                try:
                    # Handle .xbt files specially
                    if pattern.endswith('.xbt'):
                        img = self.load_xbt_as_dds(texture_path)
                        if img is None:
                            continue
                    else:
                        img = Image.open(texture_path)
                    
                    # Convert to RGB
                    img = img.convert('RGB')
                    img_array = np.array(img)
                    
                    # Atlas is 2x2 grid of sub-textures
                    # Extract the correct quadrant based on pattern
                    height, width = img_array.shape[:2]
                    half_h = height // 2
                    half_w = width // 2
                    
                    # Get coordinates based on selected pattern
                    y_start, y_end, x_start, x_end = self.get_atlas_subsector_coords(
                        sub_sector, half_h, half_w, height, width
                    )
                    sub_texture = img_array[y_start:y_end, x_start:x_end]
                    
                    # Convert to PIL Image and resize to match sector grid size
                    sub_img = Image.fromarray(sub_texture)
                    sub_img = sub_img.resize((self.grid_size, self.grid_size), Image.Resampling.LANCZOS)
                    
                    return np.array(sub_img)
                except Exception as e:
                    print(f"Error loading texture {texture_path}: {e}")
        
        return None
    
    def parse_water_from_sector(self, file_path, sector_num):
        """Parse water data from a .csdat file
        
        Water height is stored exactly 4 bytes BEFORE the 'graphics' marker.
        Pattern: [...][4-byte float water height][graphics\\...]
        """
        water = WaterData(sector_num)
        water.file_path = file_path
        water.file_name = os.path.basename(file_path)
        
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Water height is at FIXED offset 0xB0 (176 decimal)
            height_offset = 0xB0
            
            # Check if file is large enough
            if len(data) < height_offset + 4:
                return water
            
            # Read 4 bytes for the float (little-endian) at offset 0xB0-0xB3
            height_bytes = data[height_offset:height_offset + 4]
            
            try:
                # Unpack as little-endian float
                water.water_height = struct.unpack('<f', height_bytes)[0]
                water.hex_offset_height = height_offset
                
                # If water height is non-zero, this sector has water
                if water.water_height != 0.0:
                    water.has_water = True
                    
                    # Try to find water material path for display (optional)
                    water_patterns = [
                        b'graphics\\_materials\\editor\\water_',
                        b'graphics_materials\\editor\\water_'
                    ]
                    
                    graphics_pos = -1
                    for pattern in water_patterns:
                        pos = data.find(pattern)
                        if pos != -1:
                            graphics_pos = pos
                            break
                    
                    if graphics_pos != -1:
                        material_start = graphics_pos
                        material_end = data.find(b'\x00', material_start)
                        if material_end != -1:
                            water.material_path = data[material_start:material_end].decode('latin-1', errors='ignore')
                            water.hex_offset_material = material_start
                        else:
                            water.material_path = data[material_start:material_start+100].decode('latin-1', errors='ignore')
                            water.hex_offset_material = material_start
                    
                    print(f"Water found in sector {sector_num}:")
                    if water.material_path:
                        print(f"  Material path: {water.material_path}")
                        if water.hex_offset_material is not None:
                            print(f"  Material at offset: 0x{water.hex_offset_material:08X}")
                    else:
                        print(f"  Material path: Not found (but water height is non-zero)")
                    print(f"  Water height: {water.water_height:.2f}")
                    if water.hex_offset_height is not None:
                        print(f"  Height at offset: 0x{water.hex_offset_height:08X} (fixed offset 0xB0-0xB3)")
                        print(f"  Height bytes (hex): {height_bytes.hex()}")
                        print(f"  Height bytes (little-endian): {height_bytes[0]:02X} {height_bytes[1]:02X} {height_bytes[2]:02X} {height_bytes[3]:02X}")
                    
            except Exception as e:
                print(f"  Could not read water height: {e}")
                water.water_height = 0.0
                
        except Exception as e:
            print(f"Error parsing water from {file_path}: {e}")
        
        return water
    
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
        
        # First, build the atlas mapping
        self.build_atlas_mapping()
        
        self.sectors_data = {}
        self.water_data = {}  # Clear old water data
        self.sectors_textures = {}  # Clear old textures
        pattern = os.path.join(self.current_directory, "sd*.csdat")
        files = glob.glob(pattern)
        
        loaded_count = 0
        water_count = 0
        sector_numbers = []
        
        print("\n" + "="*70)
        print("LOADING SECTORS AND CHECKING FOR WATER")
        print("="*70)
        
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
                    
                    # Parse water data from this sector
                    water = self.parse_water_from_sector(file_path, sector_num)
                    self.water_data[sector_num] = water
                    if water.has_water:
                        water_count += 1
                        print(f"\n✓ WATER FOUND in Sector {sector_num}")
                        print(f"  File: {filename}")
                        if water.material_path:
                            print(f"  Material: {water.material_path}")
                        print(f"  Water Height: {water.water_height}")
                    
                    # Try to load texture for this sector if enabled
                    if self.enable_textures.get():
                        texture = self.load_sector_texture(sector_num)
                        if texture is not None:
                            self.sectors_textures[sector_num] = texture
            except ValueError:
                continue
        
        print("\n" + "="*70)
        print(f"SUMMARY: Loaded {loaded_count} sectors, found {water_count} with water")
        print("="*70)
        
        # Print detailed water summary
        if water_count > 0:
            print("\n" + "="*70)
            print("WATER SECTORS SUMMARY:")
            print("="*70)
            for sector_num in sorted([s for s, w in self.water_data.items() if w.has_water]):
                water = self.water_data[sector_num]
                print(f"\nSector {sector_num} ({water.file_name}):")
                if water.material_path:
                    print(f"  Material: {water.material_path}")
                if water.hex_offset_material is not None:
                    print(f"  Material Hex Offset: 0x{water.hex_offset_material:08X}")
                print(f"  Water Height: {water.water_height:.2f}")
                if water.hex_offset_height is not None:
                    print(f"  Height Hex Offset: 0x{water.hex_offset_height:08X}")
            print("="*70)
        print()
        
        # Update max sectors and suggest grid size
        if sector_numbers:
            self.max_sectors = max(sector_numbers) + 1
            # Suggest a good grid size based on available sectors
            import math
            suggested_size = math.ceil(math.sqrt(loaded_count))
            if suggested_size <= 100:
                self.sectors_x.set(suggested_size)
                self.sectors_y.set(math.ceil(loaded_count / suggested_size))
        
        texture_layer = self.texture_layer.get()
        texture_info = f" ({len(self.sectors_textures)} {texture_layer} textures)" if self.sectors_textures else ""
        water_info = f" | {water_count} sectors with water" if water_count > 0 else ""
        self.info_label.config(text=f"Loaded {loaded_count} sectors (0-{max(sector_numbers) if sector_numbers else 0}){texture_info}{water_info}")
        
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
    
    def get_sector_index_from_position(self, display_row, col, sectors_x, sectors_y):
        """Calculate sector index based on display position and ordering pattern.
        
        Args:
            display_row: Row position in the display (0 = top)
            col: Column position (0 = left)
            sectors_x: Total columns
            sectors_y: Total rows
            
        Returns:
            sector_index: The sector number to use at this position
        """
        pattern = self.sector_order_pattern.get()
        
        if pattern == "Avatar Game Layout (2x2 blocks, vertical)":
            # Avatar game places 2x2 atlas blocks vertically down
            # 8 grids total (16 sectors), each grid is 2x2
            # Grids are placed vertically starting from top-left
            # Within each 2x2 grid: swap top-right (1) with bottom-left (2)
            # Standard layout: TL=0, TR=1, BL=2, BR=3
            # Avatar layout:   TL=0, TR=2, BL=1, BR=3 (swap 1↔2)
            
            # Calculate which 2x2 block this position belongs to
            block_col = col // 2  # Which column of 2x2 blocks (0 or 1 for 4x2)
            block_row = display_row // 2  # Which row of 2x2 blocks (0-7 for 8 grids)
            
            # Position within the 2x2 block
            within_block_col = col % 2  # 0=left, 1=right within block
            within_block_row = display_row % 2  # 0=top, 1=bottom within block
            
            # Calculate which 2x2 grid this is (going DOWN first, then across)
            # For 4x2 layout with 8 grids vertically:
            # Grid 0 is at top-left, grid 1 is below it, ..., grid 7 is bottom-left
            # Grid 8 would be top-right, grid 9 below it, etc.
            blocks_per_column = sectors_y // 2  # 8 blocks down
            atlas_block_index = block_col * blocks_per_column + block_row
            
            # Base sector for this atlas (each atlas has 4 sectors)
            base_sector = atlas_block_index * 4
            
            # Position within the 2x2 block with Avatar's swap of positions 1 and 2
            # Standard layout: TL=0, TR=1, BL=2, BR=3
            # Avatar swap:     TL=0, TR=2, BL=1, BR=3 (swap 1↔2)
            if within_block_row == 0 and within_block_col == 0:
                offset = 0  # Top-left stays 0
            elif within_block_row == 0 and within_block_col == 1:
                offset = 2  # Top-right gets 2 (swapped from 1)
            elif within_block_row == 1 and within_block_col == 0:
                offset = 1  # Bottom-left gets 1 (swapped from 2)
            else:  # within_block_row == 1 and within_block_col == 1
                offset = 3  # Bottom-right stays 3
            
            sector_index = base_sector + offset
            
        elif pattern == "Avatar Game Layout - Horizontal":
            # Same as vertical but fills ROWS instead of columns
            # 2x2 blocks go across (right), then down
            
            block_col = col // 2
            block_row = display_row // 2
            within_block_col = col % 2
            within_block_row = display_row % 2
            
            # Total number of 2x2 blocks per row
            blocks_per_row = sectors_x // 2
            
            # Calculate which atlas block this is (going across rows)
            atlas_block_index = block_row * blocks_per_row + block_col
            base_sector = atlas_block_index * 4
            
            # Same 1↔2 swap
            if within_block_row == 0 and within_block_col == 0:
                offset = 0
            elif within_block_row == 0 and within_block_col == 1:
                offset = 2  # SWAPPED!
            elif within_block_row == 1 and within_block_col == 0:
                offset = 1  # SWAPPED!
            else:
                offset = 3
            
            sector_index = base_sector + offset
            
        elif pattern == "Avatar Game Layout - No Swap":
            # Vertical layout but NO swap
            block_col = col // 2
            block_row = display_row // 2
            within_block_col = col % 2
            within_block_row = display_row % 2
            blocks_per_column = sectors_y // 2
            atlas_block_index = block_col * blocks_per_column + block_row
            base_sector = atlas_block_index * 4
            
            # Standard order - NO SWAP
            if within_block_row == 0 and within_block_col == 0:
                offset = 0  # TL
            elif within_block_row == 0 and within_block_col == 1:
                offset = 1  # TR  (standard)
            elif within_block_row == 1 and within_block_col == 0:
                offset = 2  # BL  (standard)
            else:
                offset = 3  # BR
            
            sector_index = base_sector + offset
            
        elif pattern == "Avatar Game Layout - Swap 0↔3":
            # Vertical layout but swap 0 with 3 instead
            block_col = col // 2
            block_row = display_row // 2
            within_block_col = col % 2
            within_block_row = display_row % 2
            blocks_per_column = sectors_y // 2
            atlas_block_index = block_col * blocks_per_column + block_row
            base_sector = atlas_block_index * 4
            
            # Swap 0↔3
            if within_block_row == 0 and within_block_col == 0:
                offset = 3  # TL gets BR (SWAPPED!)
            elif within_block_row == 0 and within_block_col == 1:
                offset = 1  # TR  stays
            elif within_block_row == 1 and within_block_col == 0:
                offset = 2  # BL  stays
            else:
                offset = 0  # BR gets TL (SWAPPED!)
            
            sector_index = base_sector + offset
            
        elif pattern == "Bottom-Left Sequential":
            # Bottom-left is sector 0, proceeds right then up
            # Bottom row = sector 0, 1, 2...
            # Next row up = sector sectors_x, sectors_x+1, ...
            sector_row = sectors_y - 1 - display_row
            sector_index = sector_row * sectors_x + col
            
        elif pattern == "Top-Left Sequential":
            # Top-left is sector 0, proceeds right then down
            # Top row = sector 0, 1, 2...
            # Next row down = sector sectors_x, sectors_x+1, ...
            sector_index = display_row * sectors_x + col
            
        elif pattern == "Bottom-Right Sequential":
            # Bottom-right is sector 0, proceeds left then up
            # Bottom row = ..., 2, 1, 0 (right to left)
            sector_row = sectors_y - 1 - display_row
            sector_col = sectors_x - 1 - col
            sector_index = sector_row * sectors_x + sector_col
            
        elif pattern == "Top-Right Sequential":
            # Top-right is sector 0, proceeds left then down
            # Top row = ..., 2, 1, 0 (right to left)
            sector_col = sectors_x - 1 - col
            sector_index = display_row * sectors_x + sector_col
            
        elif pattern == "Bottom-Left by Column":
            # Bottom-left is sector 0, proceeds up then right
            # Left column (bottom to top) = 0, 1, 2...
            # Next column = sectors_y, sectors_y+1, ...
            sector_row = sectors_y - 1 - display_row
            sector_index = col * sectors_y + sector_row
            
        elif pattern == "Top-Left by Column":
            # Top-left is sector 0, proceeds down then right
            # Left column (top to bottom) = 0, 1, 2...
            # Next column = sectors_y, sectors_y+1, ...
            sector_index = col * sectors_y + display_row
            
        else:
            # Default to bottom-left sequential
            sector_row = sectors_y - 1 - display_row
            sector_index = sector_row * sectors_x + col
            
        return sector_index
    
    def reload_textures(self):
        """Reload all textures with the new atlas pattern"""
        if not self.current_directory or not self.enable_textures.get():
            return
        
        # Clear existing textures
        self.sectors_textures = {}
        
        # Reload all textures
        for sector_num in self.sectors_data.keys():
            texture = self.load_sector_texture(sector_num)
            if texture is not None:
                self.sectors_textures[sector_num] = texture
        
        # Update display
        self.update_display()
    
    def test_all_atlas_patterns(self):
        """Create a diagnostic grid showing all atlas pattern variations"""
        if not self.sectors_textures:
            messagebox.showwarning("No Textures", "Please enable and load textures first.")
            return
        
        messagebox.showinfo(
            "Pattern Testing",
            "This will create 8 diagnostic images (one for each atlas pattern).\n\n"
            "Each image will show the texture map with sector numbers overlaid.\n\n"
            "Compare these with your heightmap to find the correct pattern.\n\n"
            "Select a folder to save the diagnostic images."
        )
        
        folder = filedialog.askdirectory(title="Select folder for diagnostic images")
        if not folder:
            return
        
        patterns = [
            "Standard [0=TL, 1=TR, 2=BL, 3=BR]",
            "Rotated CW [0=TR, 1=BR, 2=TL, 3=BL]",
            "Rotated CCW [0=BL, 1=TL, 2=BR, 3=TR]",
            "Rotated 180° [0=BR, 1=BL, 2=TR, 3=TL]",
            "Flipped H [0=TR, 1=TL, 2=BR, 3=BL]",
            "Flipped V [0=BL, 1=BR, 2=TL, 3=TR]",
            "By Column [0=TL, 1=BL, 2=TR, 3=BR]",
            "By Column Rev [0=BL, 1=TL, 2=BR, 3=TR]"
        ]
        
        original_pattern = self.atlas_subsector_pattern.get()
        
        for pattern in patterns:
            # Set pattern
            self.atlas_subsector_pattern.set(pattern)
            
            # Reload textures
            self.reload_textures()
            
            # Export diagnostic
            pattern_name = pattern.split('[')[0].strip().replace(' ', '_').replace('°', 'deg')
            filename = os.path.join(folder, f"atlas_pattern_{pattern_name}.png")
            
            try:
                self._export_diagnostic_to_file(filename)
            except Exception as e:
                print(f"Error exporting pattern {pattern}: {e}")
        
        # Restore original pattern
        self.atlas_subsector_pattern.set(original_pattern)
        self.reload_textures()
        
        messagebox.showinfo(
            "Export Complete",
            f"Diagnostic images saved to:\n{folder}\n\n"
            "Compare these images with your heightmap to find which pattern matches."
        )
    
    def export_sector_diagnostic(self):
        """Export sector texture map based on selected mode"""
        if not self.sectors_textures:
            messagebox.showwarning("No Textures", "Please enable and load textures first.")
            return
        
        mode = self.export_mode.get()
        
        if mode == "Combined PNG":
            file_path = filedialog.asksaveasfilename(
                title="Save Combined Texture Map",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            if not file_path:
                return
            
            try:
                sectors_x = self.sectors_x.get()
                sectors_y = self.sectors_y.get()
                
                total_width = sectors_x * self.grid_size
                total_height = sectors_y * self.grid_size
                
                # Create combined texture map
                combined_texture = np.zeros((total_height, total_width, 3), dtype=np.uint8)
                
                # Fill with textures (match display orientation)
                current_pattern = self.sector_order_pattern.get()
                for display_row in range(sectors_y):
                    for col in range(sectors_x):
                        sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                        
                        start_y = display_row * self.grid_size
                        end_y = start_y + self.grid_size
                        start_x = col * self.grid_size
                        end_x = start_x + self.grid_size
                        
                        if sector_index in self.sectors_textures:
                            # Match the display logic - flip for non-Avatar layouts
                            if current_pattern == "Avatar Game Layout (2x2 blocks, vertical)":
                                combined_texture[start_y:end_y, start_x:end_x] = self.sectors_textures[sector_index]
                            else:
                                flipped_texture = np.flipud(self.sectors_textures[sector_index])
                                combined_texture[start_y:end_y, start_x:end_x] = flipped_texture
                
                # Apply rotation if needed
                rotation = self.map_rotation.get()
                if rotation == 90:
                    combined_texture = np.rot90(combined_texture, k=3)  # Rotate 90° clockwise
                elif rotation == 180:
                    combined_texture = np.rot90(combined_texture, k=2)
                elif rotation == 270:
                    combined_texture = np.rot90(combined_texture, k=1)  # Rotate 90° counter-clockwise
                
                img = Image.fromarray(combined_texture)
                img.save(file_path)
                
                messagebox.showinfo("Export Successful", f"Combined texture map saved to:\n{file_path}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export combined map:\n{str(e)}")
        
        elif mode == "Individual PNGs":
            folder = filedialog.askdirectory(title="Select folder to save individual sector textures")
            if not folder:
                return
            
            try:
                exported_count = 0
                current_pattern = self.sector_order_pattern.get()
                rotation = self.map_rotation.get()
                
                for sector_num in sorted(self.sectors_textures.keys()):
                    texture = self.sectors_textures[sector_num]
                    # Match display orientation
                    if current_pattern == "Avatar Game Layout (2x2 blocks, vertical)":
                        texture_to_export = texture
                    else:
                        texture_to_export = np.flipud(texture)
                    
                    # Apply rotation
                    if rotation == 90:
                        texture_to_export = np.rot90(texture_to_export, k=3)
                    elif rotation == 180:
                        texture_to_export = np.rot90(texture_to_export, k=2)
                    elif rotation == 270:
                        texture_to_export = np.rot90(texture_to_export, k=1)
                    
                    img = Image.fromarray(texture_to_export)
                    
                    filename = f"sector_{sector_num:03d}_texture.png"
                    file_path = os.path.join(folder, filename)
                    
                    img.save(file_path)
                    exported_count += 1
                
                messagebox.showinfo("Export Successful", f"Exported {exported_count} individual sector textures to:\n{folder}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export individual maps:\n{str(e)}")
        
        elif mode == "Diagnostic PNG":
            file_path = filedialog.asksaveasfilename(
                title="Save Sector Diagnostic",
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
            
            try:
                sectors_x = self.sectors_x.get()
                sectors_y = self.sectors_y.get()
                
                total_width = sectors_x * self.grid_size
                total_height = sectors_y * self.grid_size
                
                # Create combined texture map
                combined_texture = np.zeros((total_height, total_width, 3), dtype=np.uint8)
                
                # Fill with textures (match display orientation)
                current_pattern = self.sector_order_pattern.get()
                for display_row in range(sectors_y):
                    for col in range(sectors_x):
                        sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                        
                        start_y = display_row * self.grid_size
                        end_y = start_y + self.grid_size
                        start_x = col * self.grid_size
                        end_x = start_x + self.grid_size
                        
                        if sector_index in self.sectors_textures:
                            # Match the display logic
                            if current_pattern == "Avatar Game Layout (2x2 blocks, vertical)":
                                combined_texture[start_y:end_y, start_x:end_x] = self.sectors_textures[sector_index]
                            else:
                                flipped_texture = np.flipud(self.sectors_textures[sector_index])
                                combined_texture[start_y:end_y, start_x:end_x] = flipped_texture
                
                # Apply rotation if needed
                rotation = self.map_rotation.get()
                if rotation == 90:
                    combined_texture = np.rot90(combined_texture, k=3)  # Rotate 90° clockwise
                elif rotation == 180:
                    combined_texture = np.rot90(combined_texture, k=2)
                elif rotation == 270:
                    combined_texture = np.rot90(combined_texture, k=1)  # Rotate 90° counter-clockwise
                
                # Convert to PIL and draw sector numbers
                from PIL import ImageDraw, ImageFont
                img = Image.fromarray(combined_texture)
                draw = ImageDraw.Draw(img)
                
                # Try to use a good font size
                font_size = max(10, self.grid_size // 5)
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()
                
                # Draw sector numbers and grid lines
                for display_row in range(sectors_y):
                    for col in range(sectors_x):
                        sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                        
                        center_x = col * self.grid_size + self.grid_size // 2
                        center_y = display_row * self.grid_size + self.grid_size // 2
                        
                        # Draw text with background
                        text = str(sector_index)
                        
                        # Get text bounding box
                        bbox = draw.textbbox((center_x, center_y), text, font=font, anchor="mm")
                        
                        # Draw black background rectangle
                        padding = 5
                        draw.rectangle(
                            [bbox[0]-padding, bbox[1]-padding, bbox[2]+padding, bbox[3]+padding],
                            fill='black'
                        )
                        
                        # Draw text in yellow
                        draw.text((center_x, center_y), text, fill='yellow', font=font, anchor="mm")
                        
                        # Draw grid lines
                        if col < sectors_x - 1:
                            draw.line(
                                [(col+1)*self.grid_size, display_row*self.grid_size,
                                 (col+1)*self.grid_size, (display_row+1)*self.grid_size],
                                fill='red', width=2
                            )
                        if display_row < sectors_y - 1:
                            draw.line(
                                [col*self.grid_size, (display_row+1)*self.grid_size,
                                 (col+1)*self.grid_size, (display_row+1)*self.grid_size],
                                fill='red', width=2
                            )
                
                img.save(file_path)
                messagebox.showinfo("Export Successful", f"Sector diagnostic saved to:\n{file_path}\n\nCompare the sector numbers on this texture map with your heightmap to determine the correct ordering pattern.")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export diagnostic:\n{str(e)}")
    
    def _export_diagnostic_to_file(self, file_path, img=None):
        """Helper method to export diagnostic image (used by test_all_atlas_patterns)"""
        if img is None:
            # Create the image
            sectors_x = self.sectors_x.get()
            sectors_y = self.sectors_y.get()
            
            total_width = sectors_x * self.grid_size
            total_height = sectors_y * self.grid_size
            
            # Create combined texture map
            combined_texture = np.zeros((total_height, total_width, 3), dtype=np.uint8)
            
            # Fill with textures
            for display_row in range(sectors_y):
                for col in range(sectors_x):
                    sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                    
                    start_y = display_row * self.grid_size
                    end_y = start_y + self.grid_size
                    start_x = col * self.grid_size
                    end_x = start_x + self.grid_size
                    
                    if sector_index in self.sectors_textures:
                        flipped_texture = np.flipud(self.sectors_textures[sector_index])
                        combined_texture[start_y:end_y, start_x:end_x] = flipped_texture
            
            # Convert to PIL
            from PIL import ImageDraw, ImageFont
            img = Image.fromarray(combined_texture)
        
        draw = ImageDraw.Draw(img)
        
        sectors_x = self.sectors_x.get()
        sectors_y = self.sectors_y.get()
        
        # Try to use a good font size
        font_size = max(10, self.grid_size // 5)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        # Draw sector numbers
        for display_row in range(sectors_y):
            for col in range(sectors_x):
                sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                
                center_x = col * self.grid_size + self.grid_size // 2
                center_y = display_row * self.grid_size + self.grid_size // 2
                
                # Draw text with background
                text = str(sector_index)
                
                # Get text bounding box
                bbox = draw.textbbox((center_x, center_y), text, font=font, anchor="mm")
                
                # Draw black background rectangle
                padding = 5
                draw.rectangle(
                    [bbox[0]-padding, bbox[1]-padding, bbox[2]+padding, bbox[3]+padding],
                    fill='black'
                )
                
                # Draw text in yellow
                draw.text((center_x, center_y), text, fill='yellow', font=font, anchor="mm")
                
                # Draw grid lines
                if col < sectors_x - 1:
                    draw.line(
                        [(col+1)*self.grid_size, display_row*self.grid_size,
                         (col+1)*self.grid_size, (display_row+1)*self.grid_size],
                        fill='red', width=2
                    )
                if display_row < sectors_y - 1:
                    draw.line(
                        [col*self.grid_size, (display_row+1)*self.grid_size,
                         (col+1)*self.grid_size, (display_row+1)*self.grid_size],
                        fill='red', width=2
                    )
        
        img.save(file_path)
    
    def update_sector_zero_label(self):
        """Update the label showing where sector 0 is located"""
        pattern = self.sector_order_pattern.get()
        
        pattern_to_position = {
            "Avatar Game Layout (2x2 blocks, vertical)": "Top-Left (2x2 blocks ↓, swap 2↔3)",
            "Avatar Game Layout - Horizontal": "Top-Left (2x2 blocks →, swap 1↔2)",
            "Avatar Game Layout - No Swap": "Top-Left (2x2 blocks ↓, no swap)",
            "Avatar Game Layout - Swap 0↔3": "Top-Left (2x2 blocks ↓, swap 0↔3)",
            "Bottom-Left Sequential": "Bottom-Left (→ then ↑)",
            "Top-Left Sequential": "Top-Left (→ then ↓)",
            "Bottom-Right Sequential": "Bottom-Right (← then ↑)",
            "Top-Right Sequential": "Top-Right (← then ↓)",
            "Bottom-Left by Column": "Bottom-Left (↑ then →)",
            "Top-Left by Column": "Top-Left (↓ then →)"
        }
        
        position_text = pattern_to_position.get(pattern, "Unknown")
        self.sector_zero_label.config(text=position_text)
    
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
    
    def on_blend_setting_changed(self):
        """Handle when blend settings change - force full update"""
        self.update_display()
    
    def apply_seam_blending(self, sectors_dict, sectors_x, sectors_y, is_texture=True):
        """Apply sector overlapping to align repeated edge features.
        
        Each sector is slightly scaled/cropped to create overlap at edges,
        allowing repeated features to align and blend naturally.
        
        Args:
            sectors_dict: Dictionary of sector_num -> sector_data (numpy array)
            sectors_x: Number of sectors horizontally
            sectors_y: Number of sectors vertically  
            is_texture: Whether this is texture (True) or heightmap (False)
        
        Returns:
            Combined map with overlapped sectors
        """
        overlap = self.seam_overlap_pixels.get()
        if overlap < 1:
            # No overlap, use standard grid assembly
            return None
        
        blend_mode = self.seam_blend_mode.get()
        
        # Calculate new sector size (reduced by overlap on each edge)
        effective_sector_size = self.grid_size - overlap
        
        # Calculate total output size (sectors overlap by 'overlap' pixels)
        total_width = sectors_x * effective_sector_size + overlap
        total_height = sectors_y * effective_sector_size + overlap
        
        # Create output array
        if is_texture:
            combined = np.zeros((total_height, total_width, 3), dtype=np.float32)
        else:
            combined = np.zeros((total_height, total_width), dtype=np.float32)
        
        # Weight accumulator for blending
        weights = np.zeros((total_height, total_width), dtype=np.float32)
        
        # Process each sector
        current_pattern = self.sector_order_pattern.get()
        for display_row in range(sectors_y):
            for col in range(sectors_x):
                # Get the sector index
                sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                
                if sector_index not in sectors_dict:
                    continue
                
                sector_data = sectors_dict[sector_index]
                
                # Apply vertical flip for non-Avatar layouts if needed
                if not is_texture or current_pattern != "Avatar Game Layout (2x2 blocks, vertical)":
                    if is_texture and current_pattern != "Avatar Game Layout (2x2 blocks, vertical)":
                        sector_data = np.flipud(sector_data)
                
                # Calculate position in output (with overlap)
                out_y = display_row * effective_sector_size
                out_x = col * effective_sector_size
                
                # Create a weight mask for this sector (feathered edges)
                sector_weight = np.ones((self.grid_size, self.grid_size), dtype=np.float32)
                
                # Apply feathering based on blend mode
                for edge_pixel in range(overlap):
                    # Calculate blend weight (0 at edge, 1 at overlap distance)
                    if blend_mode == "Linear":
                        weight = edge_pixel / overlap
                    elif blend_mode == "Smooth Feather":
                        t = edge_pixel / overlap
                        weight = t * t * (3 - 2 * t)  # Smoothstep
                    elif blend_mode == "Gaussian":
                        t = edge_pixel / overlap
                        weight = t * t * t * (t * (t * 6 - 15) + 10)  # Smootherstep
                    else:
                        weight = edge_pixel / overlap
                    
                    # Apply weight to edges
                    # Left edge
                    sector_weight[:, edge_pixel] *= weight
                    # Right edge  
                    sector_weight[:, -(edge_pixel + 1)] *= weight
                    # Top edge
                    sector_weight[edge_pixel, :] *= weight
                    # Bottom edge
                    sector_weight[-(edge_pixel + 1), :] *= weight
                
                # Place sector data with weights into combined map
                end_y = min(out_y + self.grid_size, total_height)
                end_x = min(out_x + self.grid_size, total_width)
                
                sector_h = end_y - out_y
                sector_w = end_x - out_x
                
                if is_texture:
                    # For texture (3 channels)
                    for c in range(3):
                        combined[out_y:end_y, out_x:end_x, c] += sector_data[:sector_h, :sector_w, c] * sector_weight[:sector_h, :sector_w]
                else:
                    # For heightmap (1 channel)
                    combined[out_y:end_y, out_x:end_x] += sector_data[:sector_h, :sector_w] * sector_weight[:sector_h, :sector_w]
                
                weights[out_y:end_y, out_x:end_x] += sector_weight[:sector_h, :sector_w]
        
        # Normalize by accumulated weights
        # Avoid division by zero
        weights = np.maximum(weights, 1e-10)
        
        if is_texture:
            for c in range(3):
                combined[:, :, c] /= weights
            return np.clip(combined, 0, 255).astype(np.uint8)
        else:
            combined /= weights
            return combined.astype(np.float32)
    
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
            color_mode = self.heightmap_color_mode.get()
            
            # Copy the current map
            height_data = self.current_combined_map.copy()
            
            # Find min and max heights for scaling
            min_height = np.min(height_data)
            max_height = np.max(height_data)
            
            if color_mode == "Terrain Colors":
                # Export with terrain colormap
                if max_height == min_height:
                    normalized_data = np.zeros_like(height_data)
                else:
                    normalized_data = (height_data - min_height) / (max_height - min_height)
                
                # Apply terrain colormap
                import matplotlib.cm as cm
                terrain_cmap = cm.get_cmap('terrain')
                colored_data = terrain_cmap(normalized_data)
                
                # Convert to RGB (0-255)
                rgb_data = (colored_data[:, :, :3] * 255).astype(np.uint8)
                
                # Create PIL Image
                image = Image.fromarray(rgb_data, mode='RGB')
                mode_text = "RGB Terrain Colors"
                bit_depth = "24-bit RGB"
                
            else:
                # Export as grayscale
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
                mode_text = "Grayscale"
                bit_depth = "16-bit" if is_16bit else "8-bit"
            
            # Save the image
            image.save(file_path)
            
            # Calculate map dimensions for export info
            height, width = height_data.shape
            width_meters = width * self.meters_per_coordinate.get()
            height_meters = height * self.meters_per_coordinate.get()
            
            # Show success message with info
            sectors_x = self.sectors_x.get()
            sectors_y = self.sectors_y.get()
            
            info_message = (
                f"Heightmap exported successfully!\n\n"
                f"File: {os.path.basename(file_path)}\n"
                f"Size: {width}x{height} coordinates\n"
                f"Real Dimensions: {width_meters:.0f}m × {height_meters:.0f}m\n"
                f"Sectors: {sectors_x}x{sectors_y}\n"
                f"Mode: {mode_text}\n"
                f"Bit Depth: {bit_depth}\n"
                f"Height Range: {min_height:.2f} to {max_height:.2f}\n"
            )
            
            if color_mode == "Grayscale":
                info_message += f"Scaled Range: 0 to {65535 if is_16bit else 255}"
            
            messagebox.showinfo("Export Successful", info_message)
            
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
        
        # Create combined texture map (RGB)
        combined_texture = None
        if self.enable_textures.get() and self.sectors_textures:
            combined_texture = np.zeros((total_height, total_width, 3), dtype=np.uint8)
        
        # Track which sectors are displayed and missing
        displayed_sectors = []
        missing_sectors = []
        
        # Update sector 0 position label
        self.update_sector_zero_label()
        
        # Check if we should use seam blending (sector overlap)
        use_seam_blending = self.enable_seam_blending.get() and self.seam_overlap_pixels.get() > 0
        
        if use_seam_blending:
            # Use the new overlapping approach
            # For heightmap
            if self.apply_pattern_to_heightmap.get():
                combined_map = self.apply_seam_blending(self.sectors_data, sectors_x, sectors_y, is_texture=False)
            else:
                # For non-pattern heightmap, create temporary dict with flipped data
                flipped_heightmap_dict = {}
                for sector_num, data in self.sectors_data.items():
                    flipped_heightmap_dict[sector_num] = np.flipud(data)
                combined_map = self.apply_seam_blending(flipped_heightmap_dict, sectors_x, sectors_y, is_texture=False)
            
            # For textures
            if combined_texture is not None and self.sectors_textures:
                combined_texture = self.apply_seam_blending(self.sectors_textures, sectors_x, sectors_y, is_texture=True)
            
            # Track displayed sectors (all sectors that exist)
            displayed_sectors = list(self.sectors_data.keys())
            missing_sectors = []
        else:
            # Standard grid assembly without overlap
            for display_row in range(sectors_y):
                for col in range(sectors_x):
                    # Get sector index for heightmap (always use default Bottom-Left Sequential if toggle is off)
                    if self.apply_pattern_to_heightmap.get():
                        heightmap_sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                    else:
                        # Default: Bottom-Left Sequential for heightmap
                        sector_row = sectors_y - 1 - display_row
                        heightmap_sector_index = sector_row * sectors_x + col
                    
                    # Get sector index for texture (always use the selected pattern)
                    texture_sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                    
                    if heightmap_sector_index in self.sectors_data:
                        # Calculate position in combined map
                        start_y = display_row * self.grid_size
                        end_y = start_y + self.grid_size
                        start_x = col * self.grid_size
                        end_x = start_x + self.grid_size
                        
                        # For heightmap: check if we should apply pattern
                        current_pattern = self.sector_order_pattern.get()
                        if self.apply_pattern_to_heightmap.get() and current_pattern == "Avatar Game Layout (2x2 blocks, vertical)":
                            combined_map[start_y:end_y, start_x:end_x] = self.sectors_data[heightmap_sector_index]
                        else:
                            # FLIP THE SECTOR DATA VERTICALLY (upside down) for default display
                            flipped_sector = np.flipud(self.sectors_data[heightmap_sector_index])
                            combined_map[start_y:end_y, start_x:end_x] = flipped_sector
                        displayed_sectors.append(heightmap_sector_index)
                        
                        # Add texture if available (always use texture_sector_index)
                        if combined_texture is not None and texture_sector_index in self.sectors_textures:
                            # Shadow textures should NOT be flipped, just placed as-is
                            texture_layer = self.texture_layer.get()
                            if texture_layer == "shadow":
                                # Shadow textures: no flip, load as-is
                                combined_texture[start_y:end_y, start_x:end_x] = self.sectors_textures[texture_sector_index]
                            else:
                                # Other textures: apply pattern-based flipping
                                current_pattern = self.sector_order_pattern.get()
                                if current_pattern == "Avatar Game Layout (2x2 blocks, vertical)":
                                    combined_texture[start_y:end_y, start_x:end_x] = self.sectors_textures[texture_sector_index]
                                else:
                                    flipped_texture = np.flipud(self.sectors_textures[texture_sector_index])
                                    combined_texture[start_y:end_y, start_x:end_x] = flipped_texture
                    else:
                        missing_sectors.append(heightmap_sector_index)
        
        # Store current map for export (unrotated heightmap)
        self.current_combined_map = combined_map.copy()
        
        # Apply rotation to texture ONLY (not heightmap)
        rotation = self.map_rotation.get()
        if combined_texture is not None and rotation != 0:
            if rotation == 90:
                combined_texture = np.rot90(combined_texture, k=3)  # Rotate 90° clockwise
            elif rotation == 180:
                combined_texture = np.rot90(combined_texture, k=2)
            elif rotation == 270:
                combined_texture = np.rot90(combined_texture, k=1)  # Rotate 90° counter-clockwise
        
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
        
        # Get display mode
        display_mode = self.texture_mode.get() if hasattr(self, 'texture_mode') else "Replace"
        
        # Create axes based on display mode
        if display_mode == "Side-by-Side" and combined_texture is not None and np.any(combined_texture):
            # Create two side-by-side subplots
            self.ax1 = self.fig.add_subplot(121)
            self.ax2 = self.fig.add_subplot(122)
            
            # Left: Heightmap
            im1 = self.ax1.imshow(combined_map, cmap='terrain', origin='upper', interpolation='nearest')
            self.ax1.set_title(f"Heightmap ({sectors_x}x{sectors_y} sectors)")
            self.ax1.set_xlabel("X coordinate")
            self.ax1.set_ylabel("Y coordinate")
            self.fig.colorbar(im1, ax=self.ax1, label='Height', fraction=0.046)
            
            # Right: Texture with brightness boost
            if self.enable_brightness.get():
                brightness = self.texture_brightness.get()
                boosted_texture = np.clip(combined_texture.astype(float) * brightness, 0, 255).astype(np.uint8)
                texture_normalized = boosted_texture.astype(float) / 255.0
                brightness_text = f" ({brightness:.1f}x brightness)"
            else:
                texture_normalized = combined_texture.astype(float) / 255.0
                brightness_text = ""
            
            self.ax2.imshow(texture_normalized, origin='upper', interpolation='nearest')
            self.ax2.set_title(f"Texture Map{brightness_text}")
            self.ax2.set_xlabel("X coordinate")
            self.ax2.set_ylabel("Y coordinate")
            
            # Add grid lines to both
            if self.show_grid_lines.get():
                for ax in [self.ax1, self.ax2]:
                    for i in range(1, sectors_x):
                        ax.axvline(i * self.grid_size - 0.5, color='white', alpha=0.3, linewidth=0.5)
                    for i in range(1, sectors_y):
                        ax.axhline(i * self.grid_size - 0.5, color='white', alpha=0.3, linewidth=0.5)
            
            # Use ax1 for measurements
            self.ax = self.ax1
            
        else:
            # Single plot
            self.ax = self.fig.add_subplot(111)
            
            # Plot based on mode
            if combined_texture is not None and np.any(combined_texture):
                # Apply brightness boost to texture if enabled
                if self.enable_brightness.get():
                    brightness = self.texture_brightness.get()
                    boosted_texture = np.clip(combined_texture.astype(float) * brightness, 0, 255).astype(np.uint8)
                    texture_normalized = boosted_texture.astype(float) / 255.0
                else:
                    texture_normalized = combined_texture.astype(float) / 255.0
                
                if display_mode == "Replace":
                    # Show only texture (no heightmap colors)
                    self.ax.imshow(texture_normalized, origin='upper', interpolation='nearest')
                    
                    # Still show height as contour lines
                    contour = self.ax.contour(combined_map, levels=15, colors='white', alpha=0.3, linewidths=0.5)
                    
                    if self.enable_brightness.get():
                        brightness = self.texture_brightness.get()
                        title_suffix = f" - Texture view (brightness: {brightness:.1f}x)"
                    else:
                        title_suffix = " - Texture view"
                    show_colorbar = False
                else:  # Blend mode
                    # Show terrain with texture overlay
                    im = self.ax.imshow(combined_map, cmap='terrain', origin='upper', interpolation='nearest')
                    
                    # Overlay texture with transparency
                    opacity = self.texture_opacity.get()
                    self.ax.imshow(texture_normalized, origin='upper', interpolation='nearest', 
                                  alpha=opacity, extent=[0, total_width, total_height, 0])
                    
                    if self.enable_brightness.get():
                        brightness = self.texture_brightness.get()
                        title_suffix = f" - Blended ({opacity:.0%} texture, {brightness:.1f}x brightness)"
                    else:
                        title_suffix = f" - Blended ({opacity:.0%} texture)"
                    show_colorbar = True
            else:
                # Just show heightmap
                im = self.ax.imshow(combined_map, cmap='terrain', origin='upper', interpolation='nearest')
                title_suffix = ""
                show_colorbar = True
            
            self.ax.set_title(f"Terrain Map ({sectors_x}x{sectors_y} sectors){title_suffix} - Click and drag to measure")
            self.ax.set_xlabel(f"X coordinate | Scale: {self.meters_per_coordinate.get()} m/coord")
            self.ax.set_ylabel(f"Y coordinate")
            
            # Add colorbar if showing heightmap
            if show_colorbar and 'im' in locals():
                self.fig.colorbar(im, ax=self.ax, label='Height')
            
            # Draw grid lines to show sector boundaries
            if self.show_grid_lines.get():
                for i in range(1, sectors_x):
                    self.ax.axvline(i * self.grid_size - 0.5, color='white', alpha=0.5, linewidth=1)
                for i in range(1, sectors_y):
                    self.ax.axhline(i * self.grid_size - 0.5, color='white', alpha=0.5, linewidth=1)
        
        # Draw water overlay if enabled
        if self.show_water.get() and self.water_data:
            ax_to_draw = self.ax if display_mode != "Side-by-Side" else self.ax1
            
            # Get water color
            color_map = {
                "Blue": 'blue',
                "Cyan": 'cyan',
                "Aqua": '#00FFFF',
                "Turquoise": 'turquoise',
                "Light Blue": 'lightblue'
            }
            water_color = color_map.get(self.water_color.get(), 'blue')
            water_alpha = self.water_opacity.get()
            
            print("\n" + "="*70)
            print("DRAWING WATER OVERLAYS")
            print("="*70)
            
            # Water should follow the HEIGHTMAP coordinate system, not the display pattern
            # Heightmap uses Bottom-Left Sequential by default (sector 0 = bottom-left)
            for sector_num, water in self.water_data.items():
                if not water.has_water:
                    continue
                
                # Calculate position based on heightmap coordinate system
                # Bottom-Left Sequential: sector 0 is bottom-left, proceeds right then up
                if self.apply_pattern_to_heightmap.get():
                    # If heightmap uses the pattern, water should too
                    # Find which display position corresponds to this sector
                    found = False
                    for display_row in range(sectors_y):
                        for col in range(sectors_x):
                            if self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y) == sector_num:
                                x_start = col * self.grid_size
                                y_start = display_row * self.grid_size
                                found = True
                                break
                        if found:
                            break
                    if not found:
                        continue
                else:
                    # Use standard Bottom-Left Sequential (default heightmap layout)
                    # sector_num = sector_row * sectors_x + col
                    # where sector_row = 0 is BOTTOM row
                    col = sector_num % sectors_x
                    sector_row = sector_num // sectors_x
                    
                    # Convert to display coordinates (display_row = 0 is TOP)
                    display_row = sectors_y - 1 - sector_row
                    
                    x_start = col * self.grid_size
                    y_start = display_row * self.grid_size
                
                print(f"  Sector {sector_num}: Drawing at display position row={display_row}, col={col}")
                print(f"    Pixel position: x={x_start}, y={y_start}")
                print(f"    Water height: {water.water_height:.1f}")
                
                # Draw a semi-transparent rectangle over the sector with water
                water_rect = plt.Rectangle(
                    (x_start, y_start),
                    self.grid_size,
                    self.grid_size,
                    facecolor=water_color,
                    alpha=water_alpha,
                    edgecolor='darkblue',
                    linewidth=2
                )
                ax_to_draw.add_patch(water_rect)
                
                # Add water height label
                center_x = x_start + self.grid_size // 2
                center_y = y_start + self.grid_size // 2
                
                ax_to_draw.text(
                    center_x, center_y,
                    f"Water\nH: {water.water_height:.1f}",
                    color='white',
                    fontsize=7,
                    ha='center',
                    va='center',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='darkblue', alpha=0.8),
                    weight='bold'
                )
            
            print("="*70 + "\n")
        
        # Add sector numbers as text overlays (only if enabled)
        if self.show_sector_numbers.get():
            ax_to_label = self.ax if display_mode != "Side-by-Side" else self.ax1
            for display_row in range(sectors_y):
                for col in range(sectors_x):
                    # Get sector index based on ordering pattern
                    sector_index = self.get_sector_index_from_position(display_row, col, sectors_x, sectors_y)
                    
                    center_x = col * self.grid_size + self.grid_size // 2
                    center_y = display_row * self.grid_size + self.grid_size // 2
                    
                    if sector_index in self.sectors_data:
                        # Skip if water is shown on this sector (to avoid overlap)
                        if self.show_water.get() and sector_index in self.water_data and self.water_data[sector_index].has_water:
                            continue
                        
                        # Green text for existing sectors
                        ax_to_label.text(center_x, center_y, str(sector_index), 
                                   color='lime', fontsize=8, ha='center', va='center',
                                   bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.7))
                    else:
                        # Red text for missing sectors
                        ax_to_label.text(center_x, center_y, f"{sector_index}\n(missing)", 
                                   color='red', fontsize=6, ha='center', va='center',
                                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))
        
        # Add legend if water is shown
        if self.show_water.get() and any(w.has_water for w in self.water_data.values()):
            from matplotlib.patches import Patch
            
            color_map = {
                "Blue": 'blue',
                "Cyan": 'cyan',
                "Aqua": '#00FFFF',
                "Turquoise": 'turquoise',
                "Light Blue": 'lightblue'
            }
            water_color = color_map.get(self.water_color.get(), 'blue')
            
            legend_elements = [
                Patch(facecolor=water_color, alpha=self.water_opacity.get(), 
                      edgecolor='darkblue', label='Water Area')
            ]
            
            ax_for_legend = self.ax if display_mode != "Side-by-Side" else self.ax1
            ax_for_legend.legend(handles=legend_elements, loc='upper right', fontsize=8)
        
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