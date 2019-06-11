import numpy as np

from ..util import BaseCase

import pygsti
import pygsti.construction.modelconstruction as mc


class ModelConstructionTester(BaseCase):
    def setUp(self):
        #OK for these tests, since we test user interface?
        #Set Model objects to "strict" mode for testing
        pygsti.objects.ExplicitOpModel._strict = False

    def test_build_basis_gateset(self):
        modelA = pygsti.construction.build_explicit_model(
            [('Q0',)], ['Gi', 'Gx', 'Gy'],
            ["I(Q0)", "X(pi/2,Q0)", "Y(pi/2,Q0)"]
        )
        modelB = pygsti.construction.basis_build_explicit_model(
            [('Q0',)], pygsti.Basis.cast('gm', 4),
            ['Gi', 'Gx', 'Gy'], ["I(Q0)", "X(pi/2,Q0)", "Y(pi/2,Q0)"]
        )
        self.assertAlmostEqual(modelA.frobeniusdist(modelB), 0)
        # TODO assert correctness

    def test_raises_on_bad_parameterization(self):
        with self.assertRaises(ValueError):
            mc.build_operation([(4, 4)], [('Q0', 'Q1')], "X(pi,Q0)", "gm", parameterization="FooBar")


class GateConstructionBase:
    def setUp(self):
        pygsti.objects.ExplicitOpModel._strict = False

    def _construct_gates(self, param):
        #CNOT gate
        Ucnot = np.array([[1, 0, 0, 0],
                          [0, 1, 0, 0],
                          [0, 0, 0, 1],
                          [0, 0, 1, 0]], 'd')
        cnotMx = pygsti.tools.unitary_to_process_mx(Ucnot)
        self.CNOT_chk = pygsti.tools.change_basis(cnotMx, "std", self.basis)

        #CPHASE gate
        Ucphase = np.array([[1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, -1]], 'd')
        cphaseMx = pygsti.tools.unitary_to_process_mx(Ucphase)
        self.CPHASE_chk = pygsti.tools.change_basis(cphaseMx, "std", self.basis)
        self.ident = mc.build_operation([(4,)], [('Q0',)], "I(Q0)", self.basis, param)
        self.rotXa = mc.build_operation([(4,)], [('Q0',)], "X(pi/2,Q0)", self.basis, param)
        self.rotX2 = mc.build_operation([(4,)], [('Q0',)], "X(pi,Q0)", self.basis, param)
        self.rotYa = mc.build_operation([(4,)], [('Q0',)], "Y(pi/2,Q0)", self.basis, param)
        self.rotZa = mc.build_operation([(4,)], [('Q0',)], "Z(pi/2,Q0)", self.basis, param)
        self.rotNa = mc.build_operation([(4,)], [('Q0',)], "N(pi/2,1.0,0.5,0,Q0)", self.basis, param)
        self.iwL = mc.build_operation([(4, 1)], [('Q0', 'L0')], "I(Q0)", self.basis, param)
        self.CnotA = mc.build_operation([(4, 4)], [('Q0', 'Q1')], "CX(pi,Q0,Q1)", self.basis, param)
        self.CY = mc.build_operation([(4, 4)], [('Q0', 'Q1')], "CY(pi,Q0,Q1)", self.basis, param)
        self.CZ = mc.build_operation([(4, 4)], [('Q0', 'Q1')], "CZ(pi,Q0,Q1)", self.basis, param)
        self.CNOT = mc.build_operation([(4, 4)], [('Q0', 'Q1')], "CNOT(Q0,Q1)", self.basis, param)
        self.CPHASE = mc.build_operation([(4, 4)], [('Q0', 'Q1')], "CPHASE(Q0,Q1)", self.basis, param)

    def test_construct_gates_static(self):
        self._construct_gates('static')

    def test_construct_gates_TP(self):
        self._construct_gates('TP')

    def test_construct_gates_full(self):
        self._construct_gates('full')

        self.leakA = mc.build_operation([(1,), (1,), (1,)], [('L0',), ('L1',), ('L2',)],
                                        "LX(pi,0,1)", self.basis, 'full')
        self.rotLeak = mc.build_operation([(4,), (1,)], [('Q0',), ('L0',)],
                                          "X(pi,Q0):LX(pi,0,2)", self.basis, 'full')
        self.leakB = mc.build_operation([(4,), (1,)], [('Q0',), ('L0',)], "LX(pi,0,2)", self.basis, 'full')
        self.rotXb = mc.build_operation([(4,), (1,), (1,)], [('Q0',), ('L0',), ('L1',)],
                                        "X(pi,Q0)", self.basis, 'full')
        self.CnotB = mc.build_operation([(4, 4), (1,)], [('Q0', 'Q1'), ('L0',)], "CX(pi,Q0,Q1)", self.basis, 'full')

    def _test_leakA(self):
        leakA_ans = np.array( [[ 0.,  1.,  0.],
                               [ 1.,  0.,  0.],
                               [ 0.,  0.,  1.]], 'd')
        self.assertArraysAlmostEqual(self.leakA, leakA_ans)

    def _test_rotXa(self):
        rotXa_ans = np.array([[ 1.,  0.,  0.,  0.],
                              [ 0.,  1.,  0.,  0.],
                              [ 0.,  0.,  0,  -1.],
                              [ 0.,  0.,  1.,  0]], 'd')
        self.assertArraysAlmostEqual(self.rotXa, rotXa_ans)

    def _test_rotX2(self):
        rotX2_ans = np.array([[ 1.,  0.,  0.,  0.],
                              [ 0.,  1.,  0.,  0.],
                              [ 0.,  0., -1.,  0.],
                              [ 0.,  0.,  0., -1.]], 'd')
        self.assertArraysAlmostEqual(self.rotX2, rotX2_ans)

    def _test_rotLeak(self):
        rotLeak_ans = np.array([[ 0.5,         0.,          0.,         -0.5,         0.70710678],
                                [ 0.,          0.,          0.,          0.,          0.        ],
                                [ 0.,          0.,          0.,          0.,          0.        ],
                                [ 0.5,         0.,          0.,         -0.5,        -0.70710678],
                                [ 0.70710678,  0.,          0.,          0.70710678,  0.        ]], 'd')
        self.assertArraysAlmostEqual(self.rotLeak, rotLeak_ans)

    def _test_leakB(self):
        leakB_ans = np.array(  [[ 0.5,         0.,          0.,         -0.5,         0.70710678],
                                [ 0.,          0.,          0.,          0.,          0.        ],
                                [ 0.,          0.,          0.,          0.,          0.        ],
                                [-0.5,         0.,          0.,          0.5,         0.70710678],
                                [ 0.70710678,  0.,          0.,          0.70710678,  0.        ]], 'd')
        self.assertArraysAlmostEqual(self.leakB, leakB_ans)

    def _test_rotXb(self):
        rotXb_ans = np.array( [[ 1.,  0.,  0.,  0.,  0.,  0.],
                               [ 0.,  1.,  0.,  0.,  0.,  0.],
                               [ 0.,  0., -1.,  0.,  0.,  0.],
                               [ 0.,  0.,  0., -1.,  0.,  0.],
                               [ 0.,  0.,  0.,  0.,  1.,  0.],
                               [ 0.,  0.,  0.,  0.,  0.,  1.]], 'd')
        self.assertArraysAlmostEqual(self.rotXb, rotXb_ans)

    def _test_CnotA(self):
        CnotA_ans = np.array( [[1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0],
                               [  0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0],
                               [  0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                               [  0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0]] )
        self.assertArraysAlmostEqual(self.CnotA, CnotA_ans)

    def _test_CnotB(self):
        CnotB_ans = np.array([[  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0, -1.0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0,    0,    0,    0],
                              [    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,  1.0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0],
                              [    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,  1.0]])
        self.assertArraysAlmostEqual(self.CnotB, CnotB_ans)

    def test_raises_on_bad_basis(self):
        with self.assertRaises(AssertionError):
            mc.build_operation([(4,)], [('Q0',)], "X(pi/2,Q0)", "FooBar", 'std')

    def test_raises_on_bad_gate_name(self):
        with self.assertRaises(ValueError):
            mc.build_operation([(4,)], [('Q0',)], "FooBar(Q0)", self.basis, 'std')

    def test_raises_on_bad_state_spec(self):
        with self.assertRaises(KeyError):
            mc.build_operation([(4,)], [('A0',)], "I(Q0)", self.basis, 'std')

    def test_raises_on_bad_label(self):
        with self.assertRaises(KeyError):
            mc.build_operation([(4,)], [('Q0', 'L0')], "I(Q0,A0)", self.basis, 'std')

    def test_raises_on_state_space_dim_mismatch(self):
        with self.assertRaises(TypeError):
            mc.build_operation([2], [('Q0',)], "I(Q0)", self.basis, 'std')

    def test_raises_on_qubit_state_space_mismatch(self):
        with self.assertRaises(ValueError):
            mc.build_operation([(4,), (4,)], [('Q0',), ('Q1',)], "CZ(pi,Q0,Q1)", self.basis, 'std')

    def test_raises_on_LX_with_bad_basis_spec(self):
        with self.assertRaises(AssertionError):
            mc.build_operation([(4,), (1,)], [('Q0',), ('L0',)], "LX(pi,0,2)", "foobar", 'std')


class PauliGateConstructionTester(GateConstructionBase, BaseCase):
    basis = 'pp'


class StdGateConstructionTester(GateConstructionBase, BaseCase):
    basis = 'std'

    def test_construct_gates_full(self):
        super().test_construct_gates_full()
        self._test_leakA()


class GellMannGateConstructionTester(GateConstructionBase, BaseCase):
    basis = 'gm'

    def test_construct_gates_TP(self):
        super().test_construct_gates_TP()
        self._test_rotXa()
        self._test_rotX2()

        self._test_CnotA()

    def test_construct_gates_static(self):
        super().test_construct_gates_static()
        self._test_rotXa()
        self._test_rotX2()

        self._test_CnotA()

    def test_construct_gates_full(self):
        super().test_construct_gates_full()
        self._test_leakA()
        self._test_rotXa()
        self._test_rotX2()

        self._test_rotLeak()
        self._test_leakB()
        self._test_rotXb()

        self._test_CnotA()
        self._test_CnotB()
