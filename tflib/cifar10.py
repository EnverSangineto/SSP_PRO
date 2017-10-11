import numpy as np

import os
import urllib
import gzip
import cPickle as pickle
from scipy.stats import rv_discrete

def unpickle(file):
    fo = open(file, 'rb')
    dict = pickle.load(fo)
    fo.close()
    return dict['data']
##added by Dan ###
def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    return np.exp(x) / np.sum(np.exp(x), axis=0)

def cifar_generator(filenames, batch_size, data_dir, probability_array, ratio, eval_bool):
    all_data = []
    for filename in filenames:
        all_data.append(unpickle(data_dir + '/' + filename))

    images = np.concatenate(all_data, axis=0)

    def get_epoch():
        if eval_bool:
            for i in xrange(len(images) / batch_size):
                yield np.copy(images[i*batch_size:(i+1)*batch_size])
        elif ratio == 1:
            np.random.shuffle(images);
            for i in xrange(len(images) / batch_size):
                yield np.copy(images[i*batch_size:(i+1)*batch_size]);
        else:
            index = np.arange(len(probability_array_01));
            probability_array_01 = softmax(probability_array);
            len_index = len(probability_array_01);
            index_ = np.random.choice(len_index, int(ratio*len_index), replace=False, p=probability_array_01);
            images_selected = images[index_];
            np.random.shuffle(images_selected)  ##not sure if this is needed...
            for i in xrange(len(images_selected) / batch_size):
                yield np.copy(images_selected[i*batch_size:(i+1)*batch_size])
    return get_epoch

def load(batch_size, data_dir, probability_array, ratio, eval_bool):
    return (
        cifar_generator(['data_batch_1','data_batch_2','data_batch_3','data_batch_4','data_batch_5'], batch_size, data_dir, probability_array, ratio, eval_bool), 
        cifar_generator(['test_batch'], batch_size, data_dir, probability_array, ratio, 1)
    )