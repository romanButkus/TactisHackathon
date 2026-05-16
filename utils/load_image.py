import io

from PIL import Image


def load_image_as_bytes(image_path):
    # 1. Load the image from disk
    img = Image.open(image_path)

    # 2. Create a bytes buffer
    buffer = io.BytesIO()

    # 3. Save the image to the buffer instead of a file
    # You must specify the format (PNG, JPEG, etc.)
    img.save(buffer, format="PNG")

    # 4. Get the byte data
    image_bytes = buffer.getvalue()

    # Optional: Reset buffer pointer if you plan to read it immediately
    buffer.seek(0)
    return image_bytes
