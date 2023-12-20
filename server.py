import os
import time
import numpy
import pickle
import struct
import socket
import imageio
import threading
from queue import Queue
from datetime import datetime, timedelta
from send_alert import send2telegram

if not os.path.exists("./alert"):
    os.mkdir('./alert')
if not os.path.exists("./record"):
    os.mkdir('./record')

class ServerSocket:

    def __init__(self, server_host, server_port, alert_port):
        self.server_host = server_host
        self.server_port = server_port
        self.alert_port = alert_port
        self.stop_event = False
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.alert_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.frame_list = Queue()
        self.clients = []
        self.chunks = []
        self.anomaly = []

    def start(self):
        self.server_socket.bind((self.server_host, self.server_port))
        self.alert_socket.bind((self.server_host, self.alert_port))
        self.server_socket.listen(2)
        self.alert_socket.listen(1)
        print(f"Server listening on {self.server_host}:{self.server_port},{self.alert_port}")

        self.alert_conn, addr = self.alert_socket.accept()
        print(f"[INFO] Connection from {addr}")
        for _ in range(2):
            client_socket, addr = self.server_socket.accept()
            print(f"[INFO] Connection from {addr}")
            self.clients.append(client_socket)

        alert = threading.Thread(target=self.handleAlert)
        alert.start()
        client = threading.Thread(target=self.handleClient)
        client.start()

    def socketClose(self):
        for client in self.clients:
            client.close()
        self.alert_conn.close()
        self.server_socket.close()
        self.alert_socket.close()

    def handleClient(self):
        try:
            print(f"[INFO] Start receiving messages...")
            while True:
                msg = self.clients[1].recv(1024).decode('utf-8')
                if not msg:
                    break
                print(f"[INFO] Received from client: {msg}")
                if msg.lower() == 'live':
                    print("[INFO] Start receiving live Feed")
                    self.clients[0].sendall(msg.encode('utf-8'))
                    self.live_feed = threading.Thread(target=self.receiveMessage)
                    self.live_feed.start()
                elif msg.lower() == 'stop':
                    print("[INFO] Stop forwarding live Feed")
                    self.clients[0].sendall(msg.encode('utf-8'))
                    self.stop_event = True
        except Exception as e:
            print(f"[ERROR] Error while handling client: {e}")
        except KeyboardInterrupt:
            print(f"[INFO] Connection with client closed.")
            self.socketClose()
        finally:
            print(f"[INFO] Connection with client closed.")
            self.socketClose()

    def receiveMessage(self):
        data = b""
        payload_size = struct.calcsize("Q")
        try:
            while True:
                if self.stop_event:
                    with self.frame_list.mutex:
                        self.frame_list.queue.clear()
                    self.stop_event = False
                    return
                #print("[INFO] Forwarding video stream...")
                while len(data) < payload_size:
                    packet = self.clients[0].recv(4*1024)
                    if not packet:
                        return
                    data += packet
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q",packed_msg_size)[0]
                while len(data) < msg_size:
                    data += self.clients[0].recv(4*1024)
                frame_data = data[:msg_size]
                data = data[msg_size:]
                frame = pickle.loads(frame_data)
                self.frame_list.put(frame)
                self.forwardMessage()
        except Exception as e:
            print(f"[ERROR] {e}")
            print(f"[INFO] Connection with client closed.")
            self.socketClose()

    def forwardMessage(self):
        try:
            if not self.frame_list.empty():
                frame = self.frame_list.get()
                a = pickle.dumps(frame)
                message = struct.pack("Q",len(a)) + a
                self.clients[1].sendall(message)
            else:
                print("Queue is empty. Waiting for data...")
        except Exception as e:
            print(f"[ERROR] {e}")
            print(f"[INFO] Connection with client closed.")
            self.socketClose()

    def handleAlert(self):
        try:
            while True:
                msg = self.alert_conn.recv(1024).decode('utf-8')
                if not msg:
                    break
                print(f"[INFO] Received from client: {msg}")
                if 'alert' in msg.lower():
                    counter = int(msg.split("_")[1])
                    print("[INFO] Start receiving anomaly frames")
                    #recvAlert = threading.Thread(target=self.receiveAlert, args=(counter,))
                    #recvAlert.start()
                    self.receiveAlert(counter)
                elif 'end' in msg.lower():
                    counter = int(msg.split("_")[1])
                    print("[INFO] Start receiving anomaly frames")
                    self.receiveAlert(counter)
                    print(f"[INFO] Start creating clip...")
                    clip = threading.Thread(target=self.createClip, args=(self.anomaly[-1],))
                    clip.start()
        except Exception as e:
            print(f"[ERROR] Error while handling client: {e}")
        except KeyboardInterrupt:
            print(f"[INFO] Connection with client closed.")
            self.socketClose()
        finally:
            print(f"[INFO] Connection with client closed.")
            self.socketClose()

    def receiveAlert(self, counter):
        data = b""
        counter = counter
        payload_size = struct.calcsize("Q")
        try:
            for _ in range(counter, counter+16):
                while len(data) < payload_size:
                    packet = self.alert_conn.recv(4*1024)
                    if not packet: return
                    data += packet
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q",packed_msg_size)[0]
                while len(data) < msg_size:
                    data += self.alert_conn.recv(4*1024)
                frame_data = data[:msg_size]
                data = data[msg_size:]
                frame = pickle.loads(frame_data)
                #print("Frame received")
                self.addElement(counter, frame)
                counter += 1
        except Exception as e:
            print(f"[ERROR] Error while handling client: {e}")
        except KeyboardInterrupt:
            print(f"[INFO] Connection with client closed.")
            self.socketClose()

    def addElement(self, counter, frame):
        if not self.chunks or counter - self.chunks[-1][-1] > 80: #30/80
            self.chunks.append([counter])
            self.anomaly.append([frame])
            #if len(self.chunks) > 1:
            #    print(f"[INFO] Start creating clip...")
            #    clip = threading.Thread(target=self.createClip, args=(self.anomaly[-2],))
            #    clip.start()
        else:
            self.chunks[-1].append(counter)
            self.anomaly[-1].append(frame)

    def createClip(self, frames):
        frame_height, frame_width, _ = frames[0].shape
        current_time = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_video_file = f"./alert/alert_{current_time}.mp4"
        writer = imageio.get_writer(output_video_file, fps=20)
        for frame in frames:
            writer.append_data(numpy.uint8(frame))
        print("[INFO] Done")
        writer.close()
        send2telegram(output_video_file)

def main():
    server = ServerSocket('localhost', 5555, 6666)
    server.start()

if __name__ == "__main__":
    main()
