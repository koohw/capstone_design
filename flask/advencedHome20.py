import Adafruit_DHT
from flask import Flask, render_template, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
import Adafruit_ADXL345 
import time
import requests
import RPi.GPIO as GPIO

app = Flask(__name__)
venv_path = '/home/pi/venv'  
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{venv_path}/data.db'
db = SQLAlchemy(app)
 

prev_x = 0
prev_y = 0
prev_z = 0
delta = 0

class SensorData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    delta_x = db.Column(db.Float)
    delta_y = db.Column(db.Float)
    delta_z = db.Column(db.Float)
    delta = db.Column(db.Float)
    flame_status = db.Column(db.String(50))
    distance = db.Column(db.Float)  # Added distance column

accel = Adafruit_ADXL345.ADXL345()

def acceleration():
    global prev_x, prev_y, prev_z, delta
    while True:
        x, y, z = accel.read()
        delta_x = x - prev_x
        delta_y = y - prev_y
        delta_z = z - prev_z   

        delta = ((delta_x ** 2 + delta_y ** 2 + delta_z ** 2) ** (1/3))
        
        prev_x = x
        prev_y = y
        prev_z = z
        
        return delta_x, delta_y, delta_z, round(delta, 2)

def setup():
    global flame_pin, trig_pin, echo_pin
    GPIO.setmode(GPIO.BCM)
    flame_pin = 17
    trig_pin = 23  # Added trig_pin
    echo_pin = 12  # Added echo_pin
    GPIO.setwarnings(False)
    GPIO.setup(flame_pin, GPIO.IN)
    GPIO.setup(13, GPIO.IN)
    GPIO.setup(19, GPIO.IN)
    GPIO.setup(trig_pin, GPIO.OUT)  # Set trig_pin as output
    GPIO.setup(echo_pin, GPIO.IN)   # Set echo_pin as input

def flame_detection():
    flame_pin = 17
    if GPIO.input(flame_pin) == GPIO.HIGH:
        return "0"
    else:
        return "1"

def distance_measurement(trig_pin, echo_pin):
    GPIO.output(trig_pin, True)  # Set trig_pin high
    time.sleep(0.00001)  # Delay for 10 microseconds
    GPIO.output(trig_pin, False)  # Set trig_pin low

    start_time = time.time()
    end_time = time.time()

    while GPIO.input(echo_pin) == 0:
        start_time = time.time()

    while GPIO.input(echo_pin) == 1:
        end_time = time.time()

    pulse_duration = end_time - start_time
    speed_of_sound = 34300  # Speed of sound in cm/s
    distance = (pulse_duration * speed_of_sound) / 2

    return round(distance, 2)

def create_ngrok_tunnel():
    ngrok_api_url = "http://localhost:4040/api/tunnels"
    response = requests.get(ngrok_api_url)
    data = response.json()
    public_url = data['tunnels'][0]['public_url']
    return public_url


@app.route('/')
def index():
    sensor = Adafruit_DHT.DHT11

    pin = 27
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    delta_x, delta_y, delta_z, delta = acceleration()
    flame_status = flame_detection()

    trig_pin = 23
    echo_pin = 12
    distance = distance_measurement(trig_pin, echo_pin)

    alarm = 0
    if GPIO.input(13) == GPIO.HIGH and GPIO.input(17) == GPIO.LOW:
        alarm = 1

    alarm1 = 0
    if alarm == 1 and GPIO.input(19) == GPIO.HIGH:
        alarm1 = 1

    data = SensorData(temperature=temperature, humidity=humidity,
                      delta_x=delta_x, delta_y=delta_y, delta_z=delta_z,
                      delta=delta, flame_status=flame_status,
                      distance=distance)
    db.session.add(data)
    db.session.commit()

    return render_template('index.html', temperature=temperature, humidity=humidity,
                           delta_x=delta_x, delta_y=delta_y, delta_z=delta_z,
                           delta=delta, flame_status=flame_status,
                           distance=distance, alarm=alarm, alarm1=alarm1)

@app.route('/get_sensor_data', methods=['GET'])
def get_sensor_data():
    sensor = Adafruit_DHT.DHT11
    pin = 27
    humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
    delta_x, delta_y, delta_z, delta = acceleration()
    delta = round(float(delta),2)
    flame_pin = 17
    flame_status = flame_detection()
    trig_pin = 23
    echo_pin = 12
    distance = distance_measurement(trig_pin, echo_pin)
    alarm = 0
    if GPIO.input(13) == GPIO.HIGH and GPIO.input(17) == GPIO.LOW:
        alarm = 1
   
    alarm1 = 0
    if alarm == 1 and GPIO.input(19) == GPIO.HIGH:
        alarm1 = 1

    sensor_data = {
        'temperature': temperature,
        'humidity': humidity,
        'delta' : delta,
        'flame_status' : flame_status,
        'distance' : distance,
        'alarm' : alarm,
        'alarm1' : alarm1
    }
    return jsonify(sensor_data)


@app.route('/logs')

def logs():
    global flame_pin  # 전역 변수로 선언
    logs = SensorData.query.all()

    for log in logs:
        if GPIO.input(flame_pin) == GPIO.HIGH:
            log.flame_status = "0"
        else:
            log.flame_status = "1"

    return render_template('logs.html', logs=logs)




@app.route('/logs_app', methods=['GET'])
def logs_app():
    logs = SensorData.query.order_by(SensorData.id.desc()).limit(5).all()

    logs_data = {
        'log_data': []
    }

    for log in logs:
        log_entry = {
            'id': log.id,
            'temperature': log.temperature,
            'humidity': log.humidity,
            'delta': log.delta,
            'flame_status' : log.flame_status,
            'distance' : log.distance
        }
        logs_data['log_data'].append(log_entry)

    return jsonify(logs_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    ngrok_tunnel_url = create_ngrok_tunnel()
    print("ngrok tunnel URL:", ngrok_tunnel_url)              
    setup()
    app.run(host='0.0.0.0', port=5000)