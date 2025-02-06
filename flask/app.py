from flask import Flask, render_template, Response
import time
import io
import threading
from picamera.array import PiRGBArray
from picamera import PiCamera
import numpy as np
import cv2


app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


class Camera(object):
    thread = None
    frame = None
    last_access = 0

    def initialize(self):
        if Camera.thread is None:
            Camera.thread = threading.Thread(target=self._thread)
            Camera.thread.start()

            while self.frame is None:
                time.sleep(0)

    def get_frame(self):
        Camera.last_access = time.time()
        self.initialize()
        return self.frame

    @classmethod
    def _thread(cls):
        camera = PiCamera()
        camera.resolution = (640, 480)
        camera.framerate = 32
        camera.vflip = True

        rawCapture = PiRGBArray(camera, size=(640, 480))

        time.sleep(0.1)

        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            image = frame.array
            image = cv2.flip(image, 1)

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            boxes, weights = hog.detectMultiScale(image, winStride=(8, 8))
            boxes = np.array([[x, y, x + w, y + h] for (x, y, w, h) in boxes])
            for (xA, yA, xB, yB) in boxes:
                cv2.rectangle(image, (xA, yA), (xB, yB), (0, 255, 0), 2)

            object_count = len(boxes)

            cv2.putText(image, "Object Count: {}".format(object_count), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            ret, jpeg = cv2.imencode('.jpg', image)
            cls.frame = jpeg.tobytes()

            rawCapture.truncate(0)

            if time.time() - cls.last_access > 10:
                break

        cls.thread = None


def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, threaded=True)
