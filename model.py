import keras
import keras.backend as K
import multiprocessing
import scipy.io as sio
from keras.models import Sequential, Model
from keras.layers import Dense, Dropout, Flatten
from keras.layers import Conv3D, MaxPooling3D, ZeroPadding3D
from keras.regularizers import l2 

base_dir = "./"
c3d_model_weights = base_dir + "model/weights/c3d_sports1m.h5"
classifier_model_weigts = base_dir + "model/weights/weights_L1L2.mat"

def C3D(weights='sports1M'):
    if weights not in {'sports1M', None}:
        raise ValueError('weights should be either be sports1M or None')

    if K.image_data_format() == 'channels_last':
        shape = (16, 112, 112, 3)
    else:
        shape = (3, 16, 112, 112)

    model = Sequential()
    model.add(
        Conv3D(64, 3, activation='relu', padding='same', name='conv1', input_shape=shape))
    model.add(
        MaxPooling3D(pool_size=(1, 2, 2),
                     strides=(1, 2, 2),
                     padding='same',
                     name='pool1'))

    model.add(Conv3D(128, 3, activation='relu', padding='same', name='conv2'))
    model.add(
        MaxPooling3D(pool_size=(2, 2, 2),
                     strides=(2, 2, 2),
                     padding='valid',
                     name='pool2'))

    model.add(Conv3D(256, 3, activation='relu', padding='same', name='conv3a'))
    model.add(Conv3D(256, 3, activation='relu', padding='same', name='conv3b'))
    model.add(
        MaxPooling3D(pool_size=(2, 2, 2),
                     strides=(2, 2, 2),
                     padding='valid',
                     name='pool3'))

    model.add(Conv3D(512, 3, activation='relu', padding='same', name='conv4a'))
    model.add(Conv3D(512, 3, activation='relu', padding='same', name='conv4b'))
    model.add(
        MaxPooling3D(pool_size=(2, 2, 2),
                     strides=(2, 2, 2),
                     padding='valid',
                     name='pool4'))

    model.add(Conv3D(512, 3, activation='relu', padding='same', name='conv5a'))
    model.add(Conv3D(512, 3, activation='relu', padding='same', name='conv5b'))
    model.add(ZeroPadding3D(padding=(0, 1, 1)))
    model.add(
        MaxPooling3D(pool_size=(2, 2, 2),
                     strides=(2, 2, 2),
                     padding='valid',
                     name='pool5'))

    model.add(Flatten())

    model.add(Dense(4096, activation='relu', name='fc6'))
    model.add(Dropout(0.5))
    model.add(Dense(4096, activation='relu', name='fc7'))
    model.add(Dropout(0.5))
    model.add(Dense(487, activation='softmax', name='fc8'))

    if weights == 'sports1M':
        model.load_weights(c3d_model_weights)

    return model

def c3d_feature_extractor():
    model = C3D()
    layer_name = 'fc6'
    feature_extractor_model = Model(inputs=model.input,
                                    outputs=model.get_layer(layer_name).output)
    return feature_extractor_model

def classifier_model():
    model = Sequential()
    model.add(Dense(512, input_dim=4096, kernel_initializer='glorot_normal',
                    kernel_regularizer=l2(0.001), activation='relu'))
    model.add(Dropout(0.6))
    model.add(Dense(32, kernel_initializer='glorot_normal',
                    kernel_regularizer=l2(0.001)))
    model.add(Dropout(0.6))
    model.add(Dense(1, kernel_initializer='glorot_normal',
                    kernel_regularizer=l2(0.001), activation='sigmoid'))
    return model

def conv_dict(dict2):
    dict = {}
    for i in range(len(dict2)):
        if str(i) in dict2:
            if dict2[str(i)].shape == (0, 0):
                dict[str(i)] = dict2[str(i)]
            else:
                weights = dict2[str(i)][0]
                weights2 = []
                for weight in weights:
                    if weight.shape in [(1, x) for x in range(0, 5000)]:
                        weights2.append(weight[0])
                    else:
                        weights2.append(weight)
                dict[str(i)] = weights2
    return dict

def load_weights(model, weights_file):
    dict2 = sio.loadmat(weights_file)
    dict = conv_dict(dict2)
    i = 0
    for layer in model.layers:
        weights = dict[str(i)]
        layer.set_weights(weights)
        i += 1
    return model

def build_classifier_model():
    model = classifier_model()
    model = load_weights(model, classifier_model_weigts)
    return model