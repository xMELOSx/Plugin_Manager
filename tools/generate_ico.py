import os
from PIL import Image

def generate_ico(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return
    
    img = Image.open(input_path)
    # Define icon sizes
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(output_path, format='ICO', sizes=icon_sizes)
    print(f"Icon saved to {output_path}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_jpg = os.path.join(current_dir, "src", "resource", "icon", "icon.jpg")
    output_ico = os.path.join(current_dir, "src", "resource", "icon", "icon.ico")
    generate_ico(input_jpg, output_ico)
