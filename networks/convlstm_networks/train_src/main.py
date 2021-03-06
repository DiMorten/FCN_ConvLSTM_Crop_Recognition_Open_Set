from colorama import init
init()
from keras.layers import Input, Dense, Conv2D, MaxPool2D, Flatten, Dropout, Conv2DTranspose
# from keras.callbacks import ModelCheckpoint , EarlyStopping
from keras.optimizers import Adam,Adagrad 
from keras.models import Model
from keras import backend as K
import keras

import numpy as np
from sklearn.utils import shuffle
import cv2
import argparse
import tensorflow as tf

from keras.models import *
from keras.layers import *
from keras.optimizers import *
from keras import metrics
import sys
import glob

from sklearn.metrics import confusion_matrix,f1_score,accuracy_score,classification_report
# Local
from densnet import DenseNetFCN
from densnet_timedistributed import DenseNetFCNTimeDistributed

#from metrics import fmeasure,categorical_accuracy
import deb
from keras_weighted_categorical_crossentropy import weighted_categorical_crossentropy, sparse_accuracy_ignoring_last_label, weighted_categorical_crossentropy_ignoring_last_label, categorical_focal_ignoring_last_label, weighted_categorical_focal_ignoring_last_label
from keras.models import load_model
from keras.layers import ConvLSTM2D, UpSampling2D, multiply
from keras.utils.vis_utils import plot_model
from keras.regularizers import l1,l2
import time
import pickle
#from keras_self_attention import SeqSelfAttention
import pdb
import pathlib
from pathlib import Path, PureWindowsPath
from keras.layers import Conv3DTranspose, Conv3D

from keras.callbacks import EarlyStopping
import tensorflow as tf
from collections import Counter


#from datagenerator import DataGenerator
from generator import DataGenerator, DataGeneratorWithCoords, DataGeneratorWithCoordsPatches

import matplotlib.pyplot as plt
sys.path.append('../../../dataset/dataset/patches_extract_script/')
from dataSource import DataSource, SARSource, OpticalSource, Dataset, LEM, LEM2, CampoVerde, OpticalSourceWithClouds, Humidity
from model_input_mode import MIMFixed, MIMVarLabel, MIMVarSeqLabel, MIMVarLabel_PaddedSeq, MIMFixedLabelAllLabels, MIMFixed_PaddedSeq
from parameters.parameters_reader import ParamsTrain

from icecream import ic
from monitor import Monitor, MonitorNPY, MonitorGenerator, MonitorNPYAndGenerator
import natsort
from model import NetModel, ModelFit, ModelLoadGenerator, ModelLoadGeneratorDebug, ModelLoadGeneratorWithCoords, ModelLoadEachBatch
from dataset import Dataset, DatasetWithCoords

from patch_extractor import PatchExtractor
ic.configureOutput(includeContext=False)
np.random.seed(2021)
tf.set_random_seed(2021)


paramsTrain = ParamsTrain('parameters/')
#paramsTrain.seq_mode = 'var_label'

#paramsTrain.seq_mode = 'var_label'
paramsTrain.seq_mode = 'fixed'


if paramsTrain.seq_mode == 'var_label':
	#paramsTrain.mim = MIMVarLabel()
	paramsTrain.mim = MIMVarLabel_PaddedSeq()
elif paramsTrain.seq_mode == 'var':
	paramsTrain.mim = MIMVarSeqLabel()
elif paramsTrain.seq_mode == 'fixed_label_len':
	paramsTrain.mim = MIMVarLabel()
	paramsTrain.mim =MIMFixedLabelAllLabels()
else:
	#paramsTrain.mim = MIMFixed()
	paramsTrain.mim = MIMFixed_PaddedSeq()

deb.prints(paramsTrain.seq_mode)
deb.prints(paramsTrain.mim)

dataset = paramsTrain.dataset

#paramsTrain.known_classes = [0, 1, 10, 12] # soybean, maize, cerrado, soil



#paramsTrain = Params(parameters_path)


#========= overwrite for direct execution of this py file
direct_execution=False
if direct_execution==True:
	paramsTrain.stop_epoch=-1

	#dataset='cv'
	dataset='cv'

	#sensor_source='Optical'
	#sensor_source='OpticalWithClouds'
	sensor_source='SAR'

	if dataset=='cv':
		paramsTrain.class_n=12
		paramsTrain.path="../../../dataset/dataset/cv_data/"
		if sensor_source=='SAR':
			paramsTrain.t_len=14
			
	elif dataset=='lm':
		paramsTrain.path="../../../dataset/dataset/lm_data/"
		
		paramsTrain.class_n=15
		if sensor_source=='SAR':
			paramsTrain.channel_n=2
			paramsTrain.t_len=13
		elif sensor_source=='Optical':
			paramsTrain.channel_n=3
			paramsTrain.t_len=11
		elif sensor_source=='OpticalWithClouds':
			paramsTrain.channel_n=3
			paramsTrain.t_len=13

	paramsTrain.model_type='BUnet4ConvLSTM'
	#paramsTrain.model_type='ConvLSTM_seq2seq'
	#paramsTrain.model_type='ConvLSTM_seq2seq_bi'
	#paramsTrain.model_type='DenseNetTimeDistributed_128x2'
	#paramsTrain.model_type='BAtrousGAPConvLSTM'
	#paramsTrain.model_type='Unet3D'
	#paramsTrain.model_type='BUnet6ConvLSTM'
	#paramsTrain.model_type='BUnet4ConvLSTM_SkipLSTM'


def model_summary_print(s):
	with open('model_summary.txt','w+') as f:
		print(s, file=f)


def txt_append(filename, append_text):
	with open(filename, "a") as myfile:
		myfile.write(append_text)

def sizeof_fmt(num, suffix='B'):
    ''' by Fred Cirera,  https://stackoverflow.com/a/1094933/1870254, modified'''
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f %s%s" % (num, 'Yi', suffix)
# ========== NetModel object implements model graph definition, train/testing, early stopping ================ #

flag = {"data_create": 2, "label_one_hot": True}

class TrainTest():

	def __init__(self, paramsTrain):
		self.paramsTrain = paramsTrain

		
		if self.paramsTrain.dataset=='lm':
			self.ds=LEM(self.paramsTrain.seq_mode, self.paramsTrain.seq_date, self.paramsTrain.seq_len)
		elif self.paramsTrain.dataset=='l2':
			self.ds=LEM2(self.paramsTrain.seq_mode, self.paramsTrain.seq_date, self.paramsTrain.seq_len)
		elif self.paramsTrain.dataset=='cv':
			self.ds=CampoVerde(self.paramsTrain.seq_mode, self.paramsTrain.seq_date, self.paramsTrain.seq_len)

		deb.prints(self.ds)
		
		self.ds.addDataSource(paramsTrain.dataSource)

		dotys, dotys_sin_cos = self.ds.getDayOfTheYear()

		self.paramsTrain.t_len = self.ds.t_len # modified?
		self.paramsTrain.dotys_sin_cos = dotys_sin_cos
		self.dotys_sin_cos = dotys_sin_cos

	def trainAndEvaluate(self, model_name_id):
		
		self.model_name = model_name_id
		ic(self.model_name)
		if self.paramsTrain.sliceFromCoords == False:
			datasetClass = Dataset
		else:
			datasetClass = DatasetWithCoords
		data = datasetClass(paramsTrain = self.paramsTrain, ds = self.ds,
			dotys_sin_cos = self.dotys_sin_cos)

		data.create_load()
		
		self.paramsTrain.class_n = data.class_n
		ic(self.paramsTrain.class_n)

		adam = Adam(lr=self.paramsTrain.learning_rate, beta_1=0.9)
		
		#model = ModelLoadEachBatch(epochs=self.paramsTrain.epochs, patch_len=self.paramsTrain.patch_len,
	##	modelClass = NetModel
	##	modelClass = ModelFit
	##	modelClass = ModelLoadGenerator
		if self.paramsTrain.sliceFromCoords == False:
			#modelClass = NetModel
	#		modelClass = ModelFit
			modelClass = ModelLoadGenerator
	#		modelClass = ModelLoadGeneratorDebug
		else:
			modelClass = ModelLoadGeneratorWithCoords


		model = modelClass(paramsTrain = self.paramsTrain, ds = self.ds, 
						) # , data = data

		model.name = self.model_name
		
		model.class_n=data.class_n-1 # Model is designed without background class
		deb.prints(data.class_n)
		model.build()


		model.class_n+=1 # This is used in loss_weights_estimate, val_set_get, semantic_balance (To-do: Eliminate bcknd class)

		print("=== SELECT VALIDATION SET FROM TRAIN SET")
			
		#val_set = False # fix this
		if self.paramsTrain.val_set==True:
			deb.prints(self.paramsTrain.val_set_mode)
			data.val_set_get(self.paramsTrain.val_set_mode,0.15)
		else:
			data.patches['val']={}

			data.patches['val']['label']=np.zeros((1,1))
			data.patches['val']['in']=np.zeros((1,1))
			
			deb.prints(data.patches['val']['label'].shape)
			
		#balancing=False
		
		if self.paramsTrain.balancing==True:
			print("=== AUGMENTING TRAINING DATA")

			if self.paramsTrain.seq_mode=='fixed' or self.paramsTrain.seq_mode=='fixed_label_len':
				label_type = 'Nto1'
			elif self.paramsTrain.seq_mode=='var' or self.paramsTrain.seq_mode=='var_label':	
				label_type = 'NtoN'
			deb.prints(label_type)
			print("Before balancing:")

			data.semantic_balance(self.paramsTrain.samples_per_class,label_type = label_type) #More for known classes few. Compare with 500 later
						
		model.class_n-=1

		# Label background from 0 to last. 
		deb.prints(data.patches['train']['coords'].shape)

		#=========== End of moving bcknd label from 0 to last value

		metrics=['accuracy']

		#loss=weighted_categorical_crossentropy_ignoring_last_label(model.loss_weights_ones)
		loss=categorical_focal_ignoring_last_label(alpha=0.25,gamma=2)
		#loss=weighted_categorical_focal_ignoring_last_label(model.loss_weights,alpha=0.25,gamma=2)


	#	self.paramsTrain.model_load=False
		if self.paramsTrain.model_load:
			
			self.model_name = 'model_best_fit2.h5'
			self.model_name = 'model_lm_mar_nomask_good.h5'
			self.model_name = 'model_lm_jun_maize_nomask_good.h5'
			self.model_name = 'model_lm_jun_maize_nomask_good.h5'
			self.model_name = 'model_best_UUnet4ConvLSTM_jun.h5'
			self.model_name = 'model_cv_may_3classes_nomask.h5'
			self.model_name = 'model_best_fit2.h5'
			self.model_name = 'model_lm_mar_nomask_good.h5'
#			self.model_name = 'model_best_UUnet4ConvLSTM_jun_cv_criteria_0_92.h5'
			model.graph=load_model(self.model_name, compile=False)		

		else:
			model.graph.compile(loss=loss,
						optimizer=adam, metrics=metrics)

			model.train(data)
		
		model.evaluate(data)

if __name__ == '__main__':
	paramsTrain.dataSource = SARSource()

	trainTest = TrainTest(paramsTrain)

	patchExtractor = PatchExtractor(paramsTrain, trainTest.ds)	
	if paramsTrain.getFullIms == True:
		patchExtractor.getFullIms()	
	else:
		patchExtractor.fullImsLoad()

	if paramsTrain.coordsExtract == True:
		patchExtractor.extract()


	model_name_id = 'model_best_' + paramsTrain.model_type + '_' + \
			paramsTrain.seq_date + '_' + paramsTrain.dataset + '_' + \
			paramsTrain.model_name + '.h5'

	if paramsTrain.train == True:
		trainTest.trainAndEvaluate(model_name_id)
		