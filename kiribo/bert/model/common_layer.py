import tensorflow as tf


class FeedForwardNetwork(tf.keras.models.Model):
    '''
    Transformer 用の Position-wise Feedforward Neural Network です。
    '''
    def __init__(self, hidden_dim: int, dropout_rate: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hidden_dim = hidden_dim
        self.dropout_rate = dropout_rate

        self.filter_dense_layer = tf.keras.layers.Dense(hidden_dim * 4, use_bias=True,
                                                        activation=tf.nn.relu, name='filter_layer')
        self.output_dense_layer = tf.keras.layers.Dense(hidden_dim, use_bias=True, name='output_layer')
        self.dropout_layer = tf.keras.layers.Dropout(dropout_rate)

    def call(self, input: tf.Tensor, training: bool) -> tf.Tensor:
        '''
        FeedForwardNetwork を適用します。
        :param input: shape = [batch_size, length, hidden_dim]
        :return: shape = [batch_size, length, hidden_dim]
        '''
        tensor = self.filter_dense_layer(input)
        tensor = self.dropout_layer(tensor, training=training)
        return self.output_dense_layer(tensor)


class ResidualNormalizationWrapper(tf.keras.models.Model):
    '''
    与えられたレイヤー（もしくはモデル）に対して、下記のノーマライゼーションを行います。
    - Layer Normalization
    - Dropout
    - Residual Connection
    '''
    def __init__(self, layer: tf.keras.layers.Layer, dropout_rate: float, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.layer = layer
        self.layer_normalization = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        self.dropout_layer = tf.keras.layers.Dropout(dropout_rate)

    def call(self, input: tf.Tensor, training: bool, *args, **kwargs) -> tf.Tensor:
        tensor = self.layer_normalization(input)
        tensor = self.layer(tensor, training=training, *args, **kwargs)
        tensor = self.dropout_layer(tensor, training=training)
        return input + tensor
