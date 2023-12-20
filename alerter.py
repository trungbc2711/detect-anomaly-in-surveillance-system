import os
import cv2 
import time
import pickle
import socket
import struct
import imutils
import threading
import numpy as np
import tensorflow as tf
from queue import Queue
from datetime import datetime
from keras.utils import get_file
from keras.models import load_model
from utils import interpolate, extrapolate

frame_height = 240
frame_width = 320
channels = 3
frame_count = 16
features_per_bag = 32
base_dir = "./"
if not os.path.exists("./alert"):
    os.mkdir('./alert')
if not os.path.exists("./record"):
    os.mkdir('./record')
C3D_MEAN_PATH = 'https://github.com/adamcasson/c3d/releases/download/v0.1/c3d_mean.npy'

# load models
# extractor
feature_extractor = load_model(base_dir + "model/feature_extractor.h5")
#feature_extractor = tf.lite.Interpreter(model_path = base_dir + "model/feature_extractor.tflite")
#feature_extractor.allocate_tensors()
#input_extractor = feature_extractor.get_input_details()
#output_extractor = feature_extractor.get_output_details()
# classifier
classifier_model = load_model(base_dir + "model/classifier_model.h5")
#classifier_model = tf.lite.Interpreter(model_path = base_dir + "model/classifier_model.tflite")
#classifier_model.resize_tensor_input(classifier_model.get_input_details()[0]['index'], [32, 4096])
#classifier_model.allocate_tensors()
#input_classifier = classifier_model.get_input_details()
#output_classifier = classifier_model.get_output_details()

class AlertSocket:

    def __init__(self, server_host, alert_port):
        self.server_host = server_host
        self.alert_port = alert_port
        self.live_stream = None
        self.online = None
        self.frame_list = Queue()
        self.live_event = False
        self.alert_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socketOpen(0)

    def start(self, live_stream):
        try:
            self.live_stream = live_stream
            capturer = threading.Thread(target=self.capFrame)
            capturer.start()
            time.sleep(1)
            detector = threading.Thread(target=self.detectAnomaly)
            detector.start()
        except KeyboardInterrupt:
            os._exit(1)

    def socketOpen(self, connectCount):
        self.connectCount = connectCount
        try:
            self.alert_socket.connect((self.server_host, self.alert_port))
            self.online = True
            print(u'[INFO] Client socket is connected with Server socket [ TCP_SERVER_IP: ' + self.server_host + ', TCP_SERVER_PORT: ' + str(self.alert_port) + ' ]')
        except Exception as e:
            print(f"[ERROR] {e}")
            connectCount += 1
            if connectCount == 10:
                self.online = False
                print(u'[ERROR] Connect fail %d times. exit program'%(connectCount))
            print(u'[INFO] %d times try to connect with server'%(connectCount))
            time.sleep(0.5)
            self.socketOpen(connectCount)

    def socketClose(self):
        self.alert_socket.close()
        print(u'[INFO] Connection to server [ TCP_SERVER_IP: ' + self.server_host + ', TCP_SERVER_PORT: ' + str(self.alert_port) + ' ] is closed')    

    def capFrame(self):
        try:
            print("[INFO] Starting video stream...")
            videoFeed = cv2.VideoCapture(0)
            #videoFeed = cv2.VideoCapture("./explosion.mp4")
            while (videoFeed.isOpened()): 
                ret, frame = videoFeed.read()
                if ret == False:
                    print("[ERROR] Failed to retrieve frame")
                    break
                    #input("Press Enter to continue...")
                if self.live_event:
                    #streamer = threading.Thread(target=self.sendStream, args=(frame,))
                    #streamer.start()
                    self.sendStream(frame)
                self.frame_list.put(frame)
                frame_filename = datetime.now().strftime(base_dir + "record/%Y%m%d-%H%M%S.png")
                cv2.imwrite(frame_filename, frame)

            print("[INFO] Closing video stream...")
            videoFeed.release()
        except Exception as e:
            print(f"[ERROR] {e}")
            os._exit(1)
        except KeyboardInterrupt:
            print("User interrupted the program.")
            os._exit(1)

    def detectAnomaly(self):        
        mean_path = get_file('c3d_mean.npy',
                                C3D_MEAN_PATH,
                                cache_subdir='models',
                                md5_hash='08a07d9761e76097985124d9e8b2fe34')
        mean = np.load(mean_path)
        frames = []
        framecount = 0
        counter = 0
        tmp = None
        while True:
            try:
                if not self.frame_list.empty():
                    frame = self.frame_list.get()
                    if framecount < frame_count:
                        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        framecount += 1
                        counter += 1
                        continue

                    np_frames = np.array(frames)

                    # Reshape to 128x171
                    reshape_frames = np.zeros((np_frames.shape[0], 128, 171, np_frames.shape[3]))
                    for i, img in enumerate(np_frames):
                        img = cv2.resize(img, (171, 128))
                        reshape_frames[i, :, :, :] = img
                    reshape_frames -= mean
                    # Crop to 112x112
                    reshape_frames = reshape_frames[:, 8:120, 30:142, :]
                    # Add extra dimension for samples
                    reshape_frames = np.expand_dims(reshape_frames, axis=0)
                
                    # extract features
                    rgb_features = []
                    rgb_feature = feature_extractor.predict(reshape_frames)[0]
                    #feature_extractor.set_tensor(input_extractor[0]['index'], reshape_frames.astype(np.float32))
                    #feature_extractor.invoke()
                    #rgb_feature = feature_extractor.get_tensor(output_extractor[0]['index'])[0]
                    rgb_features.append(rgb_feature)
                
                    rgb_features = np.array(rgb_features)
                    rgb_feature_bag = interpolate(rgb_features, features_per_bag)
                
                    # classify using the trained classifier model
                    predictions = classifier_model.predict(rgb_feature_bag)
                    #classifier_model.set_tensor(input_classifier[0]['index'], rgb_feature_bag.astype(np.float32))
                    #classifier_model.invoke()
                    #predictions = classifier_model.get_tensor(output_classifier[0]['index'])
                    predictions = np.array(predictions).squeeze()
                    predictions = extrapolate(predictions, 16)
                
                    maxprob = np.max(predictions * 100)
                    print("Preds : {:.2f}%".format(maxprob))
                    if int(maxprob) >= 80:
                        tmp = counter
                        self.sendAlert(frames, counter-16, False)
                    elif tmp is not None and counter <= tmp + 160:
                        if counter == tmp + 160:
                            print("END")
                            self.sendAlert(frames, counter-16, True)
                        else:
                            self.sendAlert(frames, counter-16, False)
                
                    frames.clear()
                    framecount = 0
                else:
                    print("Queue is empty. Waiting for data...")

            except Exception as e:
                print(f"[ERROR] {e}")
                os._exit(1)
            except KeyboardInterrupt:
                print("User interrupted the program.")
                break
                os._exit(1)

    def sendAlert(self, frames, counter, end):
        try:
            if self.online == False:
                return
            if end:
                msg = f'end_{counter}'
            else:
                msg = f'alert_{counter}'
            self.alert_socket.send(msg.encode('utf-8'))
            for frame in frames:
                #cv2.imwrite(os.getcwd() + '/alert/frame_{}.jpg'.format(counter), frame)
                frame = imutils.resize(frame, width=720, height=1280)
                a = pickle.dumps(frame)
                message = struct.pack("Q",len(a)) + a
                self.alert_socket.sendall(message) 
                counter += 1
        except Exception as e:
            print(f"[ERROR] {e}")
            self.socketClose()
            os._exit(1)

    def sendStream(self, frame):
        try:
            frame = imutils.resize(frame, width=320, height=1280)
            a = pickle.dumps(frame)
            message = struct.pack("Q",len(a)) + a
            self.live_stream.client_socket.sendall(message)
        except Exception as e:
            print(f"[ERROR] {e}")
            self.socketClose()
            os._exit(1)