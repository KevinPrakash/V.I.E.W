import os
import cv2
import json
import heapq
import chainer
import numpy as np
import chainer.functions as F

from copy import deepcopy
from ResNet50 import ResNet
from chainer import serializers
from Image2CaptionDecoder import Image2CaptionDecoder

'''
Chainer is a lightweight framework used to load the RNN and CNN model
ResNet50 is the CNN model definition
Image2CaptionDecoder is the RNN model definition
'''


class CaptionGenerator(object):
    def __init__(self,rnn_model_place,cnn_model_place,dictionary_place,beamsize=3,depth_limit=50,first_word="<sos>",hidden_dim=512,mean="imagenet"):
        # Loads the dictionary File
        self.beamsize=beamsize
        self.depth_limit=depth_limit
        self.index2token=self.parse_dic(dictionary_place)
        
        # Loads the resnet 50 CNN model
        self.cnn_model=ResNet()
        serializers.load_hdf5(cnn_model_place, self.cnn_model)

        #Loads the RNN model
        self.rnn_model=Image2CaptionDecoder(len(self.token2index),hidden_dim=hidden_dim)
        if len(rnn_model_place) > 0:
            serializers.load_hdf5(rnn_model_place, self.rnn_model)
            
        self.first_word=first_word
        
        # Used for normalizing the image
        mean_image = np.ndarray((3, 224, 224), dtype=np.float32)
        mean_image[0] = 103.939
        mean_image[1] = 116.779
        mean_image[2] = 123.68
        self.mean_image = mean_image

    def parse_dic(self,dictionary_place):
        with open(dictionary_place, 'r') as f:
            json_file = json.load(f)
        if len(json_file) < 10:
            self.token2index = { word['word']:word['idx'] for word in json_file["words"]}
        else:
            self.token2index = json_file

        return {v:k for k,v in self.token2index.items()}

    def successor(self,current_state):
        '''
        Args:
            current_state: a stete, python tuple (hx,cx,path,cost)
                hidden: hidden states of LSTM
                cell: cell states LSTM
                path: word indicies so far as a python list  e.g. initial is self.token2index["<sos>"]
                cost: negative log likelihood

        Returns:
            k_best_next_states: a python list whose length is the beam size. possible_sentences[i] = {"indicies": list of word indices,"cost":negative log likelihood so far}

        '''
        word=[np.array([current_state["path"][-1]],dtype=np.int32)]
        hx=current_state["hidden"]
        cx=current_state["cell"]
        hy, cy, next_words=self.rnn_model(hx,cx,word)

        word_dist=F.softmax(next_words[0]).data[0]
        k_best_next_sentences=[]
        for i in range(self.beamsize):
            next_word_idx=int(np.argmax(word_dist))
            k_best_next_sentences.append(\
                {\
                "hidden":hy,\
                "cell":cy,\
                "path":deepcopy(current_state["path"])+[next_word_idx],\
                "cost":current_state["cost"]-np.log(word_dist[next_word_idx])
                }\
                )
            word_dist[next_word_idx]=0

        return hy, cy, k_best_next_sentences

    def beam_search(self,initial_state):
        '''
        Beam search is a graph search algorithm

        Args:
            initial state: an initial stete, python tuple (hx,cx,path,cost)
            each state has 
                hx: hidden states
                cx: cell states
                path: word indicies so far as a python list  e.g. initial is self.token2index["<sos>"]
                cost: negative log likelihood

        Returns:
            captions sorted by the cost (i.e. negative log llikelihood)
        '''
        found_paths=[]
        top_k_states=[initial_state]
        while (len(found_paths) < self.beamsize):
            new_top_k_states=[]
            for state in top_k_states:
                hy, cy, k_best_next_states = self.successor(state)
                for next_state in k_best_next_states:
                    new_top_k_states.append(next_state)
            selected_top_k_states=heapq.nsmallest(self.beamsize, new_top_k_states, key=lambda x : x["cost"])

            top_k_states=[]
            for state in selected_top_k_states:
                if state["path"][-1] == self.token2index["<eos>"] or len(state["path"])==self.depth_limit:
                    found_paths.append(state)
                else:
                    top_k_states.append(state)

        return sorted(found_paths, key=lambda x: x["cost"]) 

    def generate(self,image_cam):
        '''
        Args:
            The image that is supposed to be resized
        Output:
            The image in a CNN ready format
        '''
        img = self.resize(image_cam)
        return self.generate_from_img(img)


    def generate_from_img_feature(self,image_feature):
        batch_size=1
        hx=np.zeros((self.rnn_model.n_layers, batch_size, self.rnn_model.hidden_dim), dtype=np.float32)
        cx=np.zeros((self.rnn_model.n_layers, batch_size, self.rnn_model.hidden_dim), dtype=np.float32)
        
        hy,cy = self.rnn_model.input_cnn_feature(hx,cx,image_feature)

        initial_state={\
                    "hidden":hy,\
                    "cell":cy,\
                    "path":[self.token2index[self.first_word]],\
                    "cost":0,\
                }\

        captions=self.beam_search(initial_state)

        caption_candidates=[]
        
        for caption in captions:
            sentence= [self.index2token[word_idx] for word_idx in caption["path"]]
            log_likelihood = -float(caption["cost"])
            caption_candidates.append({"sentence":sentence,"log_likelihood":log_likelihood})

        return caption_candidates

    def generate_from_img(self,image_array):
        '''Generate Caption for an Numpy Image array
        
        Args:
            image that is to be supplied to the CNN , can be given in a array format

        Returns:
            list of generated captions, sorted by the likelihood
        '''
        # The image is sent to the CNN model and the features are extracted
        image_feature=self.cnn_model(image_array, "feature").data.reshape(1,1,2048)
        # This feature list is passed to the RNN model which creates the sentences
        return self.generate_from_img_feature(image_feature)


    def resize(self,image,image_w=224,image_h=224):
        '''
        Args:
            Given image as numpy array and the required output size
        Returns:
            An image in format that is expected by the CNN that is cropped to the specified size done by using interpolation to maintain aspect ratio and then cropped to required size.
        '''
        h, w ,c = image.shape
        # Finding the largest side of the image to compress
        if w > h:
            shape = (image_w * w // h, image_h)
        else:
            shape = (image_w, image_h * h // w)
        x = (shape[0] - image_w) // 2
        y = (shape[1] - image_h) // 2
        # Compressing using CV2 library
        pixels = cv2.resize(image,shape,interpolation=cv2.INTER_AREA).astype(np.float32)
        # Cropping to the required size
        pixels = pixels[y:y + image_h, x:x + image_w,:]
        # Converting to format as required by the CNN
        pixels = pixels[:,:,::-1].transpose(2,0,1)
        pixels -= self.mean_image
        return pixels.reshape((1,) + pixels.shape)

