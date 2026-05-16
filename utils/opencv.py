import cv2
import numpy as np
from load_image import load_image_as_bytes
from PIL import Image
from ultralytics import YOLO


def load_yolo_model(model_path="yolov8n.pt"):
    """
    Loads a YOLOv8 model.
    If 'yolov8n.pt' is not found locally, it will be downloaded automatically.
    """
    # Initialize the YOLO model
    model = YOLO(model_path)
    return model


def process_image_with_yolo(image_bytes, model):
    """
    Takes image bytes, runs YOLO object detection, draws bounding boxes using OpenCV,
    and returns the processed image as bytes.
    """
    # 1. Convert the image bytes to a numpy array, then decode into an OpenCV image (BGR)
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image bytes into an OpenCV image.")

    # 2. Run YOLO inference on the image
    results = model(img)

    # 3. Draw bounding boxes and labels on the image using OpenCV
    for result in results:
        boxes = result.boxes
        for box in boxes:
            # Extract coordinates, confidence, and class ID
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])

            # Get the class name
            label = f"{model.names[cls_id]} {conf:.2f}"

            # Draw the bounding box
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw the label background and text
            cv2.putText(
                img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
            )

    # 4. Encode the modified image back to bytes
    success, encoded_img = cv2.imencode(".png", img)
    if not success:
        raise ValueError("Could not encode the processed image.")

    return encoded_img.tobytes()


if __name__ == "__main__":
    # A simple test block you can run directly to see if it works
    # Make sure you have the required packages: pip install opencv-python ultralytics numpy
    print("Loading YOLO model...")
    test_model = load_yolo_model()
    image_path = "/home/alex/Development/projects/hackathon/test.png"
    my_bytes = load_image_as_bytes(image_path)
    print(process_image_with_yolo(my_bytes, test_model))
    print("Model loaded successfully. OpenCV and YOLO are ready!")
