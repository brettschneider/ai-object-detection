#!/usr/bin/env python
"""Python Image AI POC"""
import json
import webbrowser
from pathlib import Path

import cv2
import ollama
from imageai.Detection import ObjectDetection


def get_camera_feed(width: int = 650, height: int = 750, capture_device: int = 1) -> cv2.VideoCapture:
    """Set up the camer for video capture"""
    cam_feed = cv2.VideoCapture(capture_device)
    cam_feed.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cam_feed.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cam_feed


def get_detector(model: str = "yolov3.pt") -> ObjectDetection:
    """Stand up an object detector using the given model."""
    model_path = str(Path(__file__).parents[0] / "Datasets" / model)
    detector = ObjectDetection()
    detector.setModelTypeAsYOLOv3()
    detector.setModelPath(model_path)
    detector.loadModel()
    return detector


def extract_book_image(preds, image):
    """Given an object detection array, check if there are any books, and then crop and return the first one"""
    for obj in preds:
        if obj['name'] == 'book' and obj['percentage_probability'] > 85.0:
            x_min = obj['box_points'][0] - 10
            y_min = obj['box_points'][1] - 10
            x_max = obj['box_points'][2] + 10
            y_max = obj['box_points'][3] + 10
            cropped_image = image[y_min:y_max, x_min:x_max]
            return cropped_image
    return None


def extract_book_details(image):
    """Send the book image to llava to have it read the details from the image"""
    _, buf = cv2.imencode('.png', image)

    prompt = """
    Describe this book and give the following structured output in plain JSON:
    {
        "title": "<Provide the book's title>",
        "author": "<Provide the book's author>",
        "genre": "<Provide the genre of the book>"
    }
    If you can't determine the book's info, just respnod with "NONE"
    """

    message = {
        'role': 'user',
        'content': prompt,
        'images': [buf.tobytes()]
    }
    client = ollama.Client()
    response = client.chat(model='llava:latest', messages=[message])
    data = response['message']['content'].replace('json', '').replace('```', '')
    return json.loads(data)


def detection_loop(camera_feed: cv2.VideoCapture, detector: ObjectDetection):
    """Continuously loop, detecting objects in the camera view until the user quits (keypress)."""
    while True:
        ret, img = camera_feed.read()
        annotated_image, preds = detector.detectObjectsFromImage(
            input_image=img,
            output_type="array",
            display_percentage_probability=True,
            display_object_name=True
        )
        book = extract_book_image(preds, img)
        if book is not None:
            book_details = extract_book_details(book)
            if book_details and book_details.get('title', '').upper() != 'NONE':
                print(json.dumps(book_details, indent=4))
                url = f"https://www.amazon.com/s?k={book_details['title'].replace(' ', '+')}"
                webbrowser.open(url)

        cv2.imshow("", annotated_image)
        if cv2.waitKey(1) != -1:
            break


def cleanup(camera_feed: cv2.VideoCapture):
    """Shutdown the camera allocation"""
    camera_feed.release()
    cv2.destroyAllWindows()


if __name__ == '__main__':
    feed = get_camera_feed(1024, 768)
    object_detector = get_detector()
    detection_loop(feed, object_detector)
    cleanup(feed)
