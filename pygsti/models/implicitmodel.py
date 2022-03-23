"""
Defines the ImplicitOpModel class and supporting functionality.
"""
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import collections as _collections
import itertools as _itertools
import uuid as _uuid
import numpy as _np

from pygsti.models import model as _mdl
from pygsti.modelmembers import operations as _op
from pygsti.modelmembers import povms as _povm
from pygsti.modelmembers.modelmembergraph import ModelMemberGraph as _MMGraph
from pygsti.baseobjs.label import Label as _Label

from pygsti.baseobjs.basis import Basis as _Basis, TensorProdBasis as _TensorProdBasis
from pygsti.baseobjs.statespace import StateSpace as _StateSpace
from pygsti.models.layerrules import LayerRules as _LayerRules
from pygsti.forwardsims.forwardsim import ForwardSimulator as _FSim


class ImplicitOpModel(_mdl.OpModel):
    """
    A model that stores the building blocks for layer operations and build circuit-layer operations on-demand.

    An ImplicitOpModel represents a flexible QIP model whereby only the
    building blocks for layer operations are stored, and custom layer-lizard
    logic is used to construct layer operations from these blocks on an
    on-demand basis.

    Parameters
    ----------
    state_space : StateSpace
        The state space for this model.

    layer_rules : LayerRules
        The "layer rules" used for constructing operators for circuit
        layers.  This functionality is essential to using this model to
        simulate ciruits, and is typically supplied by derived classes.

    basis : Basis
        The basis used for the state space by dense operator representations.

    simulator : ForwardSimulator or {"auto", "matrix", "map"}
        The circuit simulator used to compute any
        requested probabilities, e.g. from :method:`probs` or

    evotype : {"densitymx", "statevec", "stabilizer", "svterm", "cterm"}
        The evolution type of this model, describing how states are
        represented, allowing compatibility checks with (super)operator
        objects.
    """
    def __init__(self,
                 state_space,
                 layer_rules,
                 basis="pp",
                 simulator="auto",
                 evotype="densitymx"):
        self.prep_blks = _collections.OrderedDict()
        self.povm_blks = _collections.OrderedDict()
        self.operation_blks = _collections.OrderedDict()
        self.instrument_blks = _collections.OrderedDict()
        self.factories = _collections.OrderedDict()

        super(ImplicitOpModel, self).__init__(state_space, basis, evotype, layer_rules, simulator)

    @property
    def _primitive_prep_label_dict(self):
        return self.prep_blks['layers']

    @property
    def _primitive_povm_label_dict(self):
        return self.povm_blks['layers']

    @property
    def _primitive_op_label_dict(self):
        # don't include 'implied' ops as primitive ops -- FUTURE - maybe should include empty layer ([])?
        return _collections.OrderedDict([(k, None) for k in self.operation_blks['layers']
                                         if not (k.name.startswith('{') and k.name.endswith('}'))])

    @property
    def _primitive_instrument_label_dict(self):
        return self.instrument_blks['layers']

    #Functions required for base class functionality

    def _iter_parameterized_objs(self):
        for dictlbl, objdict in _itertools.chain(self.prep_blks.items(),
                                                 self.povm_blks.items(),
                                                 self.operation_blks.items(),
                                                 self.instrument_blks.items(),
                                                 self.factories.items()):
            for lbl, obj in objdict.items():
                yield (_Label(dictlbl + ":" + lbl.name, lbl.sslbls), obj)

    def _init_copy(self, copy_into, memo):
        """
        Copies any "tricky" member of this model into `copy_into`, before
        deep copying everything else within a .copy() operation.
        """
        # Copy special base class members first
        super(ImplicitOpModel, self)._init_copy(copy_into, memo)

        # Copy our "tricky" members
        copy_into.prep_blks = _collections.OrderedDict([(lbl, prepdict.copy(copy_into, memo))
                                                       for lbl, prepdict in self.prep_blks.items()])
        copy_into.povm_blks = _collections.OrderedDict([(lbl, povmdict.copy(copy_into, memo))
                                                       for lbl, povmdict in self.povm_blks.items()])
        copy_into.operation_blks = _collections.OrderedDict([(lbl, opdict.copy(copy_into, memo))
                                                            for lbl, opdict in self.operation_blks.items()])
        copy_into.instrument_blks = _collections.OrderedDict([(lbl, idict.copy(copy_into, memo))
                                                             for lbl, idict in self.instrument_blks.items()])
        copy_into.factories = _collections.OrderedDict([(lbl, fdict.copy(copy_into, memo))
                                                       for lbl, fdict in self.factories.items()])

        copy_into._state_space = self.state_space.copy()  # needed by simplifier helper

    def __setstate__(self, state_dict):
        super().__setstate__(state_dict)
        if 'uuid' not in state_dict:
            self.uuid = _uuid.uuid4()  # create a new uuid

        if 'factories' not in state_dict:
            self.factories = _collections.OrderedDict()  # backward compatibility (temporary)

        #Additionally, must re-connect this model as the parent
        # of relevant OrderedDict-derived classes, which *don't*
        # preserve this information upon pickling so as to avoid
        # circular pickling...
        for prepdict in self.prep_blks.values():
            prepdict.parent = self
            for o in prepdict.values(): o.relink_parent(self)
        for povmdict in self.povm_blks.values():
            povmdict.parent = self
            for o in povmdict.values(): o.relink_parent(self)
        for opdict in self.operation_blks.values():
            opdict.parent = self
            for o in opdict.values(): o.relink_parent(self)
        for idict in self.instrument_blks.values():
            idict.parent = self
            for o in idict.values(): o.relink_parent(self)
        for fdict in self.factories.values():
            fdict.parent = self
            for o in fdict.values(): o.relink_parent(self)

    def compute_clifford_symplectic_reps(self, oplabel_filter=None):
        """
        Constructs a dictionary of the symplectic representations for all the Clifford gates in this model.

        Non-:class:`StaticCliffordOp` gates will be ignored and their entries omitted
        from the returned dictionary.

        Parameters
        ----------
        oplabel_filter : iterable, optional
            A list, tuple, or set of operation labels whose symplectic
            representations should be returned (if they exist).

        Returns
        -------
        dict
            keys are operation labels and/or just the root names of gates
            (without any state space indices/labels).  Values are
            `(symplectic_matrix, phase_vector)` tuples.
        """
        gfilter = set(oplabel_filter) if oplabel_filter is not None \
            else None

        srep_dict = {}

        for gl in self.primitive_op_labels:
            gate = self.operation_blks['layers'][gl]
            if (gfilter is not None) and (gl not in gfilter): continue

            if isinstance(gate, _op.EmbeddedOp):
                assert(isinstance(gate.embedded_op, _op.StaticCliffordOp)), \
                    "EmbeddedClifforGate contains a non-StaticCliffordOp!"
                lbl = gl.name  # strip state space labels off since this is a
                # symplectic rep for the *embedded* gate
                srep = (gate.embedded_op.smatrix, gate.embedded_op.svector)
            elif isinstance(gate, _op.StaticCliffordOp):
                lbl = gl.name
                srep = (gate.smatrix, gate.svector)
            else:
                lbl = srep = None

            if srep:
                if lbl in srep_dict:
                    assert(srep == srep_dict[lbl]), \
                        "Inconsistent symplectic reps for %s label!" % lbl
                else:
                    srep_dict[lbl] = srep

        return srep_dict

    def __str__(self):
        s = ""
        for dictlbl, d in self.prep_blks.items():
            for lbl, vec in d.items():
                s += "%s:%s = " % (str(dictlbl), str(lbl)) + str(vec) + "\n"
        s += "\n"
        for dictlbl, d in self.povm_blks.items():
            for lbl, povm in d.items():
                s += "%s:%s = " % (str(dictlbl), str(lbl)) + str(povm) + "\n"
        s += "\n"
        for dictlbl, d in self.operation_blks.items():
            for lbl, gate in d.items():
                s += "%s:%s = \n" % (str(dictlbl), str(lbl)) + str(gate) + "\n\n"
        for dictlbl, d in self.instrument_blks.items():
            for lbl, inst in d.items():
                s += "%s:%s = " % (str(dictlbl), str(lbl)) + str(inst) + "\n"
        s += "\n"
        for dictlbl, d in self.factories.items():
            for lbl, factory in d.items():
                s += "%s:%s = " % (str(dictlbl), str(lbl)) + str(factory) + "\n"
        s += "\n"

        return s

    def _default_primitive_povm_layer_lbl(self, sslbls):
        """
        Gets the default POVM label.

        This is often used when a circuit  is specified without an ending POVM layer.
        Returns `None` if there is no default and one *must* be specified.

        Parameters
        ----------
        sslbls : tuple or None
            The state space labels being measured, and for which a default POVM is desired.

        Returns
        -------
        Label or None
        """
        if len(self.primitive_povm_labels) == 1:
            povm_name = next(iter(self.primitive_povm_labels)).name
            if (self.state_space.num_tensor_product_blocks == 1
                and (self.state_space.tensor_product_block_labels(0) == sslbls
                     or sslbls == ('*',))):
                return _Label(povm_name)  # because sslbls == all of model's sslbls
            else:
                return _Label(povm_name, sslbls)
        else:
            return None

    def _effect_labels_for_povm(self, povm_lbl):
        """
        Gets the effect labels corresponding to the possible outcomes of POVM label `povm_lbl`.

        Parameters
        ----------
        povm_lbl : Label
            POVM label.

        Returns
        -------
        list
            A list of strings which label the POVM outcomes.
        """
        for povmdict in self.povm_blks.values():
            if povm_lbl in povmdict:
                return tuple(povmdict[povm_lbl].keys())
            if isinstance(povm_lbl, _Label) and povm_lbl.name in povmdict:
                return tuple(_povm.MarginalizedPOVM(povmdict[povm_lbl.name],
                                                    self.state_space, povm_lbl.sslbls).keys())

        raise KeyError("No POVM labeled %s!" % str(povm_lbl))

    def _member_labels_for_instrument(self, inst_lbl):
        """
        Gets the member labels corresponding to the possible outcomes of the instrument labeled by `inst_lbl`.

        Parameters
        ----------
        inst_lbl : Label
            Instrument label.

        Returns
        -------
        list
            A list of strings which label the instrument members.
        """
        for idict in self.instrument_blks.values():
            if inst_lbl in idict:
                return tuple(idict[inst_lbl].keys())
        raise KeyError("No instrument labeled %s!" % inst_lbl)

    def _reinit_opcaches(self):
        self._opcaches.clear()

        # Add expanded instrument and POVM operations to cache so these are accessible to circuit calcs
        simplified_effect_blks = _collections.OrderedDict()
        for povm_dict_lbl, povmdict in self.povm_blks.items():
            simplified_effect_blks['povm-' + povm_dict_lbl] = _collections.OrderedDict(
                [(k, e) for povm_lbl, povm in povmdict.items()
                 for k, e in povm.simplify_effects(povm_lbl).items()])

        simplified_op_blks = _collections.OrderedDict()
        for op_dict_lbl in self.operation_blks:
            simplified_op_blks['op-' + op_dict_lbl] = {}  # create *empty* caches corresponding to op categories
        for inst_dict_lbl, instdict in self.instrument_blks.items():
            if 'op-' + inst_dict_lbl not in simplified_op_blks:  # only create when needed
                simplified_op_blks['op-' + inst_dict_lbl] = _collections.OrderedDict()
            for inst_lbl, inst in instdict.items():
                for k, g in inst.simplify_operations(inst_lbl).items():
                    simplified_op_blks['op-' + inst_dict_lbl][k] = g

        #FUTURE: allow cache "cateogories"?  Now we just flatten the work we did above:
        self._opcaches.update(simplified_effect_blks)
        self._opcaches.update(simplified_op_blks)
        self._opcaches['complete-layers'] = {}  # used to hold final layers (of any type) if needed

    def create_modelmember_graph(self):
        self._clean_paramvec()  # Rebuild params to ensure accurate comparisons with MMGraphs

        root_dicts = {
            'prep_blks': self.prep_blks,
            'povm_blks': self.povm_blks,
            'operation_blks': self.operation_blks,
            'instrument_blks': self.instrument_blks,
            'factories': self.factories,
        }
        mm_dicts = {(root_str + "|" + k): mm_dict
                    for root_str, root_dict in root_dicts.items()
                    for k, mm_dict in root_dict.items()}
        return _MMGraph(mm_dicts)

    def _to_nice_serialization(self):
        state = super()._to_nice_serialization()
        state.update({'basis': self.basis.to_nice_serialization(),
                      'evotype': str(self.evotype),  # TODO or serialize?
                      'layer_rules': self._layer_rules.to_nice_serialization(),
                      'simulator': self.sim.to_nice_serialization()
                      })

        mmgraph = self.create_modelmember_graph()
        state['modelmembers'] = mmgraph.create_serialization_dict()
        return state

    @classmethod
    def _from_nice_serialization(cls, state):
        state_space = _StateSpace.from_nice_serialization(state['state_space'])
        layer_rules = _LayerRules.from_nice_serialization(state['layer_rules'])
        basis = _Basis.from_nice_serialization(state['basis'])
        modelmembers = _MMGraph.load_modelmembers_from_serialization_dict(state['modelmembers'])
        simulator = _FSim.from_nice_serialization(state['simulator'])

        mdl = cls(state_space, layer_rules, basis, simulator, state['evotype'])

        root_dicts = {
            'prep_blks': mdl.prep_blks,
            'povm_blks': mdl.povm_blks,
            'operation_blks': mdl.operation_blks,
            'instrument_blks': mdl.instrument_blks,
            'factories': mdl.factories,
        }
        for mm_key, mm_dict in modelmembers.items():
            root_key, sub_key = mm_key.split('|')
            root_dicts[root_key][sub_key].update(mm_dict)  # Note: sub_keys should already be created
        return mdl

    def errorgen_coefficients(self, normalized_elem_gens=True):
        """TODO: docstring - returns a nested dict containing all the error generator coefficients for all
           the operations in this model. """
        if not normalized_elem_gens:
            def rescale(coeffs):
                """ HACK: rescales errorgen coefficients for normalized-Pauli-basis elementary error gens
                         to be coefficients for the usual un-normalied-Pauli-basis elementary gens.  This
                         is only needed in the Hamiltonian case, as the non-ham "elementary" gen has a
                         factor of d2 baked into it.
                """
                d2 = _np.sqrt(self.dim); d = _np.sqrt(d2)
                return {lbl: (val / d if lbl.errorgen_type == 'H' else val) for lbl, val in coeffs.items()}

            op_coeffs = {op_label: rescale(self.operation_blks['layers'][op_label].errorgen_coefficients())
                         for op_label in self.operation_blks['layers']}
            op_coeffs.update({prep_label: rescale(self.prep_blks['layers'][prep_label].errorgen_coefficients())
                              for prep_label in self.prep_blks['layers']})
            op_coeffs.update({povm_label: rescale(self.povm_blks['layers'][povm_label].errorgen_coefficients())
                              for povm_label in self.povm_blks['layers']})
        else:
            op_coeffs = {op_label: self.operation_blks['layers'][op_label].errorgen_coefficients()
                         for op_label in self.operation_blks['layers']}
            op_coeffs.update({prep_label: self.prep_blks['layers'][prep_label].errorgen_coefficients()
                              for prep_label in self.prep_blks['layers']})
            op_coeffs.update({povm_label: self.povm_blks['layers'][povm_label].errorgen_coefficients()
                              for povm_label in self.povm_blks['layers']})

        return op_coeffs

    def _add_reparameterization(self, primitive_op_labels, fogi_dirs, errgenset_space_labels):
        raise NotImplementedError("TODO: need to implement this for implicit model FOGI parameterization to work!")

    def setup_fogi(self, initial_gauge_basis, create_complete_basis_fn=None,
                   op_label_abbrevs=None, reparameterize=False, reduce_to_model_space=True,
                   dependent_fogi_action='drop', include_spam=True):

        from pygsti.baseobjs.errorgenbasis import CompleteElementaryErrorgenBasis as _CompleteElementaryErrorgenBasis
        from pygsti.baseobjs.errorgenbasis import ExplicitElementaryErrorgenBasis as _ExplicitElementaryErrorgenBasis
        from pygsti.baseobjs.errorgenspace import ErrorgenSpace as _ErrorgenSpace
        import scipy.sparse as _sps

        from pygsti.tools import basistools as _bt
        from pygsti.tools import fogitools as _fogit
        from pygsti.models.fogistore import FirstOrderGaugeInvariantStore as _FOGIStore

        # ExplicitOpModel-specific - and assumes model's ops have specific structure (see extract_std_target*) !!
        primitive_op_labels = self.primitive_op_labels

        primitive_prep_labels = self.primitive_prep_labels if include_spam else []
        primitive_povm_labels = self.primitive_povm_labels if include_spam else []

        # "initial" gauge space is the space of error generators initially considered as
        # gauge transformations.  It can be reduced by the errors allowed on operations (by
        # their type and support).

        def extract_std_target_mx(op, op_basis):
            # TODO: more general decomposition of op - here it must be Composed(UnitaryOp, ExpErrorGen)
            #       or just ExpErrorGen
            if isinstance(op, _op.ExpErrorgenOp):  # assume just an identity op
                U = _np.identity(op.state_space.dim, 'd')
            elif isinstance(op, _op.ComposedOp):  # assume first element gives unitary
                op_mx = op.factorops[0].to_dense()  # assumes a LindbladOp and low num qubits
                nQubits = int(round(_np.log(op_mx.shape[0]) / _np.log(4))); assert(op_mx.shape[0] == 4**nQubits)
                tensorprod_std_basis = _Basis.cast('std', [(4,) * nQubits])
                U = _bt.change_basis(op_mx, op_basis, tensorprod_std_basis)  # 'std' is incorrect
            else:
                raise ValueError("Could not extract target matrix from %s op!" % str(type(op)))
            return U

        def extract_std_target_vec(v):
            #TODO - make more sophisticated...
            dim = v.state_space.dim
            nQubits = int(round(_np.log(dim) / _np.log(4))); assert(dim == 4**nQubits)
            tensorprod_std_basis = _Basis.cast('std', [(4,) * nQubits])
            v = _bt.change_basis(v.to_dense(), self.basis, tensorprod_std_basis)  # 'std' is incorrect
            return v

        if create_complete_basis_fn is None:
            assert(isinstance(initial_gauge_basis, _CompleteElementaryErrorgenBasis)), \
                ("Must supply a custom `create_complete_basis_fn` if initial gauge basis is not a complete basis!")

            def create_complete_basis_fn(target_sslbls):
                return initial_gauge_basis  #.create_subbasis(target_sslbls, retain_max_weights=False)

        # get gauge action matrices on the initial space
        gauge_action_matrices = _collections.OrderedDict()
        gauge_action_gauge_spaces = _collections.OrderedDict()
        errorgen_coefficient_labels = _collections.OrderedDict()  # by operation
        for op_label in primitive_op_labels:  # Note: "ga" stands for "gauge action" in variable names below
            print("DB FOGI: ",op_label)
            if hasattr(self.operation_blks['layers'][op_label], 'embedded_op'):
                op = self.operation_blks['layers'][op_label].embedded_op
                target_lbls = self.operation_blks['layers'][op_label].target_labels
            else:  # then assume gate is on *all* qubits
                op = self.operation_blks['layers'][op_label]
                target_lbls = self.state_space.sole_tensor_product_block_labels
            assert(self.state_space.num_tensor_product_blocks == 1)  # so that all_sslbls is correct below
            all_sslbls = self.state_space.sole_tensor_product_block_labels
            op_component_bases = [self.basis.component_bases[all_sslbls.index(lbl)] for lbl in target_lbls]
            op_basis = _TensorProdBasis(op_component_bases)
            U = extract_std_target_mx(op, op_basis)

            # below: special logic for, e.g., 2Q explicit models with 2Q gate matched with Gx:0 label
            target_sslbls = op_label.sslbls if (op_label.sslbls is not None and U.shape[0] < self.state_space.dim) \
                else self.state_space.sole_tensor_product_block_labels
            op_gauge_basis = initial_gauge_basis.create_subbasis(target_sslbls)  # gauge space lbls that overlap target
            # Note: can assume gauge action is zero (U acts as identity) on all basis elements not in op_gauge_basis

            initial_row_basis = create_complete_basis_fn(target_sslbls)

            #support_sslbls, gauge_errgen_basis = get_overlapping_labels(gauge_errgen_space_labels, target_sslbls)
            #FOGI DEBUG print("DEBUG -- ", op_label)
            mx, row_basis = _fogit.first_order_gauge_action_matrix(U, target_sslbls, self.state_space,
                                                                   op_gauge_basis, initial_row_basis)
            print("DB FOGI: action mx: ", mx.shape)
            #FOGI DEBUG print("DEBUG => mx is ", mx.shape)
            # Note: mx is a sparse lil matrix
            # mx cols => op_gauge_basis, mx rows => row_basis, as zero rows have already been removed
            # (DONE: - remove all all-zero rows from mx (and corresponding basis labels) )
            # Note: row_basis is a simple subset of initial_row_basis

            allowed_rowspace_mx, allowed_row_basis, op_gauge_space = \
                self._format_gauge_action_matrix(mx, op, reduce_to_model_space, row_basis, op_gauge_basis,
                                                 create_complete_basis_fn)
            print("DB FOGI: action matrix formatting done")

            errorgen_coefficient_labels[op_label] = allowed_row_basis.labels
            gauge_action_matrices[op_label] = allowed_rowspace_mx
            gauge_action_gauge_spaces[op_label] = op_gauge_space
            #FOGI DEBUG print("DEBUG => final allowed_rowspace_mx shape =", allowed_rowspace_mx.shape)

        # Similar for SPAM
        for prep_label in primitive_prep_labels:
            prep = self.preps[prep_label]
            v = extract_std_target_vec(prep)
            target_sslbls = prep_label.sslbls if (prep_label.sslbls is not None and v.shape[0] < self.state_space.dim) \
                else self.state_space.sole_tensor_product_block_labels
            op_gauge_basis = initial_gauge_basis.create_subbasis(target_sslbls)  # gauge space lbls that overlap target
            initial_row_basis = create_complete_basis_fn(target_sslbls)

            mx, row_basis = _fogit.first_order_gauge_action_matrix_for_prep(v, target_sslbls, self.state_space,
                                                                            op_gauge_basis, initial_row_basis)

            allowed_rowspace_mx, allowed_row_basis, op_gauge_space = \
                self._format_gauge_action_matrix(mx, prep, reduce_to_model_space, row_basis, op_gauge_basis,
                                                 create_complete_basis_fn)

            errorgen_coefficient_labels[prep_label] = allowed_row_basis.labels
            gauge_action_matrices[prep_label] = allowed_rowspace_mx
            gauge_action_gauge_spaces[prep_label] = op_gauge_space

        for povm_label in primitive_povm_labels:
            povm = self.povms[povm_label]
            vecs = [extract_std_target_vec(effect) for effect in povm.values()]
            target_sslbls = povm_label.sslbls if (povm_label.sslbls is not None
                                                  and vecs[0].shape[0] < self.state_space.dim) \
                else self.state_space.sole_tensor_product_block_labels
            op_gauge_basis = initial_gauge_basis.create_subbasis(target_sslbls)  # gauge space lbls that overlap target
            initial_row_basis = create_complete_basis_fn(target_sslbls)

            mx, row_basis = _fogit.first_order_gauge_action_matrix_for_povm(vecs, target_sslbls, self.state_space,
                                                                            op_gauge_basis, initial_row_basis)

            allowed_rowspace_mx, allowed_row_basis, op_gauge_space = \
                self._format_gauge_action_matrix(mx, povm, reduce_to_model_space, row_basis, op_gauge_basis,
                                                 create_complete_basis_fn)

            errorgen_coefficient_labels[povm_label] = allowed_row_basis.labels
            gauge_action_matrices[povm_label] = allowed_rowspace_mx
            gauge_action_gauge_spaces[povm_label] = op_gauge_space

        norm_order = "auto"  # NOTE - should be 1 for normalizing 'S' quantities and 2 for 'H',
        # so 'auto' utilizes intelligence within FOGIStore
        self.fogi_store = _FOGIStore(gauge_action_matrices, gauge_action_gauge_spaces,
                                     errorgen_coefficient_labels,  # gauge_errgen_space_labels,
                                     op_label_abbrevs, reduce_to_model_space, dependent_fogi_action,
                                     norm_order=norm_order)

        if reparameterize:
            self.param_interposer = self._add_reparameterization(
                primitive_op_labels + primitive_prep_labels + primitive_povm_labels,
                self.fogi_store.fogi_directions.toarray(),  # DENSE now (leave sparse in FUTURE?)
                self.fogi_store.errorgen_space_op_elem_labels)


def _init_spam_layers(model, prep_layers, povm_layers):
    """ Helper function for initializing the .prep_blks and .povm_blks elements of an implicit model"""
    # SPAM (same as for cloud noise model)
    if prep_layers is None:
        pass  # no prep layers
    elif isinstance(prep_layers, dict):
        for rhoname, layerop in prep_layers.items():
            model.prep_blks['layers'][_Label(rhoname)] = layerop
    elif isinstance(prep_layers, _op.LinearOperator):  # just a single layer op
        model.prep_blks['layers'][_Label('rho0')] = prep_layers
    else:  # assume prep_layers is an iterable of layers, e.g. isinstance(prep_layers, (list,tuple)):
        for i, layerop in enumerate(prep_layers):
            model.prep_blks['layers'][_Label("rho%d" % i)] = layerop

    if povm_layers is None:
        pass  # no povms
    elif isinstance(povm_layers, _povm.POVM):  # just a single povm - must precede 'dict' test!
        model.povm_blks['layers'][_Label('Mdefault')] = povm_layers
    elif isinstance(povm_layers, dict):
        for povmname, layerop in povm_layers.items():
            model.povm_blks['layers'][_Label(povmname)] = layerop
    else:  # assume povm_layers is an iterable of layers, e.g. isinstance(povm_layers, (list,tuple)):
        for i, layerop in enumerate(povm_layers):
            model.povm_blks['layers'][_Label("M%d" % i)] = layerop
