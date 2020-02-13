from __future__ import print_function
# just a commentd
import os
from keras.callbacks import TensorBoard
from keras.applications.inception_v3 import InceptionV3
from keras.applications.imagenet_utils import preprocess_input
from keras.models import Model
from keras.layers import Dense, Flatten, Input
from utils import RotNetDataGenerator, angle_error, CustomModelCheckpoint
from keras import optimizers
import numpy as np
import glob
from shutil import copyfile
import datetime, random
import tensorflow as tf
from keras.backend.tensorflow_backend import set_session

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
config.allow_soft_placement = True
set_session(tf.Session(config=config))

model_name = 'model_multi_class/'
SAVE = "logs/" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + '/'
# Save
output_folder = SAVE + model_name
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

output_log = output_folder + "Log/"
if not os.path.exists(output_log):
    os.makedirs(output_log)

output_weight = output_folder + "Best/"
if not os.path.exists(output_weight):
    os.makedirs(output_weight)

# training parameters
batch_size = 64
nb_epoch = 10000

IMAGE_FILE_PATH_DISTORTED = "/media/yoonjae/My Passport/testDataset/"

classes_focal = list(np.arange(40, 501, 10))# focal

def get_paths(IMAGE_FILE_PATH_DISTORTED):
    paths_train = glob.glob(IMAGE_FILE_PATH_DISTORTED+'train/' + "*.jpg")
    paths_train.sort()
    parameters = []
    labels_train = []
    # paths = paths[:50000] +paths[150000:160000]+ paths[-50000:]
    for path in paths_train:
        curr_parameter = float((path.split('_f_'))[1].split('_d_')[0])
        parameters.append(curr_parameter)
        curr_class = classes_focal.index(curr_parameter)
        labels_train.append(curr_class)

    c = list(zip(paths_train, labels_train))
    random.shuffle(c)
    paths_train, labels_train = zip(*c)
    paths_train, labels_train = list(paths_train), list(labels_train)

    paths_valid = glob.glob(IMAGE_FILE_PATH_DISTORTED + 'valid/' + "*.jpg")
    paths_valid.sort()
    parameters = []
    labels_valid = []
    # paths = paths[:50000] +paths[150000:160000]+ paths[-50000:]
    for path in paths_valid:
        curr_parameter = float((path.split('_f_'))[1].split('_d_')[0])
        parameters.append(curr_parameter)
        curr_class = classes_focal.index(curr_parameter)
        labels_valid.append(curr_class)

    c = list(zip(paths_valid, labels_valid))
    random.shuffle(c)
    paths_valid, labels_valid = zip(*c)
    paths_valid, labels_valid = list(paths_valid), list(labels_valid)


    return paths_train, labels_train, paths_valid, labels_valid


paths_train, labels_train, paths_valid, labels_valid = get_paths(IMAGE_FILE_PATH_DISTORTED)

print(len(paths_train), 'train samples')
print(len(paths_valid), 'valid samples')

with tf.device('/gpu:1'):
    input_shape = (299, 299, 3)
    main_input = Input(shape=input_shape, dtype='float32', name='main_input')
    phi_model = InceptionV3(weights='imagenet', include_top=False, input_tensor=main_input, input_shape=input_shape,pooling='avg')
    phi_features = phi_model.output
    # phi_flattened = Flatten(name='phi-flattened')(phi_features)
    final_output_phi = Dense(len(classes_focal), activation='softmax', name='fc181-phi')(phi_features)

    layer_index = 0
    for layer in phi_model.layers:
        layer.name = layer.name + "_phi"

    model = Model(input=main_input, output=final_output_phi)

    learning_rate = 10 ** -5
    adam = optimizers.Adam(lr=learning_rate)
    model.compile(loss='categorical_crossentropy',
                  optimizer=adam,
                  metrics=['accuracy']
                  )
    model.summary()
    model_json = phi_model.to_json()

    with open(output_folder + "model.json", "w") as json_file:
        json_file.write(model_json)

    copyfile(os.path.basename(__file__), output_folder + os.path.basename(__file__))

    tensorboard = TensorBoard(log_dir=output_log)

    checkpointer = CustomModelCheckpoint(
        model_for_saving=model,
        filepath=output_weight + "weights_{epoch:02d}_{val_loss:.2f}.h5",
        save_best_only=True,
        monitor='val_loss',
        save_weights_only=True
    )

    generator_training = RotNetDataGenerator(input_shape=input_shape, batch_size=batch_size, one_hot=True,
                                             preprocess_func=preprocess_input, shuffle=True).generate(paths_train,
                                                                                                      labels_train,
                                                                                                      len(classes_focal))
    generator_valid = RotNetDataGenerator(input_shape=input_shape, batch_size=batch_size, one_hot=True,
                                          preprocess_func=preprocess_input, shuffle=True).generate(paths_valid,
                                                                                                   labels_valid,
                                                                                                   len(classes_focal))

    # training loop
    model.fit_generator(
        generator=generator_training,
        steps_per_epoch=(len(paths_train) // batch_size), # 29977
        epochs=nb_epoch,
        validation_data=generator_valid,
        validation_steps=(len(paths_valid) // batch_size),
        callbacks=[tensorboard, checkpointer],
        use_multiprocessing=True,
        workers=2,
        # verbose=3
    )