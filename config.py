# config.py
FACES_FOLDER = "faces"

# Security
LOCK_DELAY_SECONDS = 5  # delay before automatic workstation lock
LOCK_COOLDOWN_SECONDS = 15  # minimum delay between two lock operations

# Recognition thresholds (percentage shown above the box)
MIN_CONFIDENCE_PERCENT = 55  # green when >= this percentage
WEAK_CONFIDENCE_PERCENT = 40  # red with name? when >= this percentage, otherwise Unknown

# Performance
ANALYZE_SCALE = 0.5  # 0.5 = analyze at half resolution
RECOGNITION_EVERY_N_FRAMES = 2  # 1 = every frame, 2 = every other frame
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Compatibility alias for older code
LOCK_DELAY = LOCK_DELAY_SECONDS
