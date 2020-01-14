# Speaker ID NETwork (SIDNET) Tool
This repository provides SIDNET Tool for the speaker verification task.

# Tutorial (on Voxceleb1)
First, you need to download dataset and clone this repository. Then run

    ./run.sh
Note that this tutorial does not use any speech or audio data other than voxceleb1 data for benchmark purpose. Hence, there is no noise augmentation on the training data.

A brief features of the training scheme is below

    Used Log-mel filterbanks (40 dimension) as input of the NN (512 fft, 400 samples per window, 160 samples stride)
    Cepstral mean normalization on log-mel filterbanks
    Voice Activity Detection with simple power threshold
    All training speech was subsampled between 2~4 seconds randomly
    Optimized with SGD (start from 0.005 learning rate)+Momentum (with factor of 0.9)
    Learning rate decay by 1/10 on every 5 epoch
    Mini-batch size = 16
    speaker embedding dimension = 512
    Training took roughly 12 hours on Titan X Pascal (training set has roughly 200h)


# Performance evaluation on Voxceleb1 test benchmark test (EER)

    5 layer CNN + Softmax: 7.06%
    5 layer CNN + Additive Margin Softmax (AMS) : 6.16%
    Resnet-50 + Softmax : 7.33%
    Resnet-50 + AMS :6.10%
    REsnet-50 + AMS + attentive pooling : 5.73

# Requirements (for example training code and baseline code)
    Python 2.7
    tensorflow (python library, tested on 1.14)
    librosa (python library, tested on 0.6.0)