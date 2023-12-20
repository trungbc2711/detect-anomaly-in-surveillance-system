import os
import time
import numpy
import socket
import threading
from alerter import AlertSocket

class LiveSocket:

    def __init__(self, server_host, server_port, alert_stream):
        self.server_host = server_host
        self.server_port = server_port
        self.alert_stream = alert_stream
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
            connectCount += 1
            if connectCount == 10:
                print(u'[ERROR] Connect fail %d times. exit program'%(connectCount))
            print(u'[INFO] %d times try to connect with server'%(connectCount))
            time.sleep(0.5)
            self.socketOpen(connectCount)

    def socketClose(self):
        self.client_socket.close()
        print(u'[INFO] Connection to server [ TCP_SERVER_IP: ' + self.server_host + ', TCP_SERVER_PORT: ' + str(self.server_port) + ' ] is closed')    

    def start(self):
        try:
            recvMsg = threading.Thread(target=self.receiveMessage())
            recvMsg.start()
        except Exception as e:
            print(f"[ERROR] {e}")
            os._exit(1) 

    def receiveMessage(self):
        try:
            while True:
                msg = self.client_socket.recv(1024).decode('utf-8')
                if not msg:
                    break
                print(f"[INFO] Received from server: {msg}")
                if msg.lower() == 'live':
                    print("[INFO] Start sending live Feed")
                    #live_feed = threading.Thread(target=self.sendStream)
                    #live_feed.start()
                    self.alert_stream.live_event = True
                if msg.lower() == 'stop':
                    print("[INFO] Stop sending live Feed")
                    #self.stop_event = True
                    self.alert_stream.live_event = False
                    #elf.stop_event = False
        except Exception as e:
            print(f"[ERROR] {e}")
            os._exit(1)
        except KeyboardInterrupt:
            print("User interrupted the program.")
            os._exit(1)
        finally:
            self.socketClose()

def main():
    try:
        alerter = AlertSocket('192.168.0.10', 6666)
        streamer = LiveSocket('192.168.0.10', 5555, alerter)
        client = threading.Thread(target=streamer.start)
        client.start()
        alerter.start(streamer)
    except Exception as e:
        print(f"[ERROR] {e}")
        os._exit(1)

if __name__ == "__main__":
    main()