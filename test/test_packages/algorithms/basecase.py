import unittest
import pygsti
from pygsti.construction import std1Q_XYI as std
from pygsti.baseobjs import Basis

import numpy as np
from scipy import polyfit
import sys, os

from ..testutils import BaseTestCase, compare_files, temp_files

class AlgorithmsBase(BaseTestCase):
    def setUp(self):        
        super(AlgorithmsBase, self).setUp()

        self.model = std.target_model()
        self.datagen_gateset = self.model.depolarize(op_noise=0.05, spam_noise=0.1)

        self.fiducials = std.fiducials
        self.germs = std.germs
        #OLD self.specs = pygsti.construction.build_spam_specs(self.fiducials, effect_labels=['E0']) #only use the first EVec

        self.opLabels = list(self.model.operations.keys()) # also == std.gates
        self.lgstStrings = pygsti.construction.list_lgst_circuits(self.fiducials, self.fiducials, self.opLabels)

        self.maxLengthList = [0,1,2,4,8]

        self.elgstStrings = pygsti.construction.make_elgst_lists(
            self.opLabels, self.germs, self.maxLengthList )

        self.lsgstStrings = pygsti.construction.make_lsgst_lists(
            self.opLabels, self.fiducials, self.fiducials, self.germs, self.maxLengthList )

        ## RUN BELOW LINES to create analysis dataset (SAVE)
        if os.environ.get('PYGSTI_REGEN_REF_FILES','no').lower() in ("yes","1","true","v2"): # "v2" to only gen version-dep files
            expList = pygsti.construction.make_lsgst_experiment_list(
                self.opLabels, self.fiducials, self.fiducials, self.germs, self.maxLengthList )
            ds = pygsti.construction.generate_fake_data(self.datagen_gateset, expList,
                                                        nSamples=10000, sampleError='binomial', seed=100)
            ds.save(compare_files + "/analysis.dataset%s" % self.versionsuffix)

        self.ds = pygsti.objects.DataSet(fileToLoadFrom=compare_files + "/analysis.dataset%s" % self.versionsuffix)

        ## RUN BELOW LINES to create LGST analysis dataset (SAVE)
        if os.environ.get('PYGSTI_REGEN_REF_FILES','no').lower() in ("yes","1","true","v2"): # "v2" to only gen version-dep files
            ds_lgst = pygsti.construction.generate_fake_data(self.datagen_gateset, self.lgstStrings,
                                                             nSamples=10000,sampleError='binomial', seed=100)
            ds_lgst.save(compare_files + "/analysis_lgst.dataset%s" % self.versionsuffix)
        
        self.ds_lgst = pygsti.objects.DataSet(fileToLoadFrom=compare_files + "/analysis_lgst.dataset%s" % self.versionsuffix)
