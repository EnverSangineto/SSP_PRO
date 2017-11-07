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
    return dict['data'], dict['labels']
##added by Dan ###
def softmax(x):
    """Compute softmax values for each sets of scores in x."""
    #e_x = np.exp(x - np.max(x));
    #return e_x / np.sum(e_x);
    theta = 0.0001;
    ps = np.exp(x * theta)
    return ps / np.sum(ps)

def cifar_generator(filenames, batch_size, data_dir, probability_array, ratio, eval_bool):
    all_data = []
    all_labels = []
    for filename in filenames:
        data, labels = unpickle(data_dir + '/' + filename)
        all_data.append(data)
        all_labels.append(labels)

    images = np.concatenate(all_data, axis=0)
    labels = np.concatenate(all_labels, axis=0)

    def get_epoch():
        if eval_bool:
            for i in xrange(len(images) / batch_size):
                yield (images[i*batch_size:(i+1)*batch_size], labels[i*batch_size:(i+1)*batch_size]);
        elif ratio == 1:
            rng_state = np.random.get_state()
            np.random.shuffle(images)
            np.random.set_state(rng_state)
            np.random.shuffle(labels)
            
            for i in xrange(len(images) / batch_size):
                yield (images[i*batch_size:(i+1)*batch_size], labels[i*batch_size:(i+1)*batch_size]);
        else:
            probability_array_01 = softmax(probability_array);
            len_index = len(probability_array_01);
            #print probability_array_01[0:50]
            size_generate = int(ratio*len_index);
            #non-determinstic
            #index_ = np.random.choice(len_index, size_generate, replace=False, p=probability_array_01);
            #determinstric
            index_ = np.argsort(probability_array_01)[::-1][0:size_generate];
            images_selected = images[index_];
            labels_selected = labels[index_];
            
            rng_state = np.random.get_state()
            np.random.shuffle(images_selected)  ##not sure if this is needed...
            np.random.set_state(rng_state)
            np.random.shuffle(labels_selected);
            
            for i in xrange(len(images_selected) / batch_size):
                yield (images_selected[i*batch_size:(i+1)*batch_size], labels_selected[i*batch_size:(i+1)*batch_size]);
    return get_epoch

def load(batch_size, data_dir, probability_array, ratio, eval_bool):
    return (
        cifar_generator(['data_batch_1','data_batch_2','data_batch_3','data_batch_4','data_batch_5'], batch_size, data_dir, probability_array, ratio, eval_bool), 
        cifar_generator(['test_batch'], batch_size, data_dir, probability_array, ratio, 1)
    )
