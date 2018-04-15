# coding: utf-8

import numpy as np
import chainer
import cv2
import os.path
import unet, lnet
import six
import os
from chainer import cuda, optimizers, serializers, Variable

def cvt2YUV(img):
    (major, minor, _) = cv2.__version__.split(".")
    if major == '3':
        img = cv2.cvtColor( img, cv2.COLOR_RGB2YUV )
    else:
        img = cv2.cvtColor( img, cv2.COLOR_BGR2YUV )
    return img

def cvt2GRAY(img):
    if len(img.shape) == 2:
        # Grayscale image
        return img
    width, height, color = img.shape
    if color == 4:
        # RGBA image
        r, g, b, a = cv2.split(img)
        white = (255 - a).repeat(3).reshape((width, height, 3))
        img2 = cv2.merge((r, g, b)).astype(np.uint32)
        img2 += white
        img2 = img2.clip(0, 255).astype(np.uint8)
        return cv2.cvtColor(img2, cv2.COLOR_RGB2GRAY)
    else:
        # RGB image
        return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

class ImageAndRefDataset(chainer.dataset.DatasetMixin):

    def __init__(self, paths, root1='./input', root2='./ref', dtype=np.float32):
        self._paths = paths
        self._root1 = root1
        self._root2 = root2
        self._dtype = dtype

    def __len__(self):
        return len(self._paths)

    def get_name(self, i):
        return self._paths[i]

    def get_example(self, i, minimize=False, blur=0, s_size=128):
        path1 = os.path.join(self._root1, self._paths[i])
        print(path1)
        image1 = cv2.imread(path1, cv2.IMREAD_UNCHANGED )
        print(image1.shape)
        image1 = cvt2GRAY(image1)
        print(image1.shape)

        print("load:" + path1, os.path.isfile(path1), image1 is None)
        image1 = np.asarray(image1, self._dtype)

        _image1 = image1.copy()
        if minimize:
            print(image1.shape)
            if image1.shape[0] < image1.shape[1]:
                s0 = s_size
                s1 = int(image1.shape[1] * (s_size / image1.shape[0]))
                s1 = s1 - s1 % 16
                _s0 = 4 * s0
                _s1 = int(image1.shape[1] * ( _s0 / image1.shape[0]))
                _s1 = (_s1+8) - (_s1+8) % 16
            else:
                s1 = s_size
                s0 = int(image1.shape[0] * (s_size / image1.shape[1]))
                s0 = s0 - s0 % 16
                _s1 = 4 * s1
                _s0 = int(image1.shape[0] * ( _s1 / image1.shape[1]))
                _s0 = (_s0+8) - (_s0+8) % 16

            _image1 = image1.copy()
            _image1 = cv2.resize(_image1, (_s1, _s0),
                                 interpolation=cv2.INTER_AREA)
            #noise = np.random.normal(0,5*np.random.rand(),_image1.shape).astype(self._dtype)

            if blur > 0:
                blured = cv2.blur(_image1, ksize=(blur, blur))
                image1 = _image1 + blured - 255

            image1 = cv2.resize(image1, (s1, s0), interpolation=cv2.INTER_AREA)
            print(image1.shape)

        # image is grayscale
        if image1.ndim == 2:
            image1 = image1[:, :, np.newaxis]
        if _image1.ndim == 2:
            _image1 = _image1[:, :, np.newaxis]

        image1 = np.insert(image1, 1, -512, axis=2)
        image1 = np.insert(image1, 2, 128, axis=2)
        image1 = np.insert(image1, 3, 128, axis=2)

        # add color ref image
        # path_ref = os.path.join(self._root2, self._paths[i])
        path_ref = os.path.join(self._root1, self._paths[i])

        if minimize:
            print(path_ref)
            print(cv2.IMREAD_UNCHANGED)
            image_ref = cv2.imread(path_ref, cv2.IMREAD_UNCHANGED)
            image_ref = cv2.resize(image_ref, (image1.shape[1], image1.shape[
                                   0]), interpolation=cv2.INTER_NEAREST)
            if image_ref.shape[2] == 4:
                b, g, r, a = cv2.split(image_ref)
                for x in range(image1.shape[0]):
                    for y in range(image1.shape[1]):
                        if a[x][y] != 0:
                            for ch in range(3):
                                image1[x][y][ch + 1] = image_ref[x][y][ch]
            elif  image_ref.shape[2] == 3:
                b, g, r = cv2.split(image_ref)
            image_ref = cvt2YUV( cv2.merge((b, g, r)) )


        else:
            image_ref = cv2.imread(path_ref, cv2.IMREAD_COLOR)
            image_ref = cvt2YUV(image_ref)
            image1 = cv2.resize(
                image1, (4 * image_ref.shape[1], 4 * image_ref.shape[0]), interpolation=cv2.INTER_AREA)
            image_ref = cv2.resize(image_ref, (image1.shape[1], image1.shape[
                                   0]), interpolation=cv2.INTER_AREA)

            image1[:, :, 1:] = image_ref

        return image1.transpose(2, 0, 1), _image1.transpose(2, 0, 1)


class Painter:

    def __init__(self, gpu=3):

        print("start")
        self.root = "./"
        self.batchsize = 1
        self.outdir = self.root
        self.outdir_min = self.root + "out_min/"
        self.gpu = gpu
        self._dtype = np.float32

        print("load model")
        if self.gpu >= 0:
            cuda.get_device(self.gpu).use()
            cuda.set_max_workspace_size(1024 * 1024 * 1024)  # 64MB
            chainer.Function.type_check_enable = False
        self.cnn_128 = unet.UNET()
        self.cnn_512 = unet.UNET()
        if self.gpu >= 0:
            self.cnn_128.to_gpu()
            self.cnn_512.to_gpu()
        serializers.load_npz(
            "./db/unet_128_standard", self.cnn_128)
        serializers.load_npz(
            "./db/unet_512_standard", self.cnn_512)

    def save_as_img(self, array, name):
        array = array.transpose(1, 2, 0)
        array = array.clip(0, 255).astype(np.uint8)
        array = cuda.to_cpu(array)
        (major, minor, _) = cv2.__version__.split(".")
        if major == '3':
            img = cv2.cvtColor(array, cv2.COLOR_YUV2RGB)
        else:
            img = cv2.cvtColor(array, cv2.COLOR_YUV2BGR)
        cv2.imwrite(name, img)

    def colorize(self, filename, step='C', blur=4, s_size=128,colorize_format="png"):
        if self.gpu >= 0:
            cuda.get_device(self.gpu).use()

        _ = {'S': "ref/", 'L': "out_min/", 'C': "ref/"}
        dataset = ImageAndRefDataset(
            paths=[filename], root1=self.root, root2=self.root + _[step])

        _ = {'S': True, 'L': False, 'C': True}
        sample = dataset.get_example(0, minimize=_[step], blur=blur, s_size=s_size)

        _ = {'S': 0, 'L': 1, 'C': 0}[step]
        sample_container = np.zeros(
            (1, 4, sample[_].shape[1], sample[_].shape[2]), dtype='f')
        sample_container[0, :] = sample[_]

        if self.gpu >= 0:
            sample_container = cuda.to_gpu(sample_container)

        cnn = {'S': self.cnn_128, 'L': self.cnn_512, 'C': self.cnn_128}
        with chainer.no_backprop_mode():
            with chainer.using_config('train', False):
                image_conv2d_layer = cnn[step].calc(Variable(sample_container))
        del sample_container

        if step == 'C':
            input_bat = np.zeros((1, 4, sample[1].shape[1], sample[1].shape[2]), dtype='f')
            print(input_bat.shape)
            input_bat[0, 0, :] = sample[1]

            output = cuda.to_cpu(image_conv2d_layer.data[0])
            del image_conv2d_layer  # release memory

            for channel in range(3):
                input_bat[0, 1 + channel, :] = cv2.resize(
                    output[channel, :],
                    (sample[1].shape[2], sample[1].shape[1]),
                    interpolation=cv2.INTER_CUBIC)

            if self.gpu >= 0:
                link = cuda.to_gpu(input_bat, None)
            else:
                link = input_bat
            with chainer.no_backprop_mode():
                with chainer.using_config('train', False):
                    image_conv2d_layer = self.cnn_512.calc(Variable(link))
            del link  # release memory

        image_out_path = self.outdir + filename.split(".")[0] + "_color.png"
        self.save_as_img(image_conv2d_layer.data[0], image_out_path)
        del image_conv2d_layer
        return image_out_path

if __name__ == '__main__':
    p = Painter(gpu=1)
    print(p.colorize("media/7656.jpg"))
