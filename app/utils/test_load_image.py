import io
import os
import tempfile

# Import your function here (adjust the import path if necessary)
from load_image import load_image_as_bytes
from PIL import Image


def test_load_image_as_bytes():
    # 1. Create a temporary image file on disk
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        temp_file_path = tmp_file.name

    try:
        # Create a simple 10x10 red image and save it to the temp file
        original_img = Image.new("RGB", (10, 10), color="red")
        original_img.save(temp_file_path, format="PNG")

        # 2. Call the function we want to test
        image_bytes = load_image_as_bytes(temp_file_path)

        # 3. Assertions / Checks
        assert isinstance(image_bytes, bytes), "Returned object is not bytes!"
        assert len(image_bytes) > 0, "Returned bytes are empty!"

        # 4. Verify the bytes actually represent a valid image
        loaded_img = Image.open(io.BytesIO(image_bytes))
        assert loaded_img.size == (10, 10), (
            f"Expected size (10, 10), got {loaded_img.size}"
        )

        print("✅ test_load_image_as_bytes passed!")

    finally:
        # Clean up the temporary file after the test
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


if __name__ == "__main__":
    test_load_image_as_bytes()
