import os,sys
import tensorflow as tf
import numpy as np
sys.path.insert(0, './scripts')
sys.path.insert(0, './models')
import nn_utils as utils
import validation
from tqdm import tqdm
import measurements as measure
import csv
# from sklearn.metrics import roc_curve, auc
# from tensorflow.contrib.learn.python.learn.datasets import base

### Variable Initialization
import argparse
parser = argparse.ArgumentParser(description="To train speaker verification network using voxceleb1", add_help=True)
parser.add_argument("--numgpus", type=int, default=1,help="source data")
parser.add_argument("--print_eer_interval", type=int, default=2000, help="target data")
parser.add_argument("--print_loss_interval", type=int, default=2000, help="target data")
parser.add_argument("--print_train_acc_interval", type=int, default=2000, help="target data")
parser.add_argument("--max_save_limit", type=int, default=500, help="target data")
parser.add_argument("--tfrecords_dir", type=str, default='./data/tfrecords', help="target data")
parser.add_argument("--save_dir", type=str, default='./saver', help="target data")
parser.add_argument("--save_interval", type=int, default=16000, help="target data")

parser.add_argument("--model_name", type=str, help="target data")
parser.add_argument("--learning_rate", type=float, default='0.0001', help="target data")
parser.add_argument("--input_dim", type=int, default=40, help="target data")
parser.add_argument("--mini_batch", type=int, default=16, help="target data")
parser.add_argument("--feat_type", type=str, default='mfcc_win400_hop160_fixed298', help="target data")
parser.add_argument("--train_data", type=str, default='voxceleb1_dev', help="target data")
parser.add_argument("--train_total_split", type=int, default=100, help="target data")
# parser.add_argument("--validation_data", type=str, default='voxceleb1_test', help="target data")
# parser.add_argument("--validation_total_split", type=int, default=1, help="target data")
parser.add_argument("--test_data", type=str, default='voxceleb1_test', help="target data")
parser.add_argument("--test_trials", type=str, default='voxceleb1_trials/voxceleb1_trials_sv', help="target data")
parser.add_argument("--test_total_split", type=int, default=1, help="target data")
parser.add_argument("--softmax_num", type=int, default=1211, help="target data")
parser.add_argument("--resume_startpoint", type=int, default=0, help="0 if you don't have to resume")
parser.add_argument("--max_iteration", type=int, default=800000, help="target data")
parser.add_argument("--fixed_input_frame", type=int, default=298, help="target data")
parser.add_argument("--optimizer", type=str, default='adam', help="sgd,rms or adam")
parser.add_argument("--cnn1d", type=str, default='True', help="sgd,rms or adam")
parser.add_argument("--data_root", type=str, default='data/', help="default data folder")

#scopes
parser.add_argument("--main_scope", type=str, default='resnet_v2_softmax', help="main variable scope")
parser.add_argument("--embedding_scope", type=str, default='fc2', help="Finetuning scope")

#for fine-tuning
parser.add_argument("--pretrain_model_name", type=str, help="Finetuning switch")
parser.add_argument("--pretrain_startpoint", type=int, default=48000, help="Finetuning startpoint")
parser.add_argument("--pretrain_scope", type=str, default='resnet_v2_softmax', help="Finetuning scope")
parser.add_argument("--update_scope", type=str, default='resnet_v2_softmax', help="Finetuning scope")

#for random sub-sampling
parser.add_argument("--subsample_min", type=int, default=0, help="minimum length for random sub-sampling")
parser.add_argument("--subsample_max", type=int, default=0, help="maximum length for random sub-sampling")

#for momentum optimizer
parser.add_argument("--momentum", type=float, default=0.9, help="momentum factor")
parser.add_argument("--decay_epoch", type=int, default=5, help="decay scheduling")
parser.add_argument("--decay_factor", type=float, default=0.1, help="decay factor")

args = parser.parse_known_args()[0]
print args

args.cnn1d = utils.str2bool(args.cnn1d)


NUMGPUS = args.numgpus
SAVE_INTERVAL = args.save_interval
LOSS_INTERVAL = args.print_loss_interval
MAX_SAVEFILE_LIMIT = args.max_save_limit
EERTEST_INTERVAL = args.print_eer_interval
TESTSET_INTERVAL = args.print_train_acc_interval
TFRECORDS_FOLDER = args.tfrecords_dir
# SAVER_FOLDERNAME = args.save_dir
NN_MODEL = args.model_name

LEARNING_RATE = args.learning_rate
INPUT_DIM = args.input_dim
BATCHSIZE = args.mini_batch
FEAT_TYPE = args.feat_type
DATA_NAME = args.train_data
TOTAL_SPLIT = args.train_total_split
TEST_TOTAL_SPLIT = args.test_total_split
SOFTMAX_NUM = args.softmax_num
RESUME_STARTPOINT = args.resume_startpoint
MAX_ITER = args.max_iteration
TEST_SET_NAME = args.test_data
INPUT_LENGTH = args.fixed_input_frame # in frame
PRETRAIN_STARTPOINT = args.pretrain_startpoint
EMBEDDING_SCOPE=args.embedding_scope
MOMENTUM=args.momentum

if args.subsample_min ==0:
    MINIMUM_LENTH = INPUT_LENGTH-1
else:
    MINIMUM_LENTH = args.subsample_min

if args.subsample_max ==0:
    MAXIMUM_LENGTH = INPUT_LENGTH
else:
    MAXIMUM_LENGTH = args.subsample_max


resume = False
if RESUME_STARTPOINT > 0:
    resume = True

SAVER_FOLDERNAME = args.save_dir+'/' + NN_MODEL+'_'+str(INPUT_LENGTH)+'frame_'+FEAT_TYPE
if args.pretrain_model_name:
    PRETRAIN_SAVER_FOLDERNAME = args.save_dir+'/' + args.pretrain_model_name+'_'+str(INPUT_LENGTH)+'frame_'+FEAT_TYPE

nn_model = __import__(NN_MODEL)

records_shuffle_list = []
for i in range(1,TOTAL_SPLIT+1):
    records_shuffle_list.append(TFRECORDS_FOLDER+'/'+DATA_NAME+'_'+FEAT_TYPE+'.'+str(i)+'.tfrecords')


labels,shapes,feats = utils.read_and_decode_tfrecords_fixed(records_shuffle_list,int(INPUT_LENGTH),int(INPUT_DIM),args.cnn1d)
labels_batch,feats_batch,shapes_batch = tf.train.shuffle_batch([labels, feats,shapes],
                                                               batch_size=BATCHSIZE,
                                                               allow_smaller_final_batch=False,
                                                               capacity=50000,
                                                               num_threads=4,
                                                               min_after_dequeue=10000)

#data for validation
FEAT_TYPE = FEAT_TYPE.split('_exshort')[0]
FEAT_TYPE = FEAT_TYPE.split('_fixed')[0]
records_test_list = []
for i in range(1,TEST_TOTAL_SPLIT+1):
    records_test_list.append(TFRECORDS_FOLDER+'/'+TEST_SET_NAME+'_'+FEAT_TYPE+'.'+str(i)+'.tfrecords')

vali_labels, vali_shapes, vali_feats = utils.read_and_decode_tfrecords_variable(records_test_list,args.cnn1d)
vali_set = validation.validation_set(args)


with tf.device('/cpu:0'):
    global_step = tf.Variable(0, trainable=False)

    if args.optimizer=='adam':
        opt = tf.train.AdamOptimizer(LEARNING_RATE)
    elif args.optimizer=='rms':
        opt = tf.train.RMSPropOptimizer(LEARNING_RATE)
    elif args.optimizer=='sgd':
        learning_rate = tf.train.exponential_decay(LEARNING_RATE, global_step, 50000, 0.98, staircase=True)
        opt = tf.train.GradientDescentOptimizer(learning_rate)
    elif args.optimizer=='momentum':
        num_train_samples = len( open('data/'+args.train_data+'/wav.scp','r').readlines() )
        decay_step = int( num_train_samples * args.decay_epoch / args.mini_batch )
        learning_rate = tf.train.exponential_decay(LEARNING_RATE, global_step, decay_step, args.decay_factor, staircase=True)
#         learning_rate = tf.train.exponential_decay(LEARNING_RATE, global_step, 50000, 0.1, staircase=True)
        opt = tf.train.MomentumOptimizer(learning_rate, MOMENTUM, use_nesterov=False,name='momentum')
    else:
        print "Error: Wrong optimizer"
        quit()

    emnet_losses = []
    emnet_grads = []


    if args.cnn1d: # for 1-d CNN input
        feat_batch = tf.placeholder(tf.float32, [None,None,np.int(INPUT_DIM)],name="feat_batch")
    else: # for 2-d CNN input
        feat_batch = tf.placeholder(tf.float32, [None,None,np.int(INPUT_DIM),1],name="feat_batch")
    label_batch = tf.placeholder(tf.int32, [None],name="label_batch")


    #Define NN graph
    with tf.variable_scope(tf.get_variable_scope()):
        for i in range(NUMGPUS):
            with tf.device('/gpu:%d' % i):
                emnet = nn_model.nn(feat_batch,
                                              label_batch,
                                              num_classes = SOFTMAX_NUM,
                                              is_training = True,
                                              global_pool = True,
                                              output_stride = None,
                                              reuse = tf.AUTO_REUSE,
                                              scope = args.main_scope)
                if args.pretrain_model_name:
                    ams_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES)
                    #In case to update the last layer only
                    # ams_vars = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES,scope='resnet_v2_softmax/AM_logits')
                    grads = opt.compute_gradients(emnet.loss,var_list=ams_vars)
                else:
                    grads = opt.compute_gradients(emnet.loss)
                emnet_losses.append(emnet.loss)
                emnet_grads.append(grads)

        with tf.device('/gpu:0'):
            emnet_validation = nn_model.nn(feat_batch,
                                             label_batch,
                                             num_classes = SOFTMAX_NUM,
                                             is_training = False,
                                             global_pool = True,
                                             output_stride = None,
                                             reuse = tf.AUTO_REUSE,
                                             scope = args.main_scope)

    loss = tf.reduce_mean(emnet_losses)
    grads = utils.average_gradients(emnet_grads)
    update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
    apply_gradient_op = opt.apply_gradients(grads, global_step=global_step)

    #Open new session
    sess = tf.InteractiveSession()
    saver = tf.train.Saver(max_to_keep=MAX_SAVEFILE_LIMIT)

    #To load pre-trained model
    if args.pretrain_model_name:
        pretrain_vars = []
        for i in total_vars:
            if len(i.name.split('AM_logits'))<2:
                pretrain_vars.append(i)
        #     pretrain_vars = tf.get_collection(tf.GraphKeys.VARIABLES)
        pretrain_saver = tf.train.Saver(var_list=pretrain_vars)


    #Variable initialization
    tf.initialize_all_variables().run()
    tf.train.start_queue_runners(sess=sess)
    if args.optimizer=='adam':
        learning_rate = (opt._lr_t * tf.sqrt(1 - opt._beta2_t) / (1 - opt._beta1_t))
    elif args.optimizer=='rms':
        learning_rate = tf.train.exponential_decay(LEARNING_RATE, global_step, 50000, 0.98, staircase=True)

    #load feature from test set
    vali_set.load_feature(sess, vali_labels, vali_shapes, vali_feats)

    ### Training neural network
    if resume:
        saver.restore(sess,SAVER_FOLDERNAME+'/model'+str(RESUME_STARTPOINT)+'.ckpt-'+str(RESUME_STARTPOINT))

    if args.pretrain_model_name:
        pretrain_saver.restore(sess,PRETRAIN_SAVER_FOLDERNAME+'/model'+str(PRETRAIN_STARTPOINT)+'.ckpt-'+str(PRETRAIN_STARTPOINT))

    for step in range(RESUME_STARTPOINT,MAX_ITER):

        #Do random sub-sampling on each minibatches
        feats,labels,_ = sess.run([feats_batch,labels_batch,shapes_batch])
        new_input_length = np.random.randint(MINIMUM_LENTH,MAXIMUM_LENGTH)
        new_input_start = np.random.randint(0,INPUT_LENGTH-new_input_length-1)
        if args.cnn1d: # for 1-d CNN input (batch,feat_length,feat_dim)
            feats = feats[:,new_input_start:new_input_start+new_input_length,:]
        else: # for 2-d CNN input (batch,feat_length,feat_dim,1(channel))
            feats = feats[:,new_input_start:new_input_start+new_input_length,:,:]


        #feed input and update NN
        _, _,loss_v,mean_loss = sess.run([apply_gradient_op, update_ops, emnet.loss,loss], feed_dict={
            feat_batch:feats,
            label_batch:labels
        })


        if np.isnan(loss_v):
            print ('Model diverged with loss = NAN')
            quit()

        if step % EERTEST_INTERVAL ==0 and step>=RESUME_STARTPOINT:
            vali_set.get_scores(emnet_validation, feat_batch, label_batch)
            #calculate EER
            EER = measure.calculate_eer(vali_set.scores, vali_set.tst_trials)
            norm_EER = measure.calculate_eer(vali_set.norm_scores, vali_set.tst_trials)
            print ('Step %d: loss %.3f, lr : %.5f, EER : %f (norm: %f)' % (step,mean_loss, sess.run(learning_rate),EER,norm_EER))

        if step % TESTSET_INTERVAL ==0 and step >=RESUME_STARTPOINT:
            a,b,c = sess.run([feats_batch,labels_batch,shapes_batch])
            prediction,_label= sess.run([emnet_validation.end_points['predictions'], emnet_validation.label] , feed_dict={
                feat_batch:a,
                label_batch:b
            })
            spklab_num_mat = np.eye(SOFTMAX_NUM)[_label]
            acc = utils.accuracy(prediction, spklab_num_mat)
            print ('Step %d: loss %.3f, lr : %.5f, Accuracy : %f' % (step,mean_loss, sess.run(learning_rate),acc))

        if step % LOSS_INTERVAL ==0:
            print ('Step %d: loss %.3f, lr : %.5f' % (step, mean_loss, sess.run(learning_rate)))

        if step % SAVE_INTERVAL == 0 and step >=RESUME_STARTPOINT:
            saver.save(sess, SAVER_FOLDERNAME+'/model'+str(step)+'.ckpt',global_step=step)
