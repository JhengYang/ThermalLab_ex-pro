"""
Image processing utilities for FLIR thermal images.
Handles: thermal data extraction, edge detection, alignment, 
background removal, and temperature sampling.
"""
import os
import uuid
import numpy as np
import cv2
from PIL import Image
import io
import subprocess
import json
import struct

# Directory for processed images
UPLOAD_DIR = os.environ.get('FLIR_UPLOAD_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads'))
PROCESSED_DIR = os.environ.get('FLIR_PROCESSED_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'processed'))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


def extract_thermal_data_exiftool(thermal_path):
    """
    Extract raw thermal data from FLIR RJPG using exiftool + Planck's law.
    Falls back to image-based color estimation if exiftool is not available.
    Returns a 2D numpy array of temperatures in Celsius.
    """
    # Method 1: Try exiftool with Planck's law (most accurate)
    try:
        thermal = _extract_with_exiftool_planck(thermal_path)
        if thermal is not None:
            print(f"[Thermal] Extracted via exiftool+Planck: shape={thermal.shape}, "
                  f"range={thermal.min():.2f}~{thermal.max():.2f}°C")
            return thermal
    except Exception as e:
        print(f"[Thermal] exiftool+Planck failed: {e}")

    # Method 2: Fallback to image-based estimation
    print("[Thermal] Using image-based color estimation (fallback)")
    thermal = _estimate_temperature_from_image(thermal_path)
    print(f"[Thermal] Estimated: shape={thermal.shape}, "
          f"range={thermal.min():.2f}~{thermal.max():.2f}°C")
    return thermal


def _extract_with_exiftool_planck(thermal_path):
    """
    Extract temperature map using exiftool raw data + Planck's law.
    Handles FLIR RJPG format where raw thermal data is embedded as PNG.
    """
    # Step 1: Get Planck constants from metadata
    result = subprocess.run(
        ['exiftool', '-j',
         '-RawThermalImageWidth', '-RawThermalImageHeight',
         '-PlanckR1', '-PlanckR2', '-PlanckB', '-PlanckF', '-PlanckO',
         '-RawValueMedian', '-RawValueRange',
         thermal_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return None

    meta = json.loads(result.stdout)[0]

    # Verify we have Planck constants
    required_keys = ['PlanckR1', 'PlanckR2', 'PlanckB', 'PlanckF', 'PlanckO']
    if not all(k in meta for k in required_keys):
        return None

    R1 = float(meta['PlanckR1'])
    R2 = float(meta['PlanckR2'])
    B = float(meta['PlanckB'])
    F = float(meta['PlanckF'])
    O = float(meta['PlanckO'])
    raw_median = float(meta.get('RawValueMedian', 12000))
    raw_range = float(meta.get('RawValueRange', 2000))

    # Step 2: Extract raw thermal image binary data
    result2 = subprocess.run(
        ['exiftool', '-b', '-RawThermalImage', thermal_path],
        capture_output=True, timeout=30
    )
    if result2.returncode != 0 or len(result2.stdout) == 0:
        return None

    raw_bytes = result2.stdout

    # Decode: FLIR typically embeds raw data as PNG or raw 16-bit
    if raw_bytes[:4] == b'\x89PNG':
        nparr = np.frombuffer(raw_bytes, np.uint8)
        raw_img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    elif raw_bytes[:2] in [b'II', b'MM']:
        # TIFF format
        from PIL import Image as PILImage
        raw_img = np.array(PILImage.open(io.BytesIO(raw_bytes)))
    else:
        # Raw 16-bit data
        width = int(meta.get('RawThermalImageWidth', 0))
        height = int(meta.get('RawThermalImageHeight', 0))
        if width == 0 or height == 0:
            return None
        expected = width * height * 2
        raw_img = np.frombuffer(raw_bytes[:expected], dtype=np.uint16).reshape((height, width))

    if raw_img is None:
        return None

    # Fix potential endianness issues (FLIR often stores 16-bit little-endian)
    if raw_img.dtype == np.uint16 and 'RawValueMedian' in meta:
        current_median = np.median(raw_img)
        swapped_img = raw_img.byteswap()
        swapped_median = np.median(swapped_img)
        expected_median = float(meta['RawValueMedian'])
        
        # If the swapped version is much closer to the expected median, use it
        if abs(swapped_median - expected_median) < abs(current_median - expected_median):
            raw_img = swapped_img

    raw_data = raw_img.astype(np.float64)

    # Step 3: Apply Planck's law: T = B / ln(R1/(R2*(raw+O)) + F) - 273.15
    raw_plus_o = raw_data + O

    # Vectorized computation with safe guards
    thermal = np.full_like(raw_data, np.nan)

    # Only process pixels where raw+O > 0 (valid sensor readings)
    valid_mask = raw_plus_o > 0
    if np.any(valid_mask):
        denominator = R2 * raw_plus_o[valid_mask]
        ratio = R1 / denominator
        inner = ratio + F
        # Only take log of positive values
        pos_mask = inner > 0
        # Create temporary array for valid computations
        temp_vals = np.full(np.sum(valid_mask), np.nan)
        temp_vals[pos_mask] = B / np.log(inner[pos_mask]) - 273.15
        thermal[valid_mask] = temp_vals

    # Step 4: Filter to reasonable temperature range
    # Use the raw median to estimate the expected temperature center
    median_temp = B / np.log(R1 / (R2 * (raw_median + O)) + F) - 273.15

    # Determine reasonable range: median ± generous margin
    t_low = median_temp - 30
    t_high = median_temp + 30

    # Get reasonable pixels
    reasonable_mask = ~np.isnan(thermal) & (thermal >= t_low) & (thermal <= t_high)
    if np.sum(reasonable_mask) < 100:
        # If too few reasonable pixels, widen range
        reasonable_mask = ~np.isnan(thermal) & (thermal >= -40) & (thermal <= 100)

    if np.sum(reasonable_mask) == 0:
        return None

    reasonable_mean = np.mean(thermal[reasonable_mask])

    # Replace NaN and out-of-range with mean of reasonable values
    thermal[np.isnan(thermal) | (thermal < t_low) | (thermal > t_high)] = reasonable_mean

    return thermal


def _estimate_temperature_from_image(thermal_path):
    """
    Estimate temperature from a rendered FLIR thermal image by analyzing
    the color-temperature mapping. Uses the visible colorbar/temperature
    overlay text to determine the range.
    """
    img = cv2.imread(thermal_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Cannot read thermal image: {thermal_path}")

    # Try to read temperature range from exiftool metadata
    temp_min, temp_max = None, None
    try:
        result = subprocess.run(
            ['exiftool', '-j', '-MeasuredMinTemperature', '-MeasuredMaxTemperature',
             thermal_path],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            meta = json.loads(result.stdout)[0]
            for key in ['MeasuredMinTemperature', 'MeasuredMaxTemperature']:
                if key in meta:
                    val = meta[key]
                    if isinstance(val, str):
                        val = float(val.replace('C', '').replace('°', '').strip())
                    if 'Min' in key:
                        temp_min = float(val)
                    else:
                        temp_max = float(val)
    except Exception:
        pass

    # Default range based on typical FLIR indoor imagery
    if temp_min is None:
        temp_min = 20.0
    if temp_max is None:
        temp_max = 30.0

    # Convert to HSV to map thermal colors to temperatures
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)

    # FLIR uses ironbow-like palette: black->blue->purple->red->orange->yellow->white
    # Map using combined hue + value approach
    hue_temp = np.zeros_like(h, dtype=np.float64)

    # Blue region (cold): hue ~100-130
    blue_mask = (h >= 90) & (h <= 135)
    hue_temp[blue_mask] = (135 - h[blue_mask].astype(np.float64)) / 45.0 * 0.25

    # Cyan-Green region: hue ~60-90
    green_mask = (h >= 45) & (h < 90)
    hue_temp[green_mask] = 0.25 + (90 - h[green_mask].astype(np.float64)) / 45.0 * 0.25

    # Yellow-Orange region: hue ~15-45
    yellow_mask = (h >= 10) & (h < 45)
    hue_temp[yellow_mask] = 0.5 + (45 - h[yellow_mask].astype(np.float64)) / 35.0 * 0.25

    # Red region (hot): hue ~0-10 or 170-180
    red_mask = (h < 10) | (h >= 170)
    hue_temp[red_mask] = 0.75 + v[red_mask].astype(np.float64) / 255.0 * 0.25

    # Combine with brightness for refinement
    brightness_factor = v.astype(np.float64) / 255.0
    thermal_map = hue_temp * 0.7 + brightness_factor * 0.3

    # Normalize to temperature range
    thermal_map = thermal_map * (temp_max - temp_min) + temp_min

    return thermal_map




def create_sobel_edge_image(thermal_data):
    """
    Apply Sobel Edge Detection to thermal data.
    Creates an edge-enhanced image that highlights fine boundaries,
    useful for image alignment.
    """
    # Normalize thermal data to 8-bit for edge detection
    thermal_norm = cv2.normalize(thermal_data, None, 0, 255, cv2.NORM_MINMAX)
    thermal_8bit = thermal_norm.astype(np.uint8)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(thermal_8bit, (3, 3), 0)

    # Sobel edge detection in X and Y directions
    sobel_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)

    # Compute gradient magnitude
    magnitude = np.sqrt(sobel_x**2 + sobel_y**2)
    magnitude = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    return magnitude


def create_thermal_colormap(thermal_data, colormap=cv2.COLORMAP_JET):
    """
    Create a colored thermal image from temperature data.
    Uses enhanced contrast to show fine details.
    """
    # Apply CLAHE for better contrast
    thermal_norm = cv2.normalize(thermal_data, None, 0, 255, cv2.NORM_MINMAX)
    thermal_8bit = thermal_norm.astype(np.uint8)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(thermal_8bit)

    # Apply colormap
    colored = cv2.applyColorMap(enhanced, colormap)

    return colored


def align_images(rgb_path, thermal_data, edge_image):
    """
    Align RGB image with thermal image using Enhanced Correlation Coefficient (ECC).
    Uses the Sobel edge image from thermal data and a computed Sobel magnitude 
    from the RGB image for robust multimodal alignment.
    Handles Homography, Affine, and Euclidean transforms to correct parallax offset.
    """
    # Read RGB image
    rgb_img = cv2.imread(rgb_path, cv2.IMREAD_COLOR)
    if rgb_img is None:
        raise ValueError(f"Cannot read RGB image: {rgb_path}")

    # Crop the bottom-left 550x400 from RGB to match FLIR FOV
    H, W = rgb_img.shape[:2]
    crop_w, crop_h = 550, 400
    y_start = max(0, H - crop_h)
    x_start = 0
    rgb_cropped0 = rgb_img[y_start:H, x_start:min(W, crop_w)]

    # Crop the bottom-left 480x400 from RGB to match FLIR FOV
    H, W = rgb_cropped0.shape[:2]
    crop_w, crop_h = 480, 400
    x_start = max(0, W - crop_w)
    rgb_cropped = rgb_cropped0[0:H, x_start:W]
    
    # Get thermal dimensions
    th, tw = thermal_data.shape[:2]

    # Resize cropped RGB to match thermal dimensions for alignment
    rgb_resized = cv2.resize(rgb_cropped, (tw, th), interpolation=cv2.INTER_AREA)

    # Convert RGB to grayscale for feature matching
    rgb_gray = cv2.cvtColor(rgb_resized, cv2.COLOR_BGR2GRAY)

    # Enhance edge image (from thermal) for better matching
    thermal_edges = cv2.normalize(edge_image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # Compute gradient magnitude (Sobel edges) for RGB image
    blur_rgb = cv2.GaussianBlur(rgb_gray, (3, 3), 0)
    sobelx_rgb = cv2.Sobel(blur_rgb, cv2.CV_32F, 1, 0, ksize=3)
    sobely_rgb = cv2.Sobel(blur_rgb, cv2.CV_32F, 0, 1, ksize=3)
    mag_rgb = cv2.magnitude(sobelx_rgb, sobely_rgb)
    rgb_edges = cv2.normalize(mag_rgb, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    
    # Define termination criteria for ECC (increased iterations and stricter epsilon for better convergence)
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 1000, 1e-5)
    
    # Smooth edges slightly to help ECC optimization avoid local minima
    thermal_edges_smoothed = cv2.GaussianBlur(thermal_edges, (5, 5), 0)
    rgb_edges_smoothed = cv2.GaussianBlur(rgb_edges, (5, 5), 0)

    aligned_rgb = rgb_resized.copy()
    
    try:
        # 1. Try Homography (parallax between dual lenses can involve perspective distortion)
        warp_matrix_homo = np.eye(3, 3, dtype=np.float32)
        _, warp_matrix = cv2.findTransformECC(
            thermal_edges_smoothed, rgb_edges_smoothed, warp_matrix_homo, 
            cv2.MOTION_HOMOGRAPHY, criteria, None, 5
        )
        aligned_rgb = cv2.warpPerspective(
            rgb_resized, warp_matrix, (tw, th), 
            flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
        )
        print("[Alignment] ECC Homography alignment successful.")
    except Exception as e_homo:
        print(f"[Alignment] ECC Homography failed: {e_homo}. Trying Affine...")
        try:
            # 2. Fallback to Affine (translation + rotation + scale + shear)
            warp_matrix_affine = np.eye(2, 3, dtype=np.float32)
            _, warp_matrix = cv2.findTransformECC(
                thermal_edges_smoothed, rgb_edges_smoothed, warp_matrix_affine, 
                cv2.MOTION_AFFINE, criteria, None, 5
            )
            aligned_rgb = cv2.warpAffine(
                rgb_resized, warp_matrix, (tw, th), 
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
            )
            print("[Alignment] ECC Affine alignment successful.")
        except Exception as e_affine:
            print(f"[Alignment] ECC Affine failed: {e_affine}. Trying Euclidean...")
            try:
                # 3. Fallback to Euclidean (translation + rotation)
                warp_matrix_euclidean = np.eye(2, 3, dtype=np.float32)
                _, warp_matrix = cv2.findTransformECC(
                    thermal_edges_smoothed, rgb_edges_smoothed, warp_matrix_euclidean, 
                    cv2.MOTION_EUCLIDEAN, criteria, None, 5
                )
                aligned_rgb = cv2.warpAffine(
                    rgb_resized, warp_matrix, (tw, th), 
                    flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
                )
                print("[Alignment] ECC Euclidean alignment successful.")
            except Exception as e_euclidean:
                print(f"[Alignment] All ECC alignments failed: {e_euclidean}. Using unaligned resized RGB.")

    return aligned_rgb, rgb_resized


def create_overlay(aligned_rgb, thermal_colored, alpha=0.5):
    """Create a blended overlay of aligned RGB and thermal images."""
    # Ensure same dimensions
    h, w = thermal_colored.shape[:2]
    rgb_resized = cv2.resize(aligned_rgb, (w, h))

    # Blend images
    overlay = cv2.addWeighted(rgb_resized, alpha, thermal_colored, 1 - alpha, 0)
    return overlay


_rembg_session = None

def _get_rembg_session():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        _rembg_session = new_session("birefnet-general")
    return _rembg_session


def remove_background_roi(thermal_data, roi, thermal_colored, aligned_rgb=None):
    """
    Remove background from the ROI area.
    Uses the rembg package on the RGB image to segment foreground from background.
    
    If aligned_rgb is provided, uses it for background removal.
    Otherwise, falls back to the colored thermal image.
    Applies the resulting mask to both to produce background-removed versions.
    """
    x, y, w, h = roi['x'], roi['y'], roi['width'], roi['height']

    # Ensure ROI is within bounds
    th, tw = thermal_data.shape[:2]
    x = max(0, min(x, tw - 1))
    y = max(0, min(y, th - 1))
    w = min(w, tw - x)
    h = min(h, th - y)

    if w <= 0 or h <= 0:
        raise ValueError("Invalid ROI dimensions")

    # Extract ROI from thermal data
    roi_thermal = thermal_data[y:y+h, x:x+w].copy()
    roi_colored = thermal_colored[y:y+h, x:x+w].copy()

    # Extract ROI from aligned RGB if provided
    roi_rgb = None
    if aligned_rgb is not None:
        # Ensure aligned_rgb has the same dimensions as thermal_data
        ah, aw = aligned_rgb.shape[:2]
        if ah != th or aw != tw:
            aligned_rgb_resized = cv2.resize(aligned_rgb, (tw, th), interpolation=cv2.INTER_AREA)
        else:
            aligned_rgb_resized = aligned_rgb
        roi_rgb = aligned_rgb_resized[y:y+h, x:x+w].copy()

    try:
        from rembg import remove
        from PIL import Image

        # Use RGB image for background removal if available, otherwise fallback to colored thermal
        bg_rm_input = roi_rgb if roi_rgb is not None else roi_colored
        
        # Convert BGR to RGB for rembg
        bg_rm_input_rgb = cv2.cvtColor(bg_rm_input, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(bg_rm_input_rgb)
        
        # Remove background using rembg with the specified model
        session = _get_rembg_session()
        result_pil = remove(pil_img, session=session)
        
        # Convert back to numpy array to extract the alpha channel as the mask
        result_rgba = np.array(result_pil)
        
        # The alpha channel is the mask (255 for foreground, 0 for background)
        mask = result_rgba[:, :, 3]
        
        # Ensure mask is binary (rembg might output smooth alpha, we threshold it)
        _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)
        
        # --- Thermal Refinement Step ---
        try:
            from skimage.filters import threshold_otsu
            fg_temps = roi_thermal[mask == 255]
            
            # Only refine if we have enough pixels and significant temperature variance (> 2.5°C)
            if len(fg_temps) > 50 and (fg_temps.max() - fg_temps.min()) > 2.5:
                thresh = threshold_otsu(fg_temps)
                
                hotter_mask = (roi_thermal >= thresh)
                colder_mask = (roi_thermal < thresh)
                
                hotter_count = np.sum(hotter_mask & (mask == 255))
                colder_count = np.sum(colder_mask & (mask == 255))
                
                # Assume the true object dominates the rembg mask (largest cluster)
                if hotter_count > colder_count:
                    thermal_mask = hotter_mask.astype(np.uint8) * 255
                    print(f"[Refinement] Keeping hotter cluster (>= {thresh:.2f}°C)")
                else:
                    thermal_mask = colder_mask.astype(np.uint8) * 255
                    print(f"[Refinement] Keeping colder cluster (< {thresh:.2f}°C)")
                
                mask = cv2.bitwise_and(mask, thermal_mask)
        except Exception as e:
            print(f"Thermal refinement failed: {e}")
        # -------------------------------
        
    except ImportError:
        print("rembg package is not installed. Please install it using 'pip install rembg'.")
        # Fallback to full mask if rembg is not available
        mask = np.ones((h, w), dtype=np.uint8) * 255
    except Exception as e:
        print(f"rembg background removal failed: {e}")
        # Fallback to full mask on error
        mask = np.ones((h, w), dtype=np.uint8) * 255

    # Apply mask to colored ROI
    roi_fg = cv2.bitwise_and(roi_colored, roi_colored, mask=mask)

    # Apply mask to aligned RGB ROI if available
    roi_rgb_fg = None
    if roi_rgb is not None:
        roi_rgb_fg = cv2.bitwise_and(roi_rgb, roi_rgb, mask=mask)

    # Create transparent background version (BGRA)
    roi_rgba = cv2.cvtColor(roi_fg, cv2.COLOR_BGR2BGRA)
    roi_rgba[:, :, 3] = mask

    return roi_fg, mask, roi_thermal, roi_rgb_fg


def farthest_point_sampling(points, k, max_points=10000):
    """
    Sample k points from the given points using Farthest Point Sampling (FPS) 
    for more uniform spatial distribution.
    """
    n = points.shape[0]
    if k >= n:
        return np.arange(n)
        
    rng = np.random.default_rng()
    
    # Downsample if n is too large to speed up FPS
    if n > max_points:
        subset_idx = rng.choice(n, size=max_points, replace=False)
        subset_points = points[subset_idx]
    else:
        subset_idx = np.arange(n)
        subset_points = points
        
    n_subset = subset_points.shape[0]
    centroids = np.zeros(k, dtype=int)
    centroids[0] = rng.integers(n_subset)
    distances = np.full(n_subset, np.inf)
    
    for i in range(1, k):
        last_centroid = subset_points[centroids[i-1]]
        dist_to_last = np.sum((subset_points - last_centroid)**2, axis=1)
        distances = np.minimum(distances, dist_to_last)
        centroids[i] = np.argmax(distances)
        
    return subset_idx[centroids]


def sample_temperature_points(thermal_roi, mask, k, annotation_name, roi_offset):
    """
    Uniformly sample k points from the foreground region of the ROI.
    Returns temperature samples with coordinates and labels.
    """
    # Find foreground pixel coordinates
    fg_coords = np.where(mask == 255)

    if len(fg_coords[0]) == 0:
        raise ValueError("No foreground pixels found in ROI. Try adjusting the ROI.")

    # Limit k to available foreground pixels
    n_fg = len(fg_coords[0])
    k = min(k, n_fg)

    # Convert coordinates to (N, 2) array for spatial sampling
    points = np.column_stack((fg_coords[0], fg_coords[1]))
    
    # Select k indices uniformly using Farthest Point Sampling
    selected_indices = farthest_point_sampling(points, k)

    samples = []
    for i, idx in enumerate(selected_indices):
        local_y = fg_coords[0][idx]
        local_x = fg_coords[1][idx]

        # Get temperature at this point
        temperature = float(thermal_roi[local_y, local_x])

        # Convert to global coordinates
        global_x = local_x + roi_offset['x']
        global_y = local_y + roi_offset['y']

        samples.append({
            'label': f"{annotation_name}-{i + 1}",
            'x': int(global_x),
            'y': int(global_y),
            'local_x': int(local_x),
            'local_y': int(local_y),
            'temperature': round(temperature, 2)
        })

    # Compute statistics
    fg_temps = thermal_roi[mask == 255]
    stats = {
        'min': round(float(np.min(fg_temps)), 2),
        'max': round(float(np.max(fg_temps)), 2),
        'mean': round(float(np.mean(fg_temps)), 2),
        'std': round(float(np.std(fg_temps)), 2),
        'median': round(float(np.median(fg_temps)), 2),
        'n_pixels': int(n_fg)
    }

    return samples, stats


def save_processed_image(image, prefix='processed'):
    """Save a processed image and return the relative URL path."""
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    filepath = os.path.join(PROCESSED_DIR, filename)
    cv2.imwrite(filepath, image)
    return f"/static/processed/{filename}"


def draw_sample_points_on_roi(roi_image, samples, roi_offset):
    """Draw sample points on the ROI image for visualization."""
    result = roi_image.copy()
    if len(result.shape) == 2:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    for sample in samples:
        lx = sample['local_x']
        ly = sample['local_y']

        # Draw crosshair
        color = (0, 255, 255)  # Yellow in BGR
        cv2.drawMarker(result, (lx, ly), color, cv2.MARKER_CROSS, 10, 2)

        # Draw label with temperature
        label = f"{sample['label']}: {sample['temperature']:.1f}°C"
        # Add background rectangle for text readability
        (tw, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        cv2.rectangle(result, (lx + 5, ly - text_h - 2), (lx + 5 + tw, ly + 2), (0, 0, 0), -1)
        cv2.putText(result, label, (lx + 5, ly), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (255, 255, 255), 1, cv2.LINE_AA)

    return result


def process_full_pipeline(rgb_path, thermal_path):
    """
    Run the full image processing pipeline:
    1. Extract thermal data
    2. Create Sobel edge detection image
    3. Create thermal colormap
    4. Align RGB with thermal
    5. Create overlay
    
    Returns all processed image URLs and metadata.
    """
    # Step 1: Extract thermal data
    thermal_data = extract_thermal_data_exiftool(thermal_path)

    # Step 2: Sobel edge detection
    edge_image = create_sobel_edge_image(thermal_data)

    # Step 3: Create thermal colormap
    thermal_colored = create_thermal_colormap(thermal_data)

    # Step 4: Align images
    aligned_rgb, rgb_resized = align_images(rgb_path, thermal_data, edge_image)

    # Step 5: Create overlay
    overlay = create_overlay(aligned_rgb, thermal_colored, alpha=0.5)

    # Save all processed images
    rgb_url = save_processed_image(rgb_resized, 'rgb')
    thermal_url = save_processed_image(thermal_colored, 'thermal')
    edge_url = save_processed_image(edge_image, 'edge')
    overlay_url = save_processed_image(overlay, 'overlay')

    # Also save the edge image in color for better visualization
    edge_colored = cv2.applyColorMap(edge_image, cv2.COLORMAP_HOT)
    edge_colored_url = save_processed_image(edge_colored, 'edge_colored')

    return {
        'rgb_url': rgb_url,
        'thermal_url': thermal_url,
        'edge_url': edge_url,
        'edge_colored_url': edge_colored_url,
        'overlay_url': overlay_url,
        'thermal_shape': list(thermal_data.shape),
        'temp_range': {
            'min': round(float(np.min(thermal_data)), 2),
            'max': round(float(np.max(thermal_data)), 2)
        }
    }
