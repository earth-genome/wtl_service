"""MashNet model on 2019.07.01."""

from keras.models import Model
from keras.layers import *
from keras.optimizers import Adam
    
def combo_model(texts_shape=(6, 512), quants_shape=(5,), output_len=3):

    # Text part
    text_input = Input(shape=texts_shape, name='mentions')
    x = Flatten(data_format='channels_first')(text_input)
    x = _activate('relu', Dense(128)(x))
    x = Dropout(.5)(x)
    #x = _activate('relu', Dense(64)(x))
    #x = Dropout(.5)(x)   
    text_output = _activate('softmax', Dense(output_len)(x),
                             name='mentions_output')

    # Quantitative part
    quants_input = Input(shape=quants_shape, name='quants')

    # Combined
    combo_input = concatenate([text_output, quants_input])
    y = _activate('relu', Dense(64)(combo_input))
    y = Dropout(.3)(y)
    y = _activate('relu', Dense(64)(y))
    y = Dropout(.3)(y)
    main_output = _activate('softmax', Dense(output_len)(y),
                            name='main_output')

    model = Model(inputs=[text_input, quants_input],
                  outputs=[text_output, main_output])
    model.compile(optimizer=Adam(lr=1e-3), loss='categorical_crossentropy',
                  loss_weights={'mentions_output': .2, 'main_output': 1.},
                  metrics=['accuracy'])
    print(model.summary())
    return model

def _activate(activation, layer_output, name=None):
    return Activation(activation, name=name)(BatchNormalization()(layer_output))
