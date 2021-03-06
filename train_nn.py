#!/usr/bin/env python3

"""
Simple script to train a neural network with keras
"""

import argparse
import numpy as np
import h5py
import os
import json

def get_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_file')
    parser.add_argument('-e','--epochs', type=int, default=1)
    parser.add_argument('-o','--output-dir', default='model')
    return parser.parse_args()

###############################################################
# Main Training Part
###############################################################

def run():
    args = get_args()

    # get the jets out of the input file.
    with h5py.File(args.input_file, 'r') as infile:
        jets = np.asarray(infile['jets'])

    # first, let's make the training dataset!
    input_data = preproc_inputs(jets)
    targets = make_targets(jets)

    # now make the network
    from keras.layers import Input, Dense, Softmax
    from keras.models import Model

    input_node = Input(shape=(5,))
    dense = Dense(3)(input_node)
    pred = Softmax()(dense)
    model = Model(inputs=input_node, outputs=pred)
    model.compile(optimizer='rmsprop',
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])

    # now fit this thing!
    model.fit(input_data, targets, epochs=args.epochs)

    # finally, save the trained network
    odir = args.output_dir
    if not os.path.isdir(odir):
        os.mkdir(odir)
    with open(f'{odir}/architecture.json','w') as arch_file:
        arch_file.write(model.to_json(indent=2))
    model.save_weights(f'{odir}/weights.h5')

    # also write out the variable specification
    with open(f'{odir}/variables.json', 'w') as vars_file:
        json.dump(get_variables_json(), vars_file)


def make_targets(jets):
    labels = jets['HadronConeExclExtendedTruthLabelID']
    targets = np.stack([labels == x for x in [0, 4, 5]], axis=1)
    return np.asarray(targets, dtype=int)


def get_discrim(jets, model_path, weights_path):
    """
    Get the discriminant from a saved model
    """

    # this just silences some annoying warnings that I get from
    # tensorflow. They might be useful for training but in evaluation
    # they should be harmless.
    os.environ['TF_CPP_MIN_LOG_LEVEL']='2'

    # load the model
    from keras.models import model_from_json
    with open(model_path,'r') as model_file:
        model = model_from_json(model_file.read())
    model.load_weights(weights_path)

    # get the model inputs
    input_data = preproc_inputs(jets)
    outputs = model.predict(input_data)
    b_weight, light_weights = outputs[:,2], outputs[:,0]
    output_log_ratio = np.log(b_weight / light_weights)
    return output_log_ratio



####################################################################
# Preprocessing and saving the configuration
####################################################################
#
# These constants are used to normalize the NN inputs. We typically
# want inputs that are around zero with standard deviations around 1,
# but this doesn't need to be exact.
JF_NAME = 'JetFitter_significance3d'
JF_OFFSET = -0.7
JF_SCALE = 0.75
JF_DEFAULT = 0.1
RNN_VARS = [f'rnnip_p{x}' for x in list('bcu') + ['tau']]
RNN_DEFAULT = 0.1
RNN_OFFSET = -0.5
RNN_SCALE = 2.0

def preproc_inputs(jets):
    """
    We make some hardcoded transformations to normalize these inputs
    """

    # The jf_sig variable has a long tail. To "normalize" this a bit
    # we take the log(x + 1) transformation.
    jf = jets[JF_NAME]
    jf[np.isnan(jf)] = JF_DEFAULT
    jf = (jf + JF_OFFSET ) * JF_SCALE

    rnns = []
    for rnn_var in RNN_VARS:
        rnnip = jets[rnn_var]
        rnnip[np.isnan(rnnip)] = RNN_DEFAULT
        rnnip = (rnnip + RNN_OFFSET) * RNN_SCALE
        rnns.append(rnnip)
    stack = np.stack([jf] + rnns, axis=1)
    assert not np.any(np.isnan(stack))
    return stack

def get_variables_json():
    """
    Make a file that specifies the input variables and
    transformations as JSON, so that the network can be used with lwtnn
    """

    # This is a more 'traditional' network with one set of inputs so
    # we just have to name the variables in one input node. In more
    # advanced cases we could have multiple input nodes, some of which
    # might operate on sequences.
    btag_variables = [
        {
            # Note this is not the same name we use in the file! We'll
            # have to make the log1p transformation in the C++ code to
            # build this variable.
            'name': JF_NAME,
            'offset': JF_OFFSET,
            'scale': JF_SCALE,
            'default': JF_DEFAULT,
        }
    ]
    for rnn in RNN_VARS:
        entry = {
            'name': rnn,
            'offset': RNN_OFFSET,
            'scale': RNN_SCALE,
            'default': RNN_DEFAULT,
        }
        btag_variables.append(entry)

    # note that this is a list of output nodes, where each node can
    # have multiple output values. In principal we could also add a
    # regression output to the same network (i.e. the b-hadron pt) but
    # that's a more advanced subject.
    outputs = [
        {
            'name': 'DL2',
            'labels': ['pu', 'pc', 'pb']
        }
    ]

    # lwtnn expects a specific format that allows multiple input and
    # output nodes, so we have to dress the above information a bit.
    final_dict = {
        'input_sequences': [],
        'inputs': [
            {
                'name': 'btag_variables',
                'variables': btag_variables
            }
        ],
        'outputs': outputs
    }

    return final_dict



if __name__ == '__main__':
    run()
