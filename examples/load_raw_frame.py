import sys
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

import numpy as np
from PIL import Image

def convert_raw_frame(raw_path, width, height, output_base):
    """
    Convert a raw RGBA frame file to PNG and JPEG
    
    Args:
        raw_path: Path to the raw frame file
        width: Width of the frame in pixels
        height: Height of the frame in pixels
        output_base: Base filename for output (without extension)
    """
    # Read raw RGBA data
    with open(raw_path, 'rb') as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    
    # Reshape into RGBA image array
    image = data.reshape((height, width, 3))
    
    # Flip image vertically (OpenGL coordinates are bottom-left origin)
    image = np.flipud(image)
    
    # Convert to PIL Image
    pil_image = Image.fromarray(image, 'RGB')
    
    # For JPEG, we need to convert to RGB since JPEG doesn't support alpha
    rgb_image = pil_image.convert('RGB')
    
    # Save as PNG (lossless, with alpha channel)
    pil_image.save(f"{output_base}.png")
    rgb_image.save(f"{output_base}.rgb.png")
    
    # Save as JPEG (lossy, no alpha channel)
    rgb_image.save(f"{output_base}.jpg", quality=95)  # quality=95 for high quality



def read_frame(filename, width, height):
    # Read raw RGBA data
    with open(filename, 'rb') as f:
        data = np.frombuffer(f.read(), dtype=np.uint8)
    
    # Reshape into RGBA image array
    image = data.reshape((height, width, 3))
    
    # Flip image vertically (OpenGL coordinates are bottom-left origin)
    image = np.flipud(image)
    
    # Convert RGBA to RGB
    #rgb_image = image[:, :, :3]
    
    return image

# Example usage:
print(sys.argv)
fname = sys.argv[1]
convert_raw_frame(fname, 1280, 1280, 'image')
frame = read_frame(fname, 1280, 1280)
plt.imshow(frame)
plt.axis('off')
plt.show()
