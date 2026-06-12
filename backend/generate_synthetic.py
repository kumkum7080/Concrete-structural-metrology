import os
import cv2
import numpy as np
import random

def generate_concrete_texture(width=400, height=400):
    """Generates a synthetic gray concrete texture with noise and pitting."""
    # Create base gray image (typical concrete base color)
    base_color = random.randint(180, 210)
    img = np.ones((height, width), dtype=np.uint8) * base_color
    
    # Add fine-grained noise
    noise = np.random.normal(0, 8, (height, width)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Add concrete pitting (small dark voids)
    num_pits = random.randint(30, 80)
    for _ in range(num_pits):
        px = random.randint(10, width - 10)
        py = random.randint(10, height - 10)
        radius = random.randint(1, 3)
        pit_color = random.randint(50, 120)
        cv2.circle(img, (px, py), radius, pit_color, -1)
        
    # Apply bilateral filter or Gaussian blur to smooth and make it look natural
    img = cv2.GaussianBlur(img, (5, 5), 0)
    
    # Add some subtle large-scale shading gradients
    X, Y = np.meshgrid(np.linspace(-1, 1, width), np.linspace(-1, 1, height))
    shading = (X * random.uniform(-10, 10) + Y * random.uniform(-10, 10)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + shading, 0, 255).astype(np.uint8)
    
    # Convert to BGR to match standard OpenCV formats
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

def draw_random_crack(img):
    """Procedurally draws a realistic crack (fissure path) on the texture."""
    height, width, _ = img.shape
    # Select random start point near edge or center
    sx = random.randint(30, width - 30)
    sy = random.randint(30, height - 30)
    
    # Generate random walk/trajectory
    points = [(sx, sy)]
    curr_x, curr_y = sx, sy
    
    # Choose general crack direction (angle)
    angle = random.uniform(0, 2 * np.pi)
    segments = random.randint(8, 20)
    segment_len = random.randint(15, 30)
    
    for _ in range(segments):
        # Walk forward with slight deviation
        angle += random.uniform(-0.5, 0.5)
        next_x = int(curr_x + segment_len * np.cos(angle))
        next_y = int(curr_y + segment_len * np.sin(angle))
        
        # Keep inside boundaries
        next_x = max(10, min(width - 10, next_x))
        next_y = max(10, min(height - 10, next_y))
        
        points.append((next_x, next_y))
        curr_x, curr_y = next_x, next_y
        
    # Draw the main crack path with tapering width
    num_points = len(points)
    max_thickness = random.randint(2, 5)
    
    for i in range(num_points - 1):
        pt1 = points[i]
        pt2 = points[i+1]
        # Calculate thickness (tapers off towards the ends)
        t = max(1, int(max_thickness * (1.0 - abs(i - num_points / 2) / (num_points / 2))))
        
        # Crack color is dark gray/black with slight variation
        color = random.randint(10, 50)
        cv2.line(img, pt1, pt2, (color, color, color), t, lineType=cv2.LINE_AA)
        
        # Occasional minor side branchings
        if random.random() < 0.2:
            branch_len = random.randint(10, 20)
            branch_angle = angle + random.choice([-1.0, 1.0]) * random.uniform(0.5, 1.2)
            bx = int(pt1[0] + branch_len * np.cos(branch_angle))
            by = int(pt1[1] + branch_len * np.sin(branch_angle))
            bx = max(10, min(width - 10, bx))
            by = max(10, min(height - 10, by))
            cv2.line(img, pt1, (bx, by), (color, color, color), max(1, t - 1), lineType=cv2.LINE_AA)
            
    # Apply a light blur to make the crack blend with the texture naturally
    blurred_img = cv2.GaussianBlur(img, (3, 3), 0)
    # Blend partially with original to keep the crack relatively sharp
    img = cv2.addWeighted(img, 0.6, blurred_img, 0.4, 0)
    return img

def create_dataset(destination_dir="data", count_per_class=50):
    """Generates synthetic dataset structure for Positive (cracks) and Negative (clean)."""
    pos_dir = os.path.join(destination_dir, "Positive")
    neg_dir = os.path.join(destination_dir, "Negative")
    
    os.makedirs(pos_dir, exist_ok=True)
    os.makedirs(neg_dir, exist_ok=True)
    
    print(f"Generating {count_per_class} Negative (No Cracks) concrete samples...")
    for i in range(count_per_class):
        texture = generate_concrete_texture()
        filename = f"negative_concrete_{i:04d}.png"
        cv2.imwrite(os.path.join(neg_dir, filename), texture)
        
    print(f"Generating {count_per_class} Positive (Cracks Present) concrete samples...")
    for i in range(count_per_class):
        texture = generate_concrete_texture()
        cracked = draw_random_crack(texture)
        filename = f"positive_concrete_{i:04d}.png"
        cv2.imwrite(os.path.join(pos_dir, filename), cracked)
        
    print(f"Synthetic dataset generation complete! Saved in '{destination_dir}/'")

if __name__ == "__main__":
    create_dataset()
