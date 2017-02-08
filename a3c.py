"""Defines policy networks for asynchronous advantage actor-critic architectures.

Heavily influenced by DeepMind's seminal paper 'Asynchronous Methods for Deep Reinforcement
Learning' (Mnih et al., 2016).
"""

import math
import numpy as np
import tensorflow as tf


def _convolutional_layer(x, shape, stride, activation_fn):
    if len(shape) != 4:
        raise ValueError('Shape "{}" is invalid. Must have length 4.'.format(shape))

    num_input_params = shape[0] * shape[1] * shape[2]
    num_output_params = shape[0] * shape[1] * shape[3]
    maxval = math.sqrt(6 / (num_input_params + num_output_params))
    W = tf.Variable(tf.random_uniform(shape, -maxval, maxval), name='Weights')
    b = tf.Variable(tf.constant(0.1, shape=[shape[3]]), name='Bias')
    conv = tf.nn.conv2d(x, W, [1, stride, stride, 1], 'VALID')

    return activation_fn(tf.nn.bias_add(conv, b))


def _fully_connected_layer(x, shape, activation_fn, shared_bias=False):
    if len(shape) != 2:
        raise ValueError('Shape "{}" is invalid. Must have length 2.'.format(shape))

    maxval = math.sqrt(6 / (shape[0] + shape[1]))
    W = tf.Variable(tf.random_uniform(shape, -maxval, maxval), name='Weights')

    if shared_bias:
        b = tf.Variable(tf.constant(0.1, shape=[1]), name='Bias')
    else:
        b = tf.Variable(tf.constant(0.1, shape=[shape[1]]), name='Bias')

    return activation_fn(tf.matmul(x, W) + b)


class PolicyNetwork():
    def __init__(self, num_actions, state_shape):
        """Defines a policy network implemented as a convolutional recurrent neural network.

        Args:
            num_actions: Number of possible actions.
            state_shape: A vector with three values, representing the width, height and depth of
                input states. For example, the shape of 100x80 RGB images is [100, 80, 3].
        """

        width, height, depth = state_shape
        self.x = tf.placeholder(tf.float32, [None, width, height, depth], name='Input_States')
        batch_size = tf.shape(self.x)[:1]

        with tf.name_scope('Convolutional_Layer_1'):
            h_conv1 = _convolutional_layer(self.x, [3, 3, depth, 32], 2, tf.nn.elu)

        with tf.name_scope('Convolutional_Layer_2'):
            h_conv2 = _convolutional_layer(h_conv1, [3, 3, 32, 32], 2, tf.nn.elu)

        with tf.name_scope('Convolutional_Layer_3'):
            h_conv3 = _convolutional_layer(h_conv2, [3, 3, 32, 32], 2, tf.nn.elu)

        with tf.name_scope('Convolutional_Layer_4'):
            h_conv4 = _convolutional_layer(h_conv3, [3, 3, 32, 32], 2, tf.nn.elu)

        # Flatten the output to feed it into the LSTM layer.
        num_params = np.prod(h_conv4.get_shape().as_list()[1:])
        h_flat = tf.reshape(h_conv4, [-1, num_params])

        with tf.name_scope('LSTM_Layer'):
            self.lstm_state = (tf.placeholder(tf.float32, [1, 256]),
                               tf.placeholder(tf.float32, [1, 256]))

            self.initial_lstm_state = (np.zeros([1, 256], np.float32),
                                       np.zeros([1, 256], np.float32))

            lstm_state = tf.contrib.rnn.rnn_cell.LSTMStateTuple(*self.lstm_state)
            lstm = tf.contrib.rnn.rnn_cell.BasicLSTMCell(256)

            # tf.nn.dynamic_rnn expects inputs of shape [batch_size, time, features], but the shape
            # of h_flat is [batch_size, features]. We want the batch_size dimension to be treated as
            # the time dimension, so the input is redundantly expanded to [1, batch_size, features].
            # The LSTM layer will assume it has 1 batch with a time dimension of length batch_size.
            lstm_input = tf.expand_dims(h_flat, [0])
            lstm_output, self.new_lstm_state = tf.nn.dynamic_rnn(lstm,
                                                                 lstm_input,
                                                                 batch_size,
                                                                 lstm_state)
            # Delete the fake batch dimension.
            lstm_output = tf.reshape(lstm_output, [-1, 256])

        self.logits = _fully_connected_layer(lstm_output_flat, [256, num_actions], tf.identity)
        self.value = _fully_connected_layer(lstm_output_flat, [256, 1], tf.identity)
        self.parameters = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,
                                            tf.get_variable_scope().name)
