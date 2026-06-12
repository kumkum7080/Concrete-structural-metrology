import cv2
import numpy as np

def frangi_filter(gray, scales=[1.0, 2.0, 3.0], beta=0.5, c=15.0):
    """
    Multi-scale Frangi Vesselness Filter implemented in NumPy/OpenCV.
    Specifically tuned to detect valley-like structures (dark cracks)
    on concrete surfaces while suppressing random surface texturing.
    """
    # Normalize image to float64 scale [0, 1]
    img = gray.astype(np.float64) / 255.0
    vesselness = np.zeros(img.shape, dtype=np.float64)

    for sigma in scales:
        # Determine kernel size for Gaussian Blur based on sigma
        ksize = int(6 * sigma + 1)
        if ksize % 2 == 0:
            ksize += 1
        blurred = cv2.GaussianBlur(img, (ksize, ksize), sigma)
        
        # Calculate gradients using Sobel operators
        dx = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        dy = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        dxx = cv2.Sobel(dx, cv2.CV_64F, 1, 0, ksize=3)
        dyy = cv2.Sobel(dy, cv2.CV_64F, 0, 1, ksize=3)
        dxy = cv2.Sobel(dx, cv2.CV_64F, 0, 1, ksize=3)

        # Scale-normalization of Hessian components
        dxx = dxx * (sigma ** 2)
        dyy = dyy * (sigma ** 2)
        dxy = dxy * (sigma ** 2)

        # Compute eigenvalues of 2D Hessian matrix:
        # H = [[dxx, dxy], [dxy, dyy]]
        trace = dxx + dyy
        det = dxx * dyy - dxy * dxy
        discriminant = np.sqrt(np.maximum(0.0, (dxx - dyy)**2 + 4 * dxy**2))
        
        # Eigenvalues lambda1 and lambda2
        lambda1 = (trace - discriminant) / 2.0
        lambda2 = (trace + discriminant) / 2.0

        # Sort eigenvalues such that |lambda1| <= |lambda2|
        lambda1_mag = np.where(np.abs(lambda1) <= np.abs(lambda2), lambda1, lambda2)
        lambda2_mag = np.where(np.abs(lambda1) <= np.abs(lambda2), lambda2, lambda1)

        # Vesselness ratio: deviation from blob structure (R_beta)
        R_beta = np.zeros_like(img)
        non_zero_mask = np.abs(lambda2_mag) > 1e-5
        R_beta[non_zero_mask] = np.abs(lambda1_mag[non_zero_mask]) / np.abs(lambda2_mag[non_zero_mask])
        
        # Structureness (S) - measure of contrast
        S_sq = lambda1_mag**2 + lambda2_mag**2
        
        # Frangi formula
        v_scale = np.zeros_like(img)
        v_scale[non_zero_mask] = np.exp(- (R_beta[non_zero_mask]**2) / (2 * beta**2)) * \
                                 (1.0 - np.exp(- S_sq[non_zero_mask] / (2 * c**2)))
        
        # For dark cracks in light concrete, lambda2 must be positive (valley condition)
        v_scale[lambda2_mag <= 0] = 0.0
        
        vesselness = np.maximum(vesselness, v_scale)

    # Re-normalize to [0, 255]
    v_max = np.max(vesselness)
    if v_max > 0:
        return (vesselness / v_max * 255.0).astype(np.uint8)
    return np.zeros(img.shape, dtype=np.uint8)


def analyze_crack_dimensions(image_path, pixel_to_mm_ratio=0.15, use_frangi=True, frangi_thresh=40):
    """
    Stage 2 Metrology Engine: Extracts structural crack metrics (width, length, severity)
    using Euclidean Distance Transformations and morphological thinning algorithms.
    Supports advanced Frangi Vesselness Filter preprocessing.
    """
    img = cv2.imread(image_path)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if use_frangi:
        # Detect cracks using Vesselness Filter
        vesselness = frangi_filter(gray, scales=[1.0, 2.0, 3.0])
        # Threshold the vesselness map to get a binary mask
        _, mask = cv2.threshold(vesselness, frangi_thresh, 255, cv2.THRESH_BINARY)
    else:
        # Fallback to standard bilateral filtering + adaptive thresholding
        blurred = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 8
        )
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    # Filter out extremely small noise contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cleaned_mask = np.zeros_like(mask)
    for cnt in contours:
        if cv2.contourArea(cnt) > 15:  # Ignore tiny artifacts
            cv2.drawContours(cleaned_mask, [cnt], -1, 255, -1)
    
    mask = cleaned_mask

    if np.sum(mask == 255) < 30:
        return 0.0, 0.0, "Surface Intact", mask, mask

    # Euclidean Distance Transform for Maximum Width Detection
    dist_transform = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    max_radius = np.max(dist_transform)
    max_width_pixels = max_radius * 2.0
    calculated_width_mm = max_width_pixels * pixel_to_mm_ratio

    # Morphological Skeletonization for Trajectory Length Computation
    skeleton = np.zeros(mask.shape, dtype=np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    temp_mask = mask.copy()

    while True:
        eroded = cv2.erode(temp_mask, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(temp_mask, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        temp_mask = eroded.copy()
        if cv2.countNonZero(temp_mask) == 0:
            break

    crack_length_pixels = np.sum(skeleton > 0)
    calculated_length_mm = crack_length_pixels * pixel_to_mm_ratio

    if calculated_width_mm < 0.3:
        category = "Hairline Microcrack (Low Priority)"
    elif 0.3 <= calculated_width_mm <= 1.2:
        category = "Medium Fracture propagation (Moderate Risk)"
    else:
        category = "CRITICAL STRUCTURAL FRACTURE DEPTH (High Risk - Urgent Intervention)"

    return round(calculated_width_mm, 2), round(calculated_length_mm, 2), category, mask, skeleton
