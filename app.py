import cv2
import time
import pickle
import socket
import struct
import threading
from queue import Queue
from flask import Flask, render_template, Response, request, redirect, url_for

app = Flask(__name__)

server_host = 'localhost'
server_port = 5555
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
is_streaming = False
frame_list = Queue()

def socketOpen(connect_count):
    count = connect_count
    try:
        client_socket.connect((server_host, server_port))
        print(u'[INFO] Client socket is connected with Server socket [ TCP_SERVER_IP: ' + server_host + ', TCP_SERVER_PORT: ' + str(server_port) + ' ]')
    except Exception as e:
        print(f"[ERROR] {e}")
        count += 1
        if count == 10:
            print(u'[ERROR] Connect fail %d times. exit program'%(count))                
        print(u'[INFO] %d times try to connect with server'%(count))
        time.sleep(0.5)
        socketOpen(count)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "admin":
            socketOpen(0)
            return redirect(url_for('video_stream'))
        else:
            # Invalid credentials, display error message
            error_message = 'Invalid username or password.'
            return render_template('login.html', error_message=error_message)
    return render_template('login.html')

@app.route('/video_stream')
def video_stream():
    return render_template('video_stream.html')

def receiveFrame():
    data = b""
    payload_size = struct.calcsize("Q")
    while True:
        if is_streaming:
            while len(data) < payload_size:
                packet = client_socket.recv(4*1024) 
                if not packet:
                    break
                data += packet
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q",packed_msg_size)[0]
            while len(data) < msg_size:
                data += client_socket.recv(4*1024)
            frame_data = data[:msg_size]
            data = data[msg_size:]
            frame = pickle.loads(frame_data)
            frame_list.put(frame)
        else:
            return

def generateVideo():
    while True:
        if is_streaming:
            if not frame_list.empty():
                frame = frame_list.get()

                # Convert the frame to JPEG format
                _, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()

                # Send the frame to the client
                yield (b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            #else:
            #    print("Queue is empty. Waiting for data...")

@app.route('/play_video')
def play_video():
    global is_streaming
    client_socket.sendall('live'.encode('utf-8'))
    is_streaming = True
    receiveFrame()
    #recvFrame = threading.Thread(target=receiveFrame)
    #recvFrame.start()
    print("[INFO] Start receiving video stream")
    return 'OK'

@app.route('/stop_video')
def stop_video():
    global is_streaming
    client_socket.sendall('stop'.encode('utf-8'))
    is_streaming = False
    print("[INFO] Stop receiving video stream")
    with frame_list.mutex:
        frame_list.queue.clear()
    return 'OK'

@app.route('/video_feed')
def video_feed():
    return Response(generateVideo(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    app.run(debug=True)