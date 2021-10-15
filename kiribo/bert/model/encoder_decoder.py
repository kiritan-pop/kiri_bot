# -*- coding: utf-8 -*-

from json import encoder
import tensorflow as tf
from transformers import TFBertModel
from typing import List
from .common_layer import FeedForwardNetwork, ResidualNormalizationWrapper
from .embedding import TokenEmbedding, AddPositionalEncoding
from .attention import MultiheadAttention, SelfAttention


def build_encoder(
            input_length: int = 32,
            model_name: str = "cl-tohoku/bert-base-japanese",
        ) -> tf.keras.models.Model:

    input_shape = (input_length, )
    input_ids = tf.keras.layers.Input(input_shape, dtype=tf.int32, name="input_ids")
    input_attention_mask = tf.keras.layers.Input(input_shape, dtype=tf.int32, name="input_attention_mask")
    encoder = TFBertModel.from_pretrained(model_name, output_attentions=True)
    encoder.trainable = False
    x = encoder(
        input_ids,
        attention_mask=input_attention_mask,
    )

    model = tf.keras.Model(inputs=[input_ids, input_attention_mask], outputs=[x[1]])
    return model


def build_decoder(
            vocab_size: int,
            hopping_num: int = 6,
            head_num: int = 8,
            hidden_dim: int = 512,
            dropout_rate: float = 0.1,
            encoder_output_dim: int = 768,
            target_length: int = 64,
        ) -> tf.keras.models.Model:

    encoder_output = tf.keras.layers.Input((encoder_output_dim,), name="encoder_output")
    x = tf.keras.layers.GaussianNoise(0.05)(encoder_output)
    x = tf.keras.layers.Reshape((1, hidden_dim))(x)

    target_ids = tf.keras.layers.Input((target_length,), dtype=tf.int32, name="target_ids")
    decoder = Decoder(
        vocab_size=vocab_size,
        hopping_num=hopping_num,
        head_num=head_num,
        hidden_dim=hidden_dim,
        dropout_rate=dropout_rate,
    )
    output = decoder(
        input=target_ids, 
        encoder_output=x, 
    )
    model = tf.keras.Model(inputs=[encoder_output, target_ids], outputs=[output])
    return model


def build_encoder_decoder(
            vocab_size: int,
            hopping_num: int = 6,
            head_num: int = 8,
            hidden_dim: int = 512,
            dropout_rate: float = 0.1,
            input_length: int = 32,
            target_length: int = 64,
            model_name: str = "cl-tohoku/bert-base-japanese",
        ) -> tf.keras.models.Model:

    input_shape = (input_length, )
    target_shape = (target_length, )
    input_ids = tf.keras.layers.Input(input_shape, dtype=tf.int32, name="input_ids")
    input_attention_mask = tf.keras.layers.Input(input_shape, dtype=tf.int32, name="input_attention_mask")
    encoder = TFBertModel.from_pretrained(model_name, output_attentions=True)
    encoder.trainable = False
    x = encoder(
        input_ids,
        attention_mask=input_attention_mask,
    )
    x = tf.keras.layers.Dense(hidden_dim*2)(x[1])
    x = tf.keras.layers.Reshape((1, hidden_dim*2))(x)

    target_ids = tf.keras.layers.Input(target_shape, dtype=tf.int32, name="target_ids")
    decoder = Decoder(
        vocab_size=vocab_size,
        hopping_num=hopping_num,
        head_num=head_num,
        hidden_dim=hidden_dim,
        dropout_rate=dropout_rate,
    )
    output = decoder(
        input=target_ids, 
        encoder_output=x, 
    )
    model = tf.keras.Model(inputs=[input_ids, input_attention_mask, target_ids], outputs=[output])
    return model


class Decoder(tf.keras.models.Model):
    '''
    エンコードされたベクトル列からトークン列を生成する Decoder です。
    '''
    def __init__(
            self,
            vocab_size: int,
            hopping_num: int,
            head_num: int,
            hidden_dim: int,
            dropout_rate: float,
            pad_id: int=0,
            *args,
            **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.hopping_num = hopping_num
        self.head_num = head_num
        self.hidden_dim = hidden_dim
        self.dropout_rate = dropout_rate
        self.pad_id = pad_id

        self.token_embedding = TokenEmbedding(vocab_size, hidden_dim)
        self.add_position_embedding = AddPositionalEncoding()
        self.input_dropout_layer = tf.keras.layers.Dropout(dropout_rate)

        self.attention_block_list: List[List[tf.keras.models.Model]] = []
        for _ in range(hopping_num):
            self_attention_layer = SelfAttention(hidden_dim, head_num, dropout_rate, name='self_attention')
            enc_dec_attention_layer = MultiheadAttention(hidden_dim, head_num, dropout_rate, name='enc_dec_attention')
            ffn_layer = FeedForwardNetwork(hidden_dim, dropout_rate, name='ffn')
            self.attention_block_list.append([
                ResidualNormalizationWrapper(self_attention_layer, dropout_rate, name='self_attention_wrapper'),
                ResidualNormalizationWrapper(enc_dec_attention_layer, dropout_rate, name='enc_dec_attention_wrapper'),
                ResidualNormalizationWrapper(ffn_layer, dropout_rate, name='ffn_wrapper'),
            ])
        self.output_normalization = tf.keras.layers.LayerNormalization(epsilon=1e-6)
        # 注：本家ではここは TokenEmbedding の重みを転地したものを使っている
        self.output_dense_layer = tf.keras.layers.Dense(vocab_size, use_bias=False, activation='softmax')

    def call(
            self,
            input: tf.Tensor,
            encoder_output: tf.Tensor,
            training: bool,
            target_mask: tf.Tensor=None,
            source_mask: tf.Tensor=None,
    ) -> tf.Tensor:
        '''
        モデルを実行します

        :param input: shape = [batch_size, length]
        :param training: 学習時は True
        :return: shape = [batch_size, length, hidden_dim]
        '''
        # [batch_size, length, hidden_dim]
        embedded_input = self.token_embedding(input)
        embedded_input = self.add_position_embedding(embedded_input)
        query = self.input_dropout_layer(embedded_input, training=training)
        enc_attention_mask = self._create_enc_attention_mask(attention_mask=source_mask)
        if target_mask:
            dec_self_attention_mask = self._create_dec_self_attention_mask(attention_mask=target_mask)
        else:
            dec_self_attention_mask = self._create_dec_self_attention_mask(attention_mask=input)

        # batch_size, length = tf.unstack(tf.shape(encoder_output))
        # encoder_output = tf.reshape(encoder_output, [batch_size, 1, length])
        for i, layers in enumerate(self.attention_block_list):
            self_attention_layer, enc_dec_attention_layer, ffn_layer = tuple(layers)
            with tf.name_scope(f'hopping_{i}'):
                query = self_attention_layer(query, attention_mask=dec_self_attention_mask, training=training)
                query = enc_dec_attention_layer(query, memory=encoder_output,
                                                attention_mask=enc_attention_mask, training=training)
                query = ffn_layer(query, training=training)

        query = self.output_normalization(query)  # [batch_size, length, hidden_dim]
        return self.output_dense_layer(query)  # [batch_size, length, vocab_size]

    def _create_enc_attention_mask(self, attention_mask: tf.Tensor):
        if attention_mask:
            # PADDING された部分を無視するためのマスク
            batch_size, length = tf.unstack(tf.shape(attention_mask))
            pad_array = tf.equal(attention_mask, self.pad_id)  # [batch_size, m_length]
            # shape broadcasting で [batch_size, head_num, (m|q)_length, m_length] になる
            return tf.reshape(pad_array, [batch_size, 1, 1, length])
        else:
            return tf.zeros([1, 1, 1, 1], dtype=tf.dtypes.int8)


    def _create_dec_self_attention_mask(self, attention_mask: tf.Tensor):
        batch_size, length = tf.unstack(tf.shape(attention_mask))
        pad_array = tf.equal(attention_mask, self.pad_id)  # [batch_size, m_length]
        pad_array = tf.reshape(pad_array, [batch_size, 1, 1, length])

        autoregression_array = tf.logical_not(
            tf.linalg.band_part(tf.ones([length, length], dtype=tf.bool), -1, 0))  # 下三角が False
        autoregression_array = tf.reshape(autoregression_array, [1, 1, length, length])
        return tf.logical_or(pad_array, autoregression_array)
