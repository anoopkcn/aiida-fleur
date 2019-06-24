# -*- coding: utf-8 -*-
###############################################################################
# Copyright (c), Forschungszentrum Jülich GmbH, IAS-1/PGI-1, Germany.         #
#                All rights reserved.                                         #
# This file is part of the AiiDA-FLEUR package.                               #
#                                                                             #
# The code is hosted on GitHub at https://github.com/JuDFTteam/aiida-fleur    #
# For further information on the license, see the LICENSE.txt file            #
# For further information please visit http://www.flapw.de or                 #
# http://aiida-fleur.readthedocs.io/en/develop/                               #
###############################################################################

"""
    In this module you find the workflow 'FleurSSDispWorkChain' for the calculation of
    spin spiral dispersion using scalar-relatevistic Hamiltonian.
"""

from __future__ import absolute_import
import copy

import six
from six.moves import range
from lxml.etree import XMLSyntaxError

from aiida.engine import WorkChain, ToContext
from aiida.engine import calcfunction as cf
from aiida.plugins import DataFactory
from aiida.orm import Code, load_node
from aiida.common.exceptions import NotExistent

from aiida_fleur.tools.common_fleur_wf import test_and_get_codenode
from aiida_fleur.tools.common_fleur_wf import get_inputs_fleur
from aiida_fleur.workflows.scf import FleurScfWorkChain
from aiida_fleur.data.fleurinpmodifier import FleurinpModifier
from aiida_fleur.workflows.base_fleur import FleurBaseWorkChain

StructureData = DataFactory('structure')
RemoteData = DataFactory('remote')
Dict = DataFactory('dict')
FleurInpData = DataFactory('fleur.fleurinp')

class FleurSSDispWorkChain(WorkChain):
    """
    This workflow calculates spin spiral dispersion of a structure.
    """

    _workflowversion = "0.1.0"

    _default_options = {
        'resources' : {"num_machines": 1, "num_mpiprocs_per_machine" : 1},
        'max_wallclock_seconds' : 2*60*60,
        'queue_name' : '',
        'custom_scheduler_commands' : '',
        'import_sys_environment' : False,
        'environment_variables' : {}
        }

    _wf_default = {
        'fleur_runmax': 10,
        'density_converged' : 0.00005,
        'serial' : False,
        'itmax_per_run' : 30,
        'beta' : 0.000,
        'alpha_mix' : 0.015,
        'prop_dir' : [1.0, 0.0, 0.0],
        'q_vectors': ['0.0 0.0 0.0',
                      '0.125 0.0 0.0',
                      '0.250 0.0 0.0',
                      '0.375 0.0 0.0'],
        'ref_qss' : '0.0 0.0 0.0',
        'inpxml_changes' : []
        }

    _scf_keys = ['fleur_runmax', 'density_converged', 'serial', 'itmax_per_run', 'inpxml_changes']

    @classmethod
    def define(cls, spec):
        super(FleurSSDispWorkChain, cls).define(spec)
        spec.input("wf_parameters", valid_type=Dict, required=False,
                   default=Dict(dict=cls._wf_default))
        spec.input("structure", valid_type=StructureData, required=False)
        spec.input("calc_parameters", valid_type=Dict, required=False)
        spec.input("inpgen", valid_type=Code, required=False)
        spec.input("fleur", valid_type=Code, required=True)
        spec.input("remote", valid_type=RemoteData, required=False)
        spec.input("fleurinp", valid_type=FleurInpData, required=False)
        spec.input("options", valid_type=Dict, required=False,
                   default=Dict(dict=cls._default_options))

        spec.outline(
            cls.start,
            cls.converge_scf,
            cls.force_sp_sp,
            cls.get_results,
            cls.return_results
        )

        spec.output('out', valid_type=Dict)

        #exit codes
        spec.exit_code(301, 'ERROR_INVALID_INPUT_RESOURCES',
                       message="Invalid input, plaese check input configuration.")
        spec.exit_code(302, 'ERROR_INVALID_INPUT_RESOURCES_UNDERSPECIFIED',
                       message="Some required inputs are missing.")
        spec.exit_code(303, 'ERROR_INVALID_CODE_PROVIDED',
                       message="Invalid code node specified, check inpgen and fleur code nodes.")
        spec.exit_code(304, 'ERROR_INPGEN_CALCULATION_FAILED',
                       message="Inpgen calculation failed.")
        spec.exit_code(305, 'ERROR_CHANGING_FLEURINPUT_FAILED',
                       message="Input file modification failed.")
        spec.exit_code(306, 'ERROR_CALCULATION_INVALID_INPUT_FILE',
                       message="Input file is corrupted after user's modifications.")
        spec.exit_code(307, 'ERROR_FLEUR_CALCULATION_FALIED',
                       message="Fleur calculation failed.")
        spec.exit_code(308, 'ERROR_CONVERGENCE_NOT_ARCHIVED',
                       message="SCF cycle did not lead to convergence.")
        spec.exit_code(309, 'ERROR_REFERENCE_CALCULATION_FAILED',
                       message="Reference calculation failed.")
        spec.exit_code(310, 'ERROR_REFERENCE_CALCULATION_NOREMOTE',
                       message="Found no reference calculation remote repository.")
        spec.exit_code(311, 'ERROR_FORCE_THEOREM_FAILED',
                       message="Force theorem calculation failed.")
        spec.exit_code(333, 'ERROR_NOT_OPTIMAL_RESOURSES',
                       message="Computational resourses are not optimal.")

    def start(self):
        """
        Retrieve and initialize paramters of the WorkChain
        """
        self.report('INFO: started Spin Stiffness calculation workflow version {}\n'
                    ''.format(self._workflowversion))
        self.ctx.info = []
        self.ctx.warnings = []
        self.ctx.errors = []
        self.ctx.energy_dict = []

        # initialize the dictionary using defaults if no wf paramters are given
        wf_default = self._wf_default
        if 'wf_parameters' in self.inputs:
            wf_dict = self.inputs.wf_parameters.get_dict()
        else:
            wf_dict = wf_default

        # extend wf parameters given by user using defaults
        for key, val in six.iteritems(wf_default):
            wf_dict[key] = wf_dict.get(key, val)
        self.ctx.wf_dict = wf_dict

        if wf_dict['ref_qss'] != wf_dict['q_vectors'][0]:
            error = ("The first q_vector of the forceTheorem step has to be equal to"
                     "the q vector of the reference calculation.")
            self.control_end_wc(error)
            return self.exit_codes.ERROR_INVALID_INPUT_RESOURCES

        # set up mixing parameter alpha
        self.ctx.wf_dict['inpxml_changes'].append(
            ('set_inpchanges', {'change_dict': {'alpha': self.ctx.wf_dict['alpha_mix']}}))

        # initialize the dictionary using defaults if no options are given
        defaultoptions = self._default_options
        if 'options' in self.inputs:
            options = self.inputs.options.get_dict()
        else:
            options = defaultoptions

        # extend options given by user using defaults
        for key, val in six.iteritems(defaultoptions):
            options[key] = options.get(key, val)
        self.ctx.options = options

        # Check if user gave valid inpgen and fleur execulatbles
        inputs = self.inputs
        if 'inpgen' in inputs:
            try:
                test_and_get_codenode(inputs.inpgen, 'fleur.inpgen', use_exceptions=True)
            except ValueError:
                error = ("The code you provided for inpgen of FLEUR does not "
                         "use the plugin fleur.inpgen")
                self.control_end_wc(error)
                return self.exit_codes.ERROR_INVALID_CODE_PROVIDED

        if 'fleur' in inputs:
            try:
                test_and_get_codenode(inputs.fleur, 'fleur.fleur', use_exceptions=True)
            except ValueError:
                error = ("The code you provided for FLEUR does not "
                         "use the plugin fleur.fleur")
                self.control_end_wc(error)
                return self.exit_codes.ERROR_INVALID_CODE_PROVIDED

    def converge_scf(self):
        """
        Converge charge density for collinear case which is a reference for futher
        spin spiral calculations.
        """
        inputs = self.get_inputs_scf()
        res = self.submit(FleurScfWorkChain, **inputs)
        return ToContext(reference=res)

    def get_inputs_scf(self):
        """
        Initialize inputs for the scf cycle
        """
        inputs = self.inputs
        input_scf = {}

        scf_wf_param = {}
        for key in self._scf_keys:
            scf_wf_param[key] = self.ctx.wf_dict.get(key)

        input_scf['wf_parameters'] = copy.deepcopy(scf_wf_param)
        input_scf['wf_parameters']['mode'] = 'density'

        # set up q vector for the reference calculation
        list_ref_qss = [float(x) for x in self.ctx.wf_dict['ref_qss'].split()]
        if [x for x in list_ref_qss if x != 0]:
            changes_dict = {'qss' : self.ctx.wf_dict['ref_qss'],
                            'l_noco': True,
                            'ctail': False,
                            'l_ss': True}
        else:
            changes_dict = {'qss' : ' 0.0 0.0 0.0 ',
                            'l_noco': False,
                            'ctail': True,
                            'l_ss': False}

        input_scf['wf_parameters']['inpxml_changes'].append(
            (u'set_inpchanges', {u'change_dict': changes_dict}))
        input_scf['wf_parameters'] = Dict(dict=input_scf['wf_parameters'])

        input_scf['options'] = self.ctx.options
        input_scf['options'] = Dict(dict=input_scf['options'])

        input_scf['fleur'] = self.inputs.fleur

        if 'fluerinp' in inputs:
            input_scf['fleurinp'] = inputs.fleurinp
            if 'remote' in inputs:
                input_scf['remote_data'] = inputs.remote
        elif 'remote' in inputs:
            input_scf['remote_data'] = inputs.remote
        elif 'structure' in inputs:
            input_scf['structure'] = inputs.structure
            input_scf['inpgen'] = inputs.inpgen
            if 'calc_parameters' in inputs:
                input_scf['calc_parameters'] = inputs.calc_parameters.get_dict()
            else:
                input_scf['calc_parameters'] = {}
            input_scf['calc_parameters']['qss'] = {'x': self.ctx.wf_dict['prop_dir'][0],
                                                   'y': self.ctx.wf_dict['prop_dir'][1],
                                                   'z': self.ctx.wf_dict['prop_dir'][2]}
            input_scf['calc_parameters'] = Dict(dict=input_scf['calc_parameters'])
        return input_scf

    def change_fleurinp(self):
        """
        This routine sets somethings in the fleurinp file before running a fleur
        calculation.
        """
        self.report('INFO: run change_fleurinp')
        try:
            fleurin = self.ctx.reference.outputs.fleurinp
        except NotExistent:
            error = 'Fleurinp generated in the reference claculation is not found.'
            self.control_end_wc(error)
            return self.exit_codes.ERROR_REFERENCE_CALCULATION_FAILED

        #copy inpchanges from wf parameters
        fchanges = self.ctx.wf_dict.get('inpxml_changes', [])
        #create forceTheorem tags
        fchanges.extend([('create_tag', ('/fleurInput', 'forceTheorem')),
                         ('create_tag', ('/fleurInput/forceTheorem', 'spinSpiralDispersion'))])

        for i, vectors in enumerate(self.ctx.wf_dict['q_vectors']):
            fchanges.append(('create_tag', ('/fleurInput/forceTheorem/spinSpiralDispersion', 'q')))
            #next change requires a q-vector vectors, create flag False and a position of the <q>
            fchanges.append(('xml_set_text_occ',
                             ('/fleurInput/forceTheorem/spinSpiralDispersion/q', vectors, False, i)))

        changes_dict = {'itmax' : 1,
                        'l_noco': True,
                        'ctail': False,
                        'l_ss': True}
        fchanges.append((u'set_inpchanges', {u'change_dict' : changes_dict}))

        #change beta parameter in all AtomGroups
        fchanges.append(('set_atomgr_att',
                         ({'nocoParams': [('beta', self.ctx.wf_dict.get('beta'))]}, False, 'all')))

        if fchanges:# change inp.xml file
            fleurmode = FleurinpModifier(fleurin)
            avail_ac_dict = fleurmode.get_avail_actions()

            # apply further user dependend changes
            for change in fchanges:
                function = change[0]
                para = change[1]
                method = avail_ac_dict.get(function, None)
                if not method:
                    error = ("ERROR: Input 'inpxml_changes', function {} "
                             "is not known to fleurinpmodifier class, "
                             "plaese check/test your input. I abort..."
                             "".format(method))
                    self.control_end_wc(error)
                    return self.exit_codes.ERROR_CHANGING_FLEURINPUT_FAILED

                else:# apply change
                    if function == 'set_inpchanges':
                        method(**para)
                    else:
                        method(*para)

            # validate?
            apply_c = True
            try:
                fleurmode.show(display=False, validate=True)
            except XMLSyntaxError:
                error = ('ERROR: input, user wanted inp.xml changes did not validate')
                #fleurmode.show(display=True)#, validate=True)
                self.control_end_wc(error)
                apply_c = False
                return self.exit_codes.ERROR_CALCULATION_INVALID_INPUT_FILE

            # apply
            if apply_c:
                out = fleurmode.freeze()
                self.ctx.fleurinp = out
            return
        else: # otherwise do not change the inp.xml
            self.ctx.fleurinp = fleurin
            return

    def force_sp_sp(self):
        '''
        This routine uses the force theorem to calculate energies dispersion of
        spin spirals. The force theorem calculations implemented into the FLEUR
        code. Hence a single iteration FLEUR input file having <forceTheorem> tag
        has to be created and submitted.
        '''
        calc = self.ctx.reference

        if not calc.is_finished_ok:
            message = ('The reference SCF calculation was not successful.')
            self.control_end_wc(message)
            return self.exit_codes.ERROR_REFERENCE_CALCULATION_FAILED

        try:
            outpara_node = calc.outputs.output_scf_wc_para
        except NotExistent:
            message = ('The reference SCF calculation failed, no scf output node.')
            self.control_end_wc(message)
            return self.exit_codes.ERROR_REFERENCE_CALCULATION_FAILED

        outpara = outpara_node.get_dict()

        try:
            t_e = outpara['total_energy']
        except KeyError:
            message = ('Did not manage to extract float total energy from the'
                       ' reference SCF calculation.')
            self.control_end_wc(message)
            return self.exit_codes.ERROR_REFERENCE_CALCULATION_FAILED

        self.report('INFO: run Force theorem calculations')

        status = self.change_fleurinp()
        if status:
            return status

        fleurin = self.ctx.fleurinp

        #Do not copy broyd* files from the parent
        settings = {'remove_from_remotecopy_list': ['broyd*']}

        #Retrieve remote folder of the reference calculation
        pk_last = 0
        scf_ref_node = load_node(calc.pk)
        for i in scf_ref_node.called:
            if i.node_type == u'process.workflow.workchain.WorkChainNode.':
                if i.process_class is FleurBaseWorkChain:
                    if pk_last < i.pk:
                        pk_last = i.pk
        try:
            remote = load_node(pk_last).outputs.remote_folder
        except AttributeError:
            message = ('Found no remote folder of the referece scf calculation.')
            self.control_end_wc(message)
            return self.exit_codes.ERROR_REFERENCE_CALCULATION_NOREMOTE

        label = 'Force_theorem_calculation'
        description = 'This is a force theorem calculation for all SQA'

        code = self.inputs.fleur
        options = self.ctx.options.copy()

        inputs_builder = get_inputs_fleur(code, remote,
            fleurin, options, label, description, settings, serial=self.ctx.wf_dict['serial'])
        future = self.submit(FleurBaseWorkChain, **inputs_builder)
        return ToContext(f_t=future)

    def get_results(self):
        """
        Generates results of the workchain.
        """
        t_energydict = []
        htr2eV = 27.21138602
        try:
            calculation = self.ctx.f_t
            if not calculation.is_finished_ok:
                message = ('ERROR: Force theorem Fleur calculation failed somehow it has '
                           'exit status {}'.format(calculation.exit_status))
                self.control_end_wc(message)
                return self.exit_codes.ERROR_FORCE_THEOREM_FAILED
        except AttributeError:
            message = 'ERROR: Something went wrong I do not have a force theorem Fleur calculation'
            self.control_end_wc(message)
            return self.exit_codes.ERROR_FORCE_THEOREM_FAILED

        try:
            t_energydict = calculation.outputs.output_parameters.dict.spst_force_evSum
            e_u = calculation.outputs.output_parameters.dict.energy_units

            #Find a minimal value of SpSp and count it as 0
            labelmin = 0
            for labels in range(1, len(t_energydict)):
                if t_energydict[labels] < t_energydict[labelmin]:
                    labelmin = labels
            minenergy = t_energydict[labelmin]

            for labels in range(len(t_energydict)):
                t_energydict[labels] = t_energydict[labels] - minenergy
                if e_u == 'Htr' or 'htr':
                    t_energydict[labels] = t_energydict[labels] * htr2eV
            self.ctx.energy_dict = t_energydict

        except AttributeError:
            message = ('Did not manage to read evSum or energy units after FT calculation.')
            self.control_end_wc(message)
            return self.exit_codes.ERROR_FORCE_THEOREM_FAILED

    def return_results(self):
        """
        This function outputs results of the wc
        """
        out = {'workflow_name' : self.__class__.__name__,
               'workflow_version' : self._workflowversion,
               'initial_structure': self.inputs.structure.uuid,
               'is_it_force_theorem' : True,
               'energies' : self.ctx.energy_dict,
               'q_vectors' : self.ctx.wf_dict['q_vectors'],
               'energy_units' : 'eV',
               'info' : self.ctx.info,
               'warnings' : self.ctx.warnings,
               'errors' : self.ctx.errors
              }

        out = save_output_node(Dict(dict=out))
        self.out('out', out)

    def control_end_wc(self, errormsg):
        """
        Controled way to shutdown the workchain. will initalize the output nodes
        The shutdown of the workchain will has to be done afterwards
        """
        self.report(errormsg) # because return_results still fails somewhen
        self.ctx.errors.append(errormsg)
        self.return_results()

@cf
def save_output_node(out):
    """
    This calcfunction saves the out dict in the db
    """
    out_wc = out.clone()
    return out_wc