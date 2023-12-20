import os, sys
import cv2, pickle, struct, imutils
import time
import numpy
import socket
import threading

class ClientSocket:

    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.stop_event = False
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketOpen(0)

    def socketOpen(self, connectCount):
        self.connectCount = connectCount
        try:
            self.client_socket.connect((self.server_host, self.server_port))
            print(u'[INFO] Client socket is connected with Server socket [ TCP_SERVER_IP: ' + self.server_host + ', TCP_SERVER_PORT: ' + str(self.server_port) + ' ]')
        except Exception as e:
            print(f"[ERROR] {e}")
            self.connectCount += 1
            if self.connectCount == 10:
                print(u'[ERROR] Connect fail %d times. exit program'%(self.connectCount))                
            print(u'[INFO] %d times try to connect with server'%(self.connectCount))
            time.sleep(0.5)
            self.socketOpen(connectCount)

    def socketClose(self):
        self.client_socket.close()
        print(u'[INFO] Connection to server [ TCP_SERVER_IP: ' + self.server_host + ', TCP_SERVER_PORT: ' + str(self.server_port) + ' ] is closed')

    def start(self):
        self.signalHandler()

    def signalHandler(self):
        try:
            while True:
                userInput = input("Live/Stop/Exit: ")
                if userInput.lower() == 'exit':
                    os._exit(1)
                elif userInput.lower() == 'live':
                    self.client_socket.sendall(userInput.encode('utf-8'))
                    print("[INFO] Start receiving video stream")
                    self.recv_msg = threading.Thread(target=self.receiveMessage)
                    self.recv_msg.start()
                elif userInput.lower() == 'stop':
                    self.stop_event = True
                    self.recv_msg.join()
                    self.stop_event = False
        except KeyboardInterrupt:
            print("User interrupted the program.")
        except Exception as e:
            print(f"[ERROR] {e}")
        #finally:
            #self.socketClose()
            #print(f"[INFO] Connection with server is closed")

    def receiveMessage(self):
        data = b""
        payload_size = struct.calcsize("Q")
        try:
            while True:
                while len(data) < payload_size:
                    packet = self.client_socket.recv(4*1024) 
                    if not packet:
                        break
                    data += packet
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q",packed_msg_size)[0]
                while len(data) < msg_size:
                    data += self.client_socket.recv(4*1024)
                frame_data = data[:msg_size]
                data = data[msg_size:]
                frame = pickle.loads(frame_data)
                cv2.namedWindow("RECEIVING VIDEO", cv2.WINDOW_NORMAL)
                cv2.resizeWindow("RECEIVING VIDEO", 1280, 720) 
                cv2.imshow("RECEIVING VIDEO", frame)
                if (cv2.waitKey(1) & 0xFF == ord('q')) or self.stop_event:
                    self.client_socket.sendall('stop'.encode('utf-8'))
                    print("[INFO] Stop receiving video stream")
                    break
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"[ERROR] {e}")

def main():
    client = ClientSocket("localhost", 5555)
    client.start()

if __name__ == "__main__":
    main()