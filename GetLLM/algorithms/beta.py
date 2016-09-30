'''
Created on 27 May 2013

@author: ?, vimaier

@version: 0.0.1

GetLLM.algorithms.beta.py stores helper functions for phase calculations for GetLLM.
This module is not intended to be executed. It stores only functions.

Change history:
 - <version>, <author>, <date>:
    <description>
'''

import sys
import math
import traceback

import numpy as np
from numpy import sin, cos, tan

import Python_Classes4MAD.metaclass
import Utilities.bpm
import compensate_ac_effect
import os
import re
from Python_Classes4MAD.BCORR import default

DEBUG = sys.flags.debug  # True with python option -d! ("python -d GetLLM.py...") (vimaier)

if DEBUG:
    from Utilities.progressbar import startProgress, progress, endProgress
else:
    def startProgress(name):
        print "START " + name
        
    def progress(i):
        return
    
    def endProgress():
        print "Done"

#--- Constants

PI      = 3.14159265358979323846    #@IgnorePep8
TWOPI   = PI * 2.0                  #@IgnorePep8

DEFAULT_WRONG_BETA  = 1000          #@IgnorePep8
EPSILON             = 1.0E-16       #@IgnorePep8
SEXT_FACT           = 2.0           #@IgnorePep8
A_FACT              = -.5           #@IgnorePep8

# Just for now:
# TODO: decide for one of the two (hopefully not the two step matrix)
USE_TWOSTEPMATRIX = True


#===================================================================================================
# main part
#===================================================================================================
class BetaData(object):
    """ File for storing results from beta computations. """

    def __init__(self):
        self.x_phase = None  # beta x from phase
        self.x_phase_f = None  # beta x from phase free
        self.y_phase = None  # beta y from phase
        self.y_phase_f = None  # beta y from phase free

        self.x_amp = None  # beta x from amplitude
        self.y_amp = None  # beta y from amplitude

        self.x_ratio = None  # beta x ratio
        self.x_ratio_f = None  # beta x ratio free
        self.y_ratio = None  # beta x ratio
        self.y_ratio_f = None  # beta x ratio free


def calculate_beta_from_phase(getllm_d, twiss_d, tune_d, phase_d,
                              mad_twiss, mad_ac, mad_elem, mad_elem_centre, mad_best_knowledge, mad_ac_best_knowledge,
                              files_dict, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms,
                              errordefspath):
    '''
    Calculates beta and fills the following TfsFiles:
        getbetax.out        getbetax_free.out        getbetax_free2.out
        getbetay.out        getbetay_free.out        getbetay_free2.out

    :Parameters:
        'getllm_d': _GetllmData (In-param, values will only be read)
            lhc_phase, accel and beam_direction are used.
        'twiss_d': _TwissData (In-param, values will only be read)
            Holds twiss instances of the src files.
        'tune_d': _TuneData (In-param, values will only be read)
            Holds tunes and phase advances
        'phase_d': _PhaseData (In-param, values will only be read)
            Holds results from get_phases
    '''
    beta_d = BetaData()

    print 'Calculating beta'
    if(use_only_three_bpms_for_beta_from_phase):
        print "WARNING: use_only_three_bpms_for_beta_from_phase = True"
    #---- H plane
    if twiss_d.has_zero_dpp_x():
        [beta_d.x_phase, rmsbbx, alfax, bpms, error_method, corr] = beta_from_phase(mad_ac_best_knowledge, mad_elem, mad_elem_centre,
                                                                                    twiss_d.zero_dpp_x, phase_d.ph_x, 'H',
                                                                                    use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, errordefspath)
        beta_d.x_phase['DPP'] = 0
        tfs_file = files_dict['getbetax.out']
        tfs_file.add_float_descriptor("Q1", tune_d.q1)
        tfs_file.add_float_descriptor("Q2", tune_d.q2)
        tfs_file.add_float_descriptor("RMSbetabeat", rmsbbx)
        if error_method == "Estimated by std (3 BPM method), no bet_deviations.npy file found":
            tfs_file.add_float_descriptor("NumberOfBPMs", 3)
            tfs_file.add_float_descriptor("RangeOfBPMs", 5)
        else:
            tfs_file.add_float_descriptor("NumberOfBPMs", number_of_bpms)
            tfs_file.add_float_descriptor("RangeOfBPMs", range_of_bpms)

        tfs_file.add_string_descriptor("ErrorsFrom", error_method)
        tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "SYSBETX", "STATBETX", "ERRBETX", "CORR_ALFABETA", "ALFX", "SYSALFX", "STATALFX", "ERRALFX", "BETXMDL", "ALFXMDL", "MUXMDL"])
        tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
        for i in range(0, len(bpms)):
            bn1 = str.upper(bpms[i][1])
            bns1 = bpms[i][0]
            list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x),
                                beta_d.x_phase[bn1][0], beta_d.x_phase[bn1][1], beta_d.x_phase[bn1][2], beta_d.x_phase[bn1][3],
                                corr[bn1],
                                alfax[bn1][0], alfax[bn1][1], alfax[bn1][2], alfax[bn1][3],
                                mad_ac.BETX[mad_ac.indx[bn1]], mad_ac.ALFX[mad_ac.indx[bn1]], mad_ac.MUX[mad_ac.indx[bn1]]]
            tfs_file.add_table_row(list_row_entries)

        #-- ac to free beta
        if getllm_d.with_ac_calc:
            #-- from eq
            try:
                [beta_d.x_phase_f, rmsbbxf, alfaxf, bpmsf, error_method, corr] = beta_from_phase(mad_best_knowledge, mad_elem, mad_elem_centre,
                                                                                                 twiss_d.zero_dpp_x, phase_d.x_f, 'H',
                                                                                                 use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, errordefspath)
                tfs_file = files_dict['getbetax_free.out']
                tfs_file.add_float_descriptor("Q1", tune_d.q1f)
                tfs_file.add_float_descriptor("Q2", tune_d.q2f)
                tfs_file.add_float_descriptor("RMSbetabeat", rmsbbxf)
                if error_method == "Estimated by std (3 BPM method), no bet_deviations.npy file found":
                    tfs_file.add_float_descriptor("NumberOfBPMs", 3)
                    tfs_file.add_float_descriptor("RangeOfBPMs", 5)
                else:
                    tfs_file.add_float_descriptor("NumberOfBPMs", number_of_bpms)
                    tfs_file.add_float_descriptor("RangeOfBPMs", range_of_bpms)
                tfs_file.add_string_descriptor("ErrorsFrom", error_method)
                tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "SYSBETX", "STATBETX", "ERRBETX", "CORR_ALFABETA", "ALFX", "SYSALFX", "STATALFX", "ERRALFX", "BETXMDL", "ALFXMDL", "MUXMDL"])
                tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
                for i in range(0, len(bpmsf)):
                    bn1 = str.upper(bpmsf[i][1])
                    bns1 = bpmsf[i][0]
                    list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x),
                                        beta_d.x_phase_f[bn1][0], beta_d.x_phase_f[bn1][1], beta_d.x_phase_f[bn1][2], beta_d.x_phase_f[bn1][3],
                                        corr[bn1],
                                        alfaxf[bn1][0], alfaxf[bn1][1], alfaxf[bn1][2], alfaxf[bn1][3],
                                        mad_twiss.BETX[mad_twiss.indx[bn1]], mad_twiss.ALFX[mad_twiss.indx[bn1]], mad_twiss.MUX[mad_twiss.indx[bn1]]]
                    tfs_file.add_table_row(list_row_entries)
            except:
                traceback.print_exc()

            #-- from the model
            [betaxf2, rmsbbxf2, alfaxf2, bpmsf2] = _get_free_beta(mad_ac, mad_twiss, beta_d.x_phase, rmsbbx, alfax, bpms, 'H')
            tfs_file = files_dict['getbetax_free2.out']
            tfs_file.add_float_descriptor("Q1", tune_d.q1f)
            tfs_file.add_float_descriptor("Q2", tune_d.q2f)
            tfs_file.add_float_descriptor("RMSbetabeat", rmsbbxf2)
            tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "SYSBETX", "STATBETX", "ERRBETX", "CORR_ALFABETA", "ALFX", "SYSALFX", "STATALFX", "ERRALFX", "BETXMDL", "ALFXMDL", "MUXMDL"])
            tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
            for i in range(0, len(bpmsf2)):
                bn1 = str.upper(bpmsf2[i][1])
                bns1 = bpmsf2[i][0]
                list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x),
                                    betaxf2[bn1][0], betaxf2[bn1][1], betaxf2[bn1][2], betaxf2[bn1][3],
                                    corr[bn1],
                                    alfaxf2[bn1][0], alfaxf2[bn1][1], alfaxf2[bn1][2], alfaxf2[bn1][3],
                                    mad_twiss.BETX[mad_twiss.indx[bn1]], mad_twiss.ALFX[mad_twiss.indx[bn1]], mad_twiss.MUX[mad_twiss.indx[bn1]]]
                tfs_file.add_table_row(list_row_entries)

    #---- V plane
    if twiss_d.has_zero_dpp_y():
        [beta_d.y_phase, rmsbby, alfay, bpms, error_method, corr] = beta_from_phase(mad_ac_best_knowledge, mad_elem, mad_elem_centre,
                                                                                    twiss_d.zero_dpp_y, phase_d.ph_y, 'V',
                                                                                    use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, errordefspath)
        beta_d.y_phase['DPP'] = 0
        tfs_file = files_dict['getbetay.out']
        tfs_file.add_float_descriptor("Q1", tune_d.q1)
        tfs_file.add_float_descriptor("Q2", tune_d.q2)
        tfs_file.add_float_descriptor("RMSbetabeat", rmsbby)
        if error_method == "Estimated by std (3 BPM method), no bet_deviations.npy file found":
            tfs_file.add_float_descriptor("NumberOfBPMs", 3)
            tfs_file.add_float_descriptor("RangeOfBPMs", 5)
        else:
            tfs_file.add_float_descriptor("NumberOfBPMs", number_of_bpms)
            tfs_file.add_float_descriptor("RangeOfBPMs", range_of_bpms)
        tfs_file.add_string_descriptor("ErrorsFrom", error_method)
        tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "SYSBETY", "STATBETY", "ERRBETY", "CORR_ALFABETA", "ALFY", "SYSALFY", "STATALFY", "ERRALFY", "BETYMDL", "ALFYMDL", "MUYMDL"])
        tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
        for i in range(0, len(bpms)):
            bn1 = str.upper(bpms[i][1])
            bns1 = bpms[i][0]
            list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y),
                                beta_d.y_phase[bn1][0], beta_d.y_phase[bn1][1], beta_d.y_phase[bn1][2], beta_d.y_phase[bn1][3],
                                corr[bn1],
                                alfay[bn1][0], alfay[bn1][1], alfay[bn1][2], alfay[bn1][3],
                                mad_ac.BETY[mad_ac.indx[bn1]], mad_ac.ALFY[mad_ac.indx[bn1]], mad_ac.MUY[mad_ac.indx[bn1]]]
            tfs_file.add_table_row(list_row_entries)

        #-- ac to free beta
        if getllm_d.with_ac_calc:
            #-- from eq
            try:
                [beta_d.y_phase_f, rmsbbyf, alfayf, bpmsf, error_method, corr] = beta_from_phase(mad_best_knowledge, mad_elem, mad_elem_centre,
                                                                                                 twiss_d.zero_dpp_y, phase_d.y_f, 'V',
                                                                                                 use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, errordefspath)
                tfs_file = files_dict['getbetay_free.out']
                tfs_file.add_float_descriptor("Q1", tune_d.q1f)
                tfs_file.add_float_descriptor("Q2", tune_d.q2f)
                tfs_file.add_float_descriptor("RMSbetabeat", rmsbbyf)
                if error_method == "Estimated by std (3 BPM method), no bet_deviations.npy file found":
                    tfs_file.add_float_descriptor("NumberOfBPMs", 3)
                    tfs_file.add_float_descriptor("RangeOfBPMs", 5)
                else:
                    tfs_file.add_float_descriptor("NumberOfBPMs", number_of_bpms)
                    tfs_file.add_float_descriptor("RangeOfBPMs", range_of_bpms)
                tfs_file.add_string_descriptor("ErrorsFrom", error_method)
                tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "SYSBETY", "STATBETY", "ERRBETY", "CORR_ALFABETA", "ALFY", "SYSALFY", "STATALFY", "ERRALFY", "BETYMDL", "ALFYMDL", "MUYMDL"])
                tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
                for i in range(0, len(bpmsf)):
                    bn1 = str.upper(bpmsf[i][1])
                    bns1 = bpmsf[i][0]
                    list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y),
                                        beta_d.y_phase_f[bn1][0], beta_d.y_phase_f[bn1][1], beta_d.y_phase_f[bn1][2], beta_d.y_phase_f[bn1][3],
                                        corr[bn1],
                                        alfayf[bn1][0], alfayf[bn1][1], alfayf[bn1][2], alfayf[bn1][3],
                                        mad_twiss.BETY[mad_twiss.indx[bn1]], mad_twiss.ALFY[mad_twiss.indx[bn1]], mad_twiss.MUY[mad_twiss.indx[bn1]]]
                    tfs_file.add_table_row(list_row_entries)
            except:
                traceback.print_exc()

            #-- from the model
            [betayf2, rmsbbyf2, alfayf2, bpmsf2] = _get_free_beta(mad_ac, mad_twiss, beta_d.y_phase, rmsbby, alfay, bpms, 'V')
            tfs_file = files_dict['getbetay_free2.out']
            tfs_file.add_float_descriptor("Q1", tune_d.q1f)
            tfs_file.add_float_descriptor("Q2", tune_d.q2f)
            tfs_file.add_float_descriptor("RMSbetabeat", rmsbbyf2)
            tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "SYSBETY", "STATBETY", "ERRBETY", "CORR_ALFABETA", "ALFY", "SYSALFY", "STATALFY", "ERRALFY", "BETYMDL", "ALFYMDL", "MUYMDL"])
            tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
            for i in range(0, len(bpmsf2)):
                bn1 = str.upper(bpmsf2[i][1])
                bns1 = bpmsf2[i][0]
                list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y),
                                    betayf2[bn1][0], betayf2[bn1][1], betayf2[bn1][2], betayf2[bn1][3],
                                    corr[bn1],
                                    alfayf2[bn1][0], alfayf2[bn1][1], alfayf2[bn1][2], alfayf2[bn1][3],
                                    mad_twiss.BETY[mad_twiss.indx[bn1]], mad_twiss.ALFY[mad_twiss.indx[bn1]], mad_twiss.MUY[mad_twiss.indx[bn1]]]
                tfs_file.add_table_row(list_row_entries)

    return beta_d
# END calculate_beta_from_phase -------------------------------------------------------------------------------


def calculate_beta_from_amplitude(getllm_d, twiss_d, tune_d, phase_d, beta_d, mad_twiss, mad_ac, files_dict):
    '''
    Calculates beta and fills the following TfsFiles:
        getampbetax.out        getampbetax_free.out        getampbetax_free2.out
        getampbetay.out        getampbetay_free.out        getampbetay_free2.out

    :Parameters:
        'getllm_d': _GetllmData (In-param, values will only be read)
            accel and beam_direction are used.
        'twiss_d': _TwissData (In-param, values will only be read)
            Holds twiss instances of the src files.
        'tune_d': _TuneData (In-param, values will only be read)
            Holds tunes and phase advances
        'phase_d': _PhaseData (In-param, values will only be read)
            Holds results from get_phases
        'beta_d': _BetaData (In/Out-param, values will be read and set)
            Holds results from get_beta. Beta from amp and ratios will be set.

    :Return: _BetaData
        the same instance as param beta_d to indicate that x_amp,y_amp and ratios were set.
    '''
    print 'Calculating beta from amplitude'

    #---- H plane
    if twiss_d.has_zero_dpp_x():
        [beta_d.x_amp, rmsbbx, bpms, inv_jx] = beta_from_amplitude(mad_ac, twiss_d.zero_dpp_x, 'H')
        beta_d.x_amp['DPP'] = 0
        #-- Rescaling
        beta_d.x_ratio = 0
        skipped_bpmx = []
        arcbpms = Utilities.bpm.filterbpm(bpms)
        for bpm in arcbpms:
            name = str.upper(bpm[1])  # second entry is the name
        #Skip BPM with strange data
            if abs(beta_d.x_phase[name][0] / beta_d.x_amp[name][0]) > 100:
                skipped_bpmx.append(name)
            elif (beta_d.x_amp[name][0] < 0 or beta_d.x_phase[name][0] < 0):
                skipped_bpmx.append(name)
            else:
                beta_d.x_ratio = beta_d.x_ratio + (beta_d.x_phase[name][0] / beta_d.x_amp[name][0])

        try:
            beta_d.x_ratio = beta_d.x_ratio / (len(arcbpms) - len(skipped_bpmx))
        except ZeroDivisionError:
            beta_d.x_ratio = 1
        except:
            traceback.print_exc()
            beta_d.x_ratio = 1

        betax_rescale = {}

        for bpm in bpms:
            name = str.upper(bpm[1])
            betax_rescale[name] = [beta_d.x_ratio * beta_d.x_amp[name][0], beta_d.x_ratio * beta_d.x_amp[name][1], beta_d.x_amp[name][2]]

        tfs_file = files_dict['getampbetax.out']
        tfs_file.add_float_descriptor("Q1", tune_d.q1)
        tfs_file.add_float_descriptor("Q2", tune_d.q2)
        tfs_file.add_float_descriptor("RMSbetabeat", rmsbbx)
        tfs_file.add_float_descriptor("RescalingFactor", beta_d.x_ratio)
        tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "BETXSTD", "BETXMDL", "MUXMDL", "BETXRES", "BETXSTDRES"])
        tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
        for i in range(0, len(bpms)):
            bn1 = str.upper(bpms[i][1])
            bns1 = bpms[i][0]
            list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x), beta_d.x_amp[bn1][0], beta_d.x_amp[bn1][1], mad_ac.BETX[mad_ac.indx[bn1]], mad_ac.MUX[mad_ac.indx[bn1]], betax_rescale[bn1][0], betax_rescale[bn1][1]]
            tfs_file.add_table_row(list_row_entries)

        #-- ac to free amp beta
        if getllm_d.with_ac_calc:
            #-- from eq
            try:
                betaxf, rmsbbxf, bpmsf = compensate_ac_effect.get_free_beta_from_amp_eq(mad_ac, twiss_d.zero_dpp_x, tune_d.q1, tune_d.q1f, phase_d.acphasex_ac2bpmac, 'H', getllm_d.beam_direction, getllm_d.lhc_phase)
                #-- Rescaling
                beta_d.x_ratio_f = 0
                skipped_bpmxf = []
                arcbpms = Utilities.bpm.filterbpm(bpmsf)
                for bpm in arcbpms:
                    name = str.upper(bpm[1])  # second entry is the name
                #Skip BPM with strange data
                    if abs(beta_d.x_phase_f[name][0] / betaxf[name][0]) > 10:
                        skipped_bpmxf.append(name)
                    elif abs(beta_d.x_phase_f[name][0] / betaxf[name][0]) < 0.1:
                        skipped_bpmxf.append(name)
                    elif (betaxf[name][0] < 0 or beta_d.x_phase_f[name][0] < 0):
                        skipped_bpmxf.append(name)
                    else:
                        beta_d.x_ratio_f = beta_d.x_ratio_f + (beta_d.x_phase_f[name][0] / betaxf[name][0])

                try:
                    beta_d.x_ratio_f = beta_d.x_ratio_f / (len(arcbpms) - len(skipped_bpmxf))
                except:
                    traceback.print_exc()
                    beta_d.x_ratio_f = 1
                tfs_file = files_dict['getampbetax_free.out']
                tfs_file.add_float_descriptor("Q1", tune_d.q1f)
                tfs_file.add_float_descriptor("Q2", tune_d.q2f)
                tfs_file.add_float_descriptor("RMSbetabeat", rmsbbxf)
                tfs_file.add_float_descriptor("RescalingFactor", beta_d.x_ratio_f)
                tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "BETXSTD", "BETXMDL", "MUXMDL", "BETXRES", "BETXSTDRES"])
                tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
                for i in range(0, len(bpmsf)):
                    bn1 = str.upper(bpmsf[i][1])
                    bns1 = bpmsf[i][0]
                    list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x), betaxf[bn1][0], betaxf[bn1][1], mad_twiss.BETX[mad_twiss.indx[bn1]], mad_twiss.MUX[mad_twiss.indx[bn1]], beta_d.x_ratio_f * betaxf[bn1][0], beta_d.x_ratio_f * betaxf[bn1][1]]
                    tfs_file.add_table_row(list_row_entries)

            except:
                traceback.print_exc()
            #-- from the model
            # Since invJxf2(return_value[3]) is not used, slice the return value([:3]) (vimaier)
            [betaxf2, rmsbbxf2, bpmsf2] = _get_free_amp_beta(beta_d.x_amp, rmsbbx, bpms, inv_jx, mad_ac, mad_twiss, 'H')[:3]
            betaxf2_rescale = _get_free_amp_beta(betax_rescale, rmsbbx, bpms, inv_jx, mad_ac, mad_twiss, 'H')[0]
            tfs_file = files_dict['getampbetax_free2.out']
            tfs_file.add_float_descriptor("Q1", tune_d.q1f)
            tfs_file.add_float_descriptor("Q2", tune_d.q2f)
            tfs_file.add_float_descriptor("RMSbetabeat", rmsbbxf2)
            tfs_file.add_float_descriptor("RescalingFactor", beta_d.x_ratio)
            tfs_file.add_column_names(["NAME", "S", "COUNT", "BETX", "BETXSTD", "BETXMDL", "MUXMDL", "BETXRES", "BETXSTDRES"])
            tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
            for i in range(0, len(bpmsf2)):
                bn1 = str.upper(bpmsf2[i][1])
                bns1 = bpmsf2[i][0]
                list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_x), betaxf2[bn1][0], betaxf2[bn1][1], mad_twiss.BETX[mad_twiss.indx[bn1]], mad_twiss.MUX[mad_twiss.indx[bn1]], betaxf2_rescale[bn1][0], betaxf2_rescale[bn1][1]]
                tfs_file.add_table_row(list_row_entries)  # V plane

    if twiss_d.has_zero_dpp_y():
        [beta_d.y_amp, rmsbby, bpms, inv_jy] = beta_from_amplitude(mad_ac, twiss_d.zero_dpp_y, 'V')
        beta_d.y_amp['DPP'] = 0
        #-- Rescaling
        beta_d.y_ratio = 0
        skipped_bpmy = []
        arcbpms = Utilities.bpm.filterbpm(bpms)
        for bpm in arcbpms:
            name = str.upper(bpm[1])  # second entry is the name
            #Skip BPM with strange data
            if name in beta_d.y_phase:
                if abs(beta_d.y_phase[name][0] / beta_d.y_amp[name][0]) > 100:
                    skipped_bpmy.append(name)
                elif (beta_d.y_amp[name][0] < 0 or beta_d.y_phase[name][0] < 0):
                    skipped_bpmy.append(name)
                else:
                    beta_d.y_ratio = beta_d.y_ratio + (beta_d.y_phase[name][0] / beta_d.y_amp[name][0])

        try:
            beta_d.y_ratio = beta_d.y_ratio / (len(arcbpms) - len(skipped_bpmy))
        except ZeroDivisionError:
            beta_d.y_ratio = 1
        betay_rescale = {}

        for bpm in bpms:
            name = str.upper(bpm[1])
            betay_rescale[name] = [beta_d.y_ratio * beta_d.y_amp[name][0], beta_d.y_ratio * beta_d.y_amp[name][1], beta_d.y_amp[name][2]]

        tfs_file = files_dict['getampbetay.out']
        tfs_file.add_float_descriptor("Q1", tune_d.q1)
        tfs_file.add_float_descriptor("Q2", tune_d.q2)
        tfs_file.add_float_descriptor("RMSbetabeat", rmsbby)
        tfs_file.add_float_descriptor("RescalingFactor", beta_d.y_ratio)
        tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "BETYSTD", "BETYMDL", "MUYMDL", "BETYRES", "BETYSTDRES"])
        tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
        for i in range(0, len(bpms)):
            bn1 = str.upper(bpms[i][1])
            bns1 = bpms[i][0]
            list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y), beta_d.y_amp[bn1][0], beta_d.y_amp[bn1][1], mad_ac.BETY[mad_ac.indx[bn1]], mad_ac.MUY[mad_ac.indx[bn1]], betay_rescale[bn1][0], betay_rescale[bn1][1]]
            tfs_file.add_table_row(list_row_entries)  # ac to free amp beta

        if getllm_d.with_ac_calc:  # from eq
            try:
                betayf, rmsbbyf, bpmsf = compensate_ac_effect.get_free_beta_from_amp_eq(mad_ac, twiss_d.zero_dpp_y, tune_d.q2, tune_d.q2f, phase_d.acphasey_ac2bpmac, 'V', getllm_d.beam_direction, getllm_d.accel)  # Rescaling
                beta_d.y_ratio_f = 0
                skipped_bpmyf = []
                arcbpms = Utilities.bpm.filterbpm(bpmsf)
                for bpm in arcbpms:
                    name = str.upper(bpm[1])  # second entry is the name
                    #Skip BPM with strange data
                    if abs(beta_d.y_phase_f[name][0] / betayf[name][0]) > 10:
                        skipped_bpmyf.append(name)
                    elif (betayf[name][0] < 0 or beta_d.y_phase_f[name][0] < 0):
                        skipped_bpmyf.append(name)
                    elif abs(beta_d.y_phase_f[name][0] / betayf[name][0]) < 0.1:
                        skipped_bpmyf.append(name)
                    else:
                        beta_d.y_ratio_f = beta_d.y_ratio_f + (beta_d.y_phase_f[name][0] / betayf[name][0])

                try:
                    beta_d.y_ratio_f = beta_d.y_ratio_f / (len(arcbpms) - len(skipped_bpmyf))
                except ZeroDivisionError:
                    beta_d.y_ratio_f = 1
                tfs_file = files_dict['getampbetay_free.out']
                tfs_file.add_float_descriptor("Q1", tune_d.q1f)
                tfs_file.add_float_descriptor("Q2", tune_d.q2f)
                tfs_file.add_float_descriptor("RMSbetabeat", rmsbbyf)
                tfs_file.add_float_descriptor("RescalingFactor", beta_d.y_ratio_f)
                tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "BETYSTD", "BETYMDL", "MUYMDL", "BETYRES", "BETYSTDRES"])
                tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
                for i in range(0, len(bpmsf)):
                    bn1 = str.upper(bpmsf[i][1])
                    bns1 = bpmsf[i][0]
                    list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y), betayf[bn1][0], betayf[bn1][1], mad_twiss.BETY[mad_twiss.indx[bn1]], mad_twiss.MUY[mad_twiss.indx[bn1]], (beta_d.y_ratio_f * betayf[bn1][0]), (beta_d.y_ratio_f * betayf[bn1][1])]
                    tfs_file.add_table_row(list_row_entries)  # 'except ALL' catched a SystemExit from filterbpm().(vimaier)

            except SystemExit:
                traceback.print_exc()
                sys.exit(1)
            except:
                #-- from the model
                traceback.print_exc()
            # Since invJyf2(return_value[3]) is not used, slice the return value([:3]) (vimaier)
            [betayf2, rmsbbyf2, bpmsf2] = _get_free_amp_beta(beta_d.y_amp, rmsbby, bpms, inv_jy, mad_ac, mad_twiss, 'V')[:3]
            betayf2_rescale = _get_free_amp_beta(betay_rescale, rmsbby, bpms, inv_jy, mad_ac, mad_twiss, 'V')[0]
            tfs_file = files_dict['getampbetay_free2.out']
            tfs_file.add_float_descriptor("Q1", tune_d.q1f)
            tfs_file.add_float_descriptor("Q2", tune_d.q2f)
            tfs_file.add_float_descriptor("RMSbetabeat", rmsbbyf2)
            tfs_file.add_float_descriptor("RescalingFactor", beta_d.y_ratio)
            tfs_file.add_column_names(["NAME", "S", "COUNT", "BETY", "BETYSTD", "BETYMDL", "MUYMDL", "BETYRES", "BETYSTDRES"])
            tfs_file.add_column_datatypes(["%s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
            for i in range(0, len(bpmsf2)):
                bn1 = str.upper(bpmsf2[i][1])
                bns1 = bpmsf2[i][0]
                list_row_entries = ['"' + bn1 + '"', bns1, len(twiss_d.zero_dpp_y), betayf2[bn1][0], betayf2[bn1][1], mad_twiss.BETY[mad_twiss.indx[bn1]], mad_twiss.MUY[mad_twiss.indx[bn1]], betayf2_rescale[bn1][0], betayf2_rescale[bn1][1]]
                tfs_file.add_table_row(list_row_entries)

    return beta_d
# END calculate_beta_from_amplitude ----------------------------------------------------------------


def beta_from_phase(madTwiss, madElements, madElementsCentre, ListOfFiles, phase, plane, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, errordefspath):
    '''
    Calculate the beta function from phase advances
    If range of BPMs is sufficiently large use averaging with weighted mean. The weights are determinde using either the
    output of Monte Carlo simulations or using analytical formulas derived from exacter formulas to calculate the beta
    function.
    
    :Parameters:
        'madTwiss':twiss
            model twiss file
        'ListOfFiles':twiss
            measurement files
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'use_only_three_bpms_for_beta_from_phase':Boolean
            self-explanatory
        'number_of_bpms':int
            use the number_of_bpm betas with the lowest phase advance (only used when monte carlo simulations are used)
        'range_of_bpms':int
            length of range of bpms used to calculate the beta function. Has to be an odd number 1 < r < 21
        'errordefspath':String
            the paths to the error definition file. If not specified, Monte Carlo simulation is used
    :Return:tupel (beta,rmsbb,alfa,commonbpms)
        'beta':dict
            calculated beta function for all BPMs
        'rmsbb':float
            rms beta-beating
        'alfa':dict
            calculated alfa function for all BPMs
        'commonbpms':list
            intersection of common BPMs in measurement files and model
    '''
    if phase == {}:
        return [{}, 0.0, {}, []]
    alfa = {}
    beta = {}
    corr = {}
    
    print "START beta from phase"

    commonbpms = Utilities.bpm.intersect(ListOfFiles)
    commonbpms = Utilities.bpm.model_intersect(commonbpms, madTwiss)
    
    errorfile = None
    if not use_only_three_bpms_for_beta_from_phase:
        errorfile = create_errorfile(errordefspath, madTwiss, madElements, madElementsCentre, commonbpms, plane)
   
    if 3 > len(commonbpms):
        print "beta_from_phase: Less than three BPMs for plane", plane + ". Returning empty values."
        return ({}, 0.0, {}, [])

    if 7 > len(commonbpms) and errorfile == None:
        print "beta_from_phase: Less than seven BPMs for plane", plane + ". Can not use optimised algorithm."

    errors_method = "Covariance matrix"
    
    delbeta = []
    
    rmsbb = 0.0
    
    #---- Error definitions given and we decided to not use the simulation => use analytical formulas to calculate the
    # systematic errors
    if errorfile != None and not use_only_three_bpms_for_beta_from_phase:
        
        rmsbb, errors_method = ScanAllBPMs_withSystematicErrors(madTwiss, errorfile, phase, plane, range_of_bpms, alfa, beta, corr, commonbpms, delbeta)
        return [beta, rmsbb, alfa, commonbpms, errors_method, corr]
    #---- use the simulations
    else:
        rmsbb, errors_method = ScanAllBPMS_sim_3bpm(madTwiss, phase, plane, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, alfa, beta, corr, commonbpms, delbeta)

    return [beta, rmsbb, alfa, commonbpms, errors_method, corr]


def beta_from_amplitude(mad_twiss, list_of_files, plane):

    beta = {}
    root2j = []
    commonbpms = Utilities.bpm.intersect(list_of_files)
    commonbpms = Utilities.bpm.model_intersect(commonbpms, mad_twiss)
    sum_a = 0.0
    amp = []
    amp2 = []
    kick2 = []
    for i in range(0, len(commonbpms)):  # this loop have become complicated after modifications... anybody simplify?
        bn1 = str.upper(commonbpms[i][1])
        if plane == 'H':
            tembeta = mad_twiss.BETX[mad_twiss.indx[bn1]]
        elif plane == 'V':
            tembeta = mad_twiss.BETY[mad_twiss.indx[bn1]]
        amp_i = 0.0
        amp_j2 = []
        root2j_i = 0.0
        counter = 0
        for tw_file in list_of_files:
            if i == 0:
                kick2.append(0)
            if plane == 'H':
                amp_i += tw_file.AMPX[tw_file.indx[bn1]]
                amp_j2.append(tw_file.AMPX[tw_file.indx[bn1]] ** 2)
                root2j_i += tw_file.PK2PK[tw_file.indx[bn1]] / 2.
            elif plane == 'V':
                amp_i += tw_file.AMPY[tw_file.indx[bn1]]
                amp_j2.append(tw_file.AMPY[tw_file.indx[bn1]] ** 2)
                root2j_i += tw_file.PK2PK[tw_file.indx[bn1]] / 2.

            kick2[counter] += amp_j2[counter] / tembeta
            counter += 1

        amp_i = amp_i / len(list_of_files)
        root2j_i = root2j_i / len(list_of_files)
        amp.append(amp_i)
        amp2.append(amp_j2)

        sum_a += amp_i ** 2 / tembeta
        root2j.append(root2j_i / math.sqrt(tembeta))

    kick = sum_a / len(commonbpms)  # Assuming the average of beta is constant
    kick2 = np.array(kick2)
    kick2 = kick2 / len(commonbpms)
    amp2 = np.array(amp2)
    root2j = np.array(root2j)
    root2j_ave = np.average(root2j)
    root2j_rms = math.sqrt(np.average(root2j * root2j) - root2j_ave**2 + 2.2e-16)

    delbeta = []
    for i in range(0, len(commonbpms)):
        bn1 = str.upper(commonbpms[i][1])
        location = commonbpms[i][0]
        for j in range(0, len(list_of_files)):
            amp2[i][j] = amp2[i][j] / kick2[j]
        #print np.average(amp2[i]*amp2[i]),np.average(amp2[i])**2
        try:
            betstd = math.sqrt(np.average(amp2[i] * amp2[i]) - np.average(amp2[i])**2 + 2.2e-16)
        except:
            betstd = 0

        beta[bn1] = [amp[i] ** 2 / kick, betstd, location]
        if plane == 'H':
            betmdl = mad_twiss.BETX[mad_twiss.indx[bn1]]
        elif plane == 'V':
            betmdl = mad_twiss.BETY[mad_twiss.indx[bn1]]
        delbeta.append((beta[bn1][0] - betmdl) / betmdl)

    invariant_j = [root2j_ave, root2j_rms]

    delbeta = np.array(delbeta)
    rmsbb = math.sqrt(np.average(delbeta * delbeta))
    return [beta, rmsbb, commonbpms, invariant_j]


#=======================================================================================================================
#---============== using the simulations to calculate the beta function and error bars =================================
#=======================================================================================================================

def ScanAllBPMS_sim_3bpm(madTwiss, phase, plane, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms, alfa, beta, corr, commonbpms, delbeta):
    systematic_errors_found = False
    systematics_error_path = os.path.join(os.path.dirname(os.path.abspath(madTwiss.filename)), "bet_deviations.npy")
    systematic_errors = None
    
    montecarlo = True
    errors_method = "Monte-Carlo Simulations"
    
    if use_only_three_bpms_for_beta_from_phase:
        montecarlo = False
        errors_method = "Standard (3 BPM method)"
    elif not os.path.isfile(systematics_error_path):
        montecarlo = False
        errors_method = "Stdandard (3 BPM method) because no bet_deviations.npy could be found"
        use_only_three_bpms_for_beta_from_phase = True
    else
        systematic_errors = np.load(systematics_error_path)
            
    if DEBUG:
        debugfile = open("debugfileMonteCarlo" + plane, "w+")
        startProgress("Calculate betas")
    print "Errors from " + errors_method
    for i in range(0, len(commonbpms)):
        if (i % 10) == 0 and DEBUG:
            progress(float(i) / len(commonbpms) * 100.0)
        alfa_beta, probed_bpm_name, M = get_best_three_bpms_with_beta_and_alfa(madTwiss, phase, plane, commonbpms, i, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms)
        alfi = sum([alfa_beta[i][3] for i in range(len(alfa_beta))]) / len(alfa_beta)
        alfstd = math.sqrt(sum([alfa_beta[i][2] ** 2 for i in range(len(alfa_beta))])) / math.sqrt(len(alfa_beta))
        try:
            alferr = math.sqrt(sum([alfa_beta[i][3] ** 2 for i in range(len(alfa_beta))]) / len(alfa_beta) - alfi ** 2.)
        except ValueError:
            alferr = 0
        if plane == 'H':
            betmdl1 = madTwiss.BETX[madTwiss.indx[probed_bpm_name]]
        elif plane == 'V':
            betmdl1 = madTwiss.BETY[madTwiss.indx[probed_bpm_name]]
        beti = DEFAULT_WRONG_BETA
        if montecarlo:
            T = np.transpose(np.matrix([alfa_beta[i][7] for i in range(len(alfa_beta))]))
            V1 = M * T
            V_stat = np.transpose(T) * V1
            V = np.zeros([len(alfa_beta), len(alfa_beta)])
            V_syst = np.zeros([len(alfa_beta), len(alfa_beta)])
            np.fill_diagonal(V_syst, 100000)
            #all_comb = [[alfa_beta[i][5], alfa_beta[i][6]] for i in range(len(alfa_beta))]
            if plane == 'H':
                sindex = 0
            elif plane == 'V':
                sindex = 1
            for comb1 in range(len(alfa_beta)):
                for comb2 in range(len(alfa_beta)):
                    possible_dict_key = [''.join([probed_bpm_name, alfa_beta[comb1][i], alfa_beta[comb1][j], alfa_beta[comb2][k], alfa_beta[comb2][l]]) for i in [5, 6] for j in [5, 6] if i != j for k in [5, 6] for l in [5, 6] if k != l]
                    for keyname in possible_dict_key:
                        if keyname in systematic_errors[sindex]:
                            V_syst[comb1][comb2] = systematic_errors[sindex][keyname] * betmdl1 ** 2
                            V_syst[comb2][comb1] = systematic_errors[sindex][keyname] * betmdl1 ** 2
            
            for k in range(len(alfa_beta)):
                for l in range(len(alfa_beta)):
                    V[k][l] = V_stat.item(k, l) + V_syst[k][l]
            
            try:
                V_inv = np.linalg.pinv(V)
            except LinAlgError:
                V_inv = np.diag(1.0, V.shape[0])
            if DEBUG:
                debugfile.write("\n\nbegin BPM " + probed_bpm_name + " :\n")
                printMatrix(debugfile, V_stat, "V_stat")
                printMatrix(debugfile, np.matrix(V_syst), "V_syst")
                printMatrix(debugfile, V, "V")
                printMatrix(debugfile, V_inv, "V_inv")
                printMatrix(debugfile, np.transpose(T), "T_trans")
                printMatrix(debugfile, M, "M")
            w = np.zeros(len(alfa_beta))
            V_inv_row_sum = V_inv.sum(axis=1, dtype='float')
            V_inv_sum = V_inv.sum(dtype='float')
            betstd = 0
            beterr = 0
            if V_inv_sum != 0:
                for i in range(len(w)):
                    w[i] = V_inv_row_sum[i] / V_inv_sum
                
                beti = float(sum([w[i] * alfa_beta[i][1] for i in range(len(alfa_beta))]))
                for i in range(len(alfa_beta)):
                    for j in range(len(alfa_beta)):
                        betstd = betstd + w[i] * w[j] * V_stat.item(i, j)
                
                betstd = np.sqrt(float(betstd))
                for i in range(len(alfa_beta)):
                    for j in range(len(alfa_beta)):
                        beterr = beterr + w[i] * w[j] * V_syst.item(i, j)
                if beterr < 0:
                    beterr = DEFAULT_WRONG_BETA
                else:
                    beterr = np.sqrt(float(beterr))
                if DEBUG:
                    debugfile.write("\ncombinations:\t")
                    for i in range(len(w)):
                        debugfile.write(alfa_beta[i][8] + "\t")
                    
                    debugfile.write("\n")
                    debugfile.write("\n")
                    debugfile.write("\nweights:\t")
                    #print "beti =", beti
                    for i in range(len(w)):
                        debugfile.write("{:.7f}".format(w[i]) + "\t")
                    
                    debugfile.write("\nbeta_values:\t")
                    for i in range(len(w)):
                        debugfile.write(str(alfa_beta[i][1]) + "\t")
                    
                    debugfile.write("\n")
                    debugfile.write("averaged beta: " + str(beti) + "\n")
                    debugfile.write("\nalfa_values:\t")
                    for i in range(len(w)):
                        debugfile.write(str(alfa_beta[i][3]) + "\t")
                    
                    debugfile.write("\n")
            else:
                betstd = DEFAULT_WRONG_BETA
                beterr = DEFAULT_WRONG_BETA
        else:
            beti = sum([alfa_beta[i][1] for i in range(len(alfa_beta))]) / len(alfa_beta)
            betstd = math.sqrt(sum([alfa_beta[i][0] ** 2 for i in range(len(alfa_beta))])) / math.sqrt(len(alfa_beta))
            try:
                beterr = math.sqrt(sum([alfa_beta[i][1] ** 2 for i in range(len(alfa_beta))]) / len(alfa_beta) - beti ** 2.)
            except ValueError:
                beterr = 0
                
        beta[probed_bpm_name] = beti, beterr, betstd, math.sqrt(beterr ** 2 + betstd ** 2)
        alfa[probed_bpm_name] = alfi, alferr, alfstd, math.sqrt(alferr ** 2 + alfstd ** 2)
        corr[probed_bpm_name] = .0
        delbeta.append((beti - betmdl1) / betmdl1)
        if DEBUG:
            debugfile.write("end\n")
    
    if DEBUG:
        endProgress()
    delbeta = np.array(delbeta)
    rmsbb = math.sqrt(np.average(delbeta * delbeta))
    if DEBUG:
        debugfile.close()
    return rmsbb, errors_method


def get_best_three_bpms_with_beta_and_alfa(madTwiss, phase, plane, commonbpms, i, use_only_three_bpms_for_beta_from_phase, number_of_bpms, range_of_bpms):
    '''
    Sorts BPM sets for the beta calculation based on their phase advance.
    If less than 7 BPMs are available it will fall back to using only next neighbours.
    :Parameters:
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'commonbpms':list
            intersection of common BPMs in measurement files and model
        'i': integer
            current iterator in the loop of all BPMs
    :Return: tupel(candidate1, candidate2, candidate3, bn4)
        'candidate1-3':list
            contains calculated beta and alfa
        'bn4':string
            name of the probed BPM
    '''

    RANGE = int(range_of_bpms)
    probed_index = int((RANGE - 1) / 2.)
 
    if 7 > len(commonbpms) or use_only_three_bpms_for_beta_from_phase:
        bn1 = str.upper(commonbpms[i % len(commonbpms)][1])
        bn2 = str.upper(commonbpms[(i + 1) % len(commonbpms)][1])
        bn3 = str.upper(commonbpms[(i + 2) % len(commonbpms)][1])
        bn4 = str.upper(commonbpms[(i + 3) % len(commonbpms)][1])
        bn5 = str.upper(commonbpms[(i + 4) % len(commonbpms)][1])
        candidates = []
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_right(bn1, bn2, bn3, madTwiss, phase, plane, 0, 0, 0)
        candidates.append([tbetstd, tbet, talfstd, talf])
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_mid(bn2, bn3, bn4, madTwiss, phase, plane, 0, 0, 0)
        candidates.append([tbetstd, tbet, talfstd, talf])
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_left(bn3, bn4, bn5, madTwiss, phase, plane, 0, 0, 0)
        candidates.append([tbetstd, tbet, talfstd, talf])
        return candidates, bn3, []

    bpm_name = {}
    for n in range(RANGE):
        bpm_name[n] = str.upper(commonbpms[(i + n) % len(commonbpms)][1])
        phase_err = {}
    if plane == 'H':
        for i in range(RANGE):
            if i < probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[i]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]])
            elif i > probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[probed_index], bpm_name[i]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[i]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]])
        phase_err[probed_index] = min([phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETX[madTwiss.indx[bpm_name[i]]]) for i in range(probed_index)] + [phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + 1 + i]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index + 1 + i]]]) for i in range(probed_index)])
    if plane == 'V':
        for i in range(RANGE):
            if i < probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[i]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]])
            if i > probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[probed_index], bpm_name[i]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[i]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]])
        phase_err[probed_index] = min([phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETY[madTwiss.indx[bpm_name[i]]]) for i in range(probed_index)] + [phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + 1 + i]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index + 1 + i]]]) for i in range(probed_index)])
   
    M = np.zeros([RANGE - 1, RANGE - 1])
    for k in range(RANGE - 1):
        for l in range(RANGE - 1):
            if k == l and k < probed_index:
                M[k][l] = (2*np.pi)**2 * phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + k + 1]])][1]**2
            elif k == l and k >= probed_index:
                M[k][l] = (2*np.pi)**2 * phase["".join([plane, bpm_name[RANGE - 2 - k], bpm_name[probed_index]])][1]**2
            elif (k < probed_index and l >= probed_index) or (k >= probed_index and l < probed_index):
                M[k][l] = -(2*np.pi)**2 * phase_err[probed_index]**2
            else:
                M[k][l] = (2*np.pi)**2 * phase_err[probed_index]**2
    candidates = []
    left_bpm = range(probed_index)
    right_bpm = range(probed_index + 1, RANGE)
    left_combo = [[x, y] for x in left_bpm for y in left_bpm if x < y]
    right_combo = [[x, y] for x in right_bpm for y in right_bpm if x < y]
    mid_combo = [[x, y] for x in left_bpm for y in right_bpm]
    
    #right_combo = []    #ABB
    #mid_combo = []      # BAB
    #left_combo = []     # BBA
   
    for n in left_combo:
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_right(bpm_name[n[0]], bpm_name[n[1]], bpm_name[probed_index], madTwiss, phase, plane, phase_err[n[0]], phase_err[n[1]], phase_err[probed_index])
        t_matrix_row = [0] * (RANGE-1)
        t_matrix_row[RANGE-2 - n[0]] = t1
        t_matrix_row[RANGE-2 - n[1]] = t2
        patternstr = ["x"] * RANGE
        patternstr[n[0]] = "B"
        patternstr[n[1]] = "B"
        patternstr[probed_index] = "A"
        candidates.append([tbetstd, tbet, talfstd, talf, mdlerr, bpm_name[n[0]], bpm_name[n[1]], t_matrix_row, "".join(patternstr)])

    for n in mid_combo:
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_mid(bpm_name[n[0]], bpm_name[probed_index], bpm_name[n[1]], madTwiss, phase, plane, phase_err[n[0]], phase_err[probed_index], phase_err[n[1]])
        t_matrix_row = [0] * (RANGE - 1)
        t_matrix_row[RANGE - 2 - n[0]] = t1
        t_matrix_row[n[1] - 1 - probed_index] = t2
        patternstr = ["x"] * RANGE
        patternstr[n[0]] = "B"
        patternstr[n[1]] = "B"
        patternstr[probed_index] = "A"
        candidates.append([tbetstd, tbet, talfstd, talf, mdlerr, bpm_name[n[0]], bpm_name[n[1]], t_matrix_row, "".join(patternstr)])

    for n in right_combo:
        tbet, tbetstd, talf, talfstd, mdlerr, t1, t2 = BetaFromPhase_BPM_left(bpm_name[probed_index], bpm_name[n[0]], bpm_name[n[1]], madTwiss, phase, plane, phase_err[probed_index], phase_err[n[0]], phase_err[n[1]])
        t_matrix_row = [0] * (RANGE-1)
        t_matrix_row[n[0] - 1 - probed_index] = t1
        t_matrix_row[n[1] - 1 - probed_index] = t2
        patternstr = ["x"] * RANGE
        patternstr[n[0]] = "B"
        patternstr[n[1]] = "B"
        patternstr[probed_index] = "A"
        candidates.append([tbetstd, tbet, talfstd, talf, mdlerr, bpm_name[n[0]], bpm_name[n[1]], t_matrix_row, "".join(patternstr)])

    #sort_cand = sorted(candidates, key=lambda x: x[4])
    #return [sort_cand[i] for i in range(NUM_BPM_COMBOS)], bpm_name[probed_index], M
    return candidates, bpm_name[probed_index], M


def BetaFromPhase_BPM_left(bn1, bn2, bn3, madTwiss, phase, plane, p1, p2, p3):
    '''
    Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is left of the other two BPMs (ABB)
    :Parameters:
        'bn1':string
            Name of probed BPM
        'bn2':string
            Name of first BPM right of the probed BPM
        'bn3':string
            Name of second BPM right of the probed BPM
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'betstd':float
            calculated error on beta function at probed BPM
        'alf':float
            calculated alfa function at probed BPM
        'alfstd':float
            calculated error on alfa function at probed BPM
    '''
    ph2pi12=2.*np.pi*phase["".join([plane,bn1,bn2])][0]
    ph2pi13=2.*np.pi*phase["".join([plane,bn1,bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl12 = 2.*np.pi*phase["".join([plane,bn1,bn2])][2]
    phmdl13=2.*np.pi*phase["".join([plane,bn1,bn3])][2]
    if plane=='H':
        betmdl1=madTwiss.BETX[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETX[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETX[madTwiss.indx[bn3]]
        alpmdl1=madTwiss.ALFX[madTwiss.indx[bn1]]
    elif plane=='V':
        betmdl1=madTwiss.BETY[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETY[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETY[madTwiss.indx[bn3]]
        alpmdl1=madTwiss.ALFY[madTwiss.indx[bn1]]
    if betmdl3 < 0 or betmdl2<0 or betmdl1<0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta1 and alpha1 from phases assuming model transfer matrix
    # Matrix M: BPM1-> BPM2
    # Matrix N: BPM1-> BPM3
    M11=math.sqrt(betmdl2/betmdl1)*(cos(phmdl12)+alpmdl1*sin(phmdl12))
    M12=math.sqrt(betmdl1*betmdl2)*sin(phmdl12)
    N11=math.sqrt(betmdl3/betmdl1)*(cos(phmdl13)+alpmdl1*sin(phmdl13))
    N12=math.sqrt(betmdl1*betmdl3)*sin(phmdl13)

    denom=M11/M12-N11/N12+1e-16
    numer=1/tan(ph2pi12)-1/tan(ph2pi13)
    bet=numer/denom

    betstd=        (2*np.pi*phase["".join([plane,bn1,bn2])][1]/sin(ph2pi12)**2)**2
    betstd=betstd+(2*np.pi*phase["".join([plane,bn1,bn3])][1]/sin(ph2pi13)**2)**2
    betstd=math.sqrt(betstd)/abs(denom)

    mdlerr=        (2*np.pi*0.001/sin(phmdl12)**2)**2
    mdlerr=mdlerr+(2*np.pi*0.001/sin(phmdl13)**2)**2
    mdlerr=math.sqrt(mdlerr)/abs(denom)    

    term1 = 1/sin(phmdl12)**2/denom
    term2 = -1/sin(phmdl13)**2/denom

    denom=M12/M11-N12/N11+1e-16
    numer=-M12/M11/tan(ph2pi12)+N12/N11/tan(ph2pi13)
    alf=numer/denom

    alfstd=        (M12/M11*2*np.pi*phase["".join([plane,bn1,bn2])][1]/sin(ph2pi12)**2)**2
    alfstd=alfstd+(N12/N11*2*np.pi*phase["".join([plane,bn1,bn3])][1]/sin(ph2pi13)**2)**2
    alfstd=math.sqrt(alfstd)/denom

    return bet, betstd, alf, alfstd, mdlerr, term1, term2

def BetaFromPhase_BPM_mid(bn1,bn2,bn3,madTwiss,phase,plane,p1,p2,p3):
    '''
    Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is between the other two BPMs
    :Parameters:
        'bn1':string
            Name of BPM left of the probed BPM
        'bn2':string
            Name of probed BPM
        'bn3':string
            Name of BPM right of the probed BPM
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'betstd':float
            calculated error on beta function at probed BPM
        'alf':float
            calculated alfa function at probed BPM
        'alfstd':float
            calculated error on alfa function at probed BPM
    '''
    ph2pi12=2.*np.pi*phase["".join([plane,bn1,bn2])][0]
    ph2pi23=2.*np.pi*phase["".join([plane,bn2,bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl12=2.*np.pi*phase["".join([plane,bn1,bn2])][2]
    phmdl23=2.*np.pi*phase["".join([plane,bn2,bn3])][2]
    if plane=='H':
        betmdl1=madTwiss.BETX[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETX[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETX[madTwiss.indx[bn3]]
        alpmdl2=madTwiss.ALFX[madTwiss.indx[bn2]]
    elif plane=='V':
        betmdl1=madTwiss.BETY[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETY[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETY[madTwiss.indx[bn3]]
        alpmdl2=madTwiss.ALFY[madTwiss.indx[bn2]]
    if betmdl3 < 0 or betmdl2<0 or betmdl1<0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta2 and alpha2 from phases assuming model transfer matrix
    # Matrix M: BPM1-> BPM2
    # Matrix N: BPM2-> BPM3
    M22=math.sqrt(betmdl1/betmdl2)*(cos(phmdl12)-alpmdl2*sin(phmdl12))
    M12=math.sqrt(betmdl1*betmdl2)*sin(phmdl12)
    N11=math.sqrt(betmdl3/betmdl2)*(cos(phmdl23)+alpmdl2*sin(phmdl23))
    N12=math.sqrt(betmdl2*betmdl3)*sin(phmdl23)

    denom=M22/M12+N11/N12+EPSILON
    #denom = (1.0/tan(phmdl12) + 1.0/tan(phmdl23) +EPSILON)/betmdl2
    numer=1/tan(ph2pi12)+1/tan(ph2pi23)
    bet=numer/denom

    betstd=        (2*np.pi*phase["".join([plane,bn1,bn2])][1]/sin(ph2pi12)**2)**2
    betstd=betstd+(2*np.pi*phase["".join([plane,bn2,bn3])][1]/sin(ph2pi23)**2)**2
    betstd=math.sqrt(betstd)/abs(denom)

    mdlerr=        (2*np.pi*0.001/sin(phmdl12)**2)**2
    mdlerr=mdlerr+(2*np.pi*0.001/sin(phmdl23)**2)**2
    mdlerr=math.sqrt(mdlerr)/abs(denom)

    term2 = 1/sin(phmdl23)**2/denom  #sign
    term1 = -1/sin(phmdl12)**2/denom  #sign

    denom=M12/M22+N12/N11+1e-16
    numer=M12/M22/tan(ph2pi12)-N12/N11/tan(ph2pi23)
    alf=numer/denom

    alfstd=        (M12/M22*2*np.pi*phase["".join([plane,bn1,bn2])][1]/sin(ph2pi12)**2)**2
    alfstd=alfstd+(N12/N11*2*np.pi*phase["".join([plane,bn2,bn3])][1]/sin(ph2pi23)**2)**2
    alfstd=math.sqrt(alfstd)/abs(denom)

    return bet, betstd, alf, alfstd, mdlerr, term1, term2

def BetaFromPhase_BPM_right(bn1,bn2,bn3,madTwiss,phase,plane,p1,p2,p3):
    '''
    Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is right the other two BPMs
    :Parameters:
        'bn1':string
            Name of second BPM left of the probed BPM
        'bn2':string
            Name of first BPM left of the probed BPM
        'bn3':string
            Name of probed BPM
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'betstd':float
            calculated error on beta function at probed BPM
        'alf':float
            calculated alfa function at probed BPM
        'alfstd':float
            calculated error on alfa function at probed BPM
    '''
    ph2pi23=2.*np.pi*phase["".join([plane,bn2,bn3])][0]
    ph2pi13=2.*np.pi*phase["".join([plane,bn1,bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl13=2.*np.pi*phase["".join([plane,bn1,bn3])][2]
    phmdl23=2.*np.pi*phase["".join([plane,bn2,bn3])][2]
    if plane=='H':
        betmdl1=madTwiss.BETX[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETX[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETX[madTwiss.indx[bn3]]
        alpmdl3=madTwiss.ALFX[madTwiss.indx[bn3]]
    elif plane=='V':
        betmdl1=madTwiss.BETY[madTwiss.indx[bn1]]
        betmdl2=madTwiss.BETY[madTwiss.indx[bn2]]
        betmdl3=madTwiss.BETY[madTwiss.indx[bn3]]
        alpmdl3=madTwiss.ALFY[madTwiss.indx[bn3]]
    if betmdl3 < 0 or betmdl2<0 or betmdl1<0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta3 and alpha3 from phases assuming model transfer matrix
    # Matrix M: BPM2-> BPM3
    # Matrix N: BPM1-> BPM3
    M22=math.sqrt(betmdl2/betmdl3)*(cos(phmdl23)-alpmdl3*sin(phmdl23))
    M12=math.sqrt(betmdl2*betmdl3)*sin(phmdl23)
    N22=math.sqrt(betmdl1/betmdl3)*(cos(phmdl13)-alpmdl3*sin(phmdl13))
    N12=math.sqrt(betmdl1*betmdl3)*sin(phmdl13)

    denom=M22/M12-N22/N12+1e-16
    numer=1/tan(ph2pi23)-1/tan(ph2pi13)
    bet=numer/denom

    betstd=        (2*np.pi*phase["".join([plane,bn2,bn3])][1]/sin(ph2pi23)**2)**2
    betstd=betstd+(2*np.pi*phase["".join([plane,bn1,bn3])][1]/sin(ph2pi13)**2)**2
    betstd=math.sqrt(betstd)/abs(denom)

    mdlerr=        (2*np.pi*0.001/sin(phmdl23)**2)**2
    mdlerr=mdlerr+(2*np.pi*0.001/sin(phmdl13)**2)**2
    mdlerr=math.sqrt(mdlerr)/abs(denom)

    term2 = -1/sin(phmdl23)**2/denom  #sign
    term1 = 1/sin(phmdl13)**2/denom  #sign

    denom=M12/M22-N12/N22+1e-16
    numer=M12/M22/tan(ph2pi23)-N12/N22/tan(ph2pi13)
    alf=numer/denom

    alfstd=        (M12/M22*2*np.pi*phase["".join([plane,bn2,bn3])][1]/sin(ph2pi23)**2)**2
    alfstd=alfstd+(N12/N22*2*np.pi*phase["".join([plane,bn1,bn3])][1]/sin(ph2pi13)**2)**2
    alfstd=math.sqrt(alfstd)/abs(denom)


    return bet, betstd, alf, alfstd, mdlerr, term1, term2

#=======================================================================================================================
#---============== using analytical formula ============================================================================
#=======================================================================================================================


def ScanAllBPMs_withSystematicErrors(madTwiss, errorfile, phase, plane, range_of_bpms, alfa, beta, corr, commonbpms, delbeta):
    '''
    If errorfile is given (!= "0") this function calculates the beta function for each BPM using the analytic expression
    for the estimation of the error matrix.
    
    :Parameters:
        'madTwiss':twiss
            model twiss file
        'errorfile':twiss
            final errorfile (not error definitions)
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'alfa, beta':vector
            out vectors which will be filled with the beta nad alfa functions
        'commonbpms':list
            intersection of common BPMs in measurement files and model
    '''
    
    print "INFO: errorfile given. Create list_of_Ks"
    list_of_Ks = []
    
    errors_method = "Analytical Formula"
    print "Errors from " + errors_method
       
    #---- create list of Ks, i.e. assign to each BPM a vector with all the errore lements that come after the bpm
    # and their respective errors
    # and model phases so that list_of_Ks[n] yields the error elements between BPM[n] and BPM[n+1]
    # update 2016-07-28: list_of_Ks[n][k], n: BPM number, k=0: quadrupole field errors,
    # k=1: transversal sextupole missalignments
    # k=2: longitudinal quadrupole missalignments

    for n in range(len(commonbpms) + range_of_bpms + 1):
        index_n = errorfile.indx[commonbpms[n % len(commonbpms)][1]]
        index_nplus1 = errorfile.indx[commonbpms[(n + 1) % len(commonbpms)][1]]
              
        quad_fields = []
        sext_trans = []
        quad_missal = []
               
        if index_n < index_nplus1:           
            for i in range(index_n + 1, index_nplus1):
                if errorfile.dK1[i] != 0:
                    quad_fields.append(i)
                if errorfile.dX[i] != 0:
                    sext_trans.append(i)
                if errorfile.dS[i] != 0:
                    quad_missal.append(i)
                    
        else:
            for i in range(index_n + 1, len(errorfile.NAME)):
                if errorfile.dK1[i] != 0:
                    quad_fields.append(i)
                if errorfile.dX[i] != 0:
                    sext_trans.append(i)
                if errorfile.dS[i] != 0:
                    quad_missal.append(i)
                    
            for i in range(index_nplus1):  # ums Eck
                if errorfile.dK1[i] != 0:
                    quad_fields.append(i)
                if errorfile.dX[i] != 0:
                    sext_trans.append(i)
                if errorfile.dS[i] != 0:
                    quad_missal.append(i)
       
        list_of_Ks.append([quad_fields, sext_trans, quad_missal])

    
    if DEBUG:
        debugfile = open("debugfile" + plane, "w+")
        
    width = range_of_bpms / 2
   
    left_bpm = range(-width, 0)
    right_bpm = range(0 + 1, width + 1)
    BBA_combo = [[x, y] for x in left_bpm for y in left_bpm if x < y]
    ABB_combo = [[x, y] for x in right_bpm for y in right_bpm if x < y]
    BAB_combo = [[x, y] for x in left_bpm for y in right_bpm]
    
    startProgress("Calcuating betas")
    #--- commence loop over the BPMs
    for i in range(0, len(commonbpms)):
        
        if (i % 10) == 0:
            progress(float(i) / len(commonbpms) * 100.0)
            #--- RUN get_beta_from_phase_systematic_errors
        T_rows_Alfa, T_rows_Beta, betadata, alfadata, probed_bpm_name, M = get_beta_from_phase_systematic_errors(madTwiss, errorfile,
                                                                                               phase, plane, commonbpms, list_of_Ks, i,
                                                                                               range_of_bpms,
                                                                                               ABB_combo, BAB_combo, BBA_combo)
        T_Alfa = np.matrix(T_rows_Alfa)
        T_Beta = np.matrix(T_rows_Beta)
        
        if plane == 'H':
            betmdl1 = madTwiss.BETX[madTwiss.indx[probed_bpm_name]]
        elif plane == 'V':
            betmdl1 = madTwiss.BETY[madTwiss.indx[probed_bpm_name]]
        beti = DEFAULT_WRONG_BETA
        
        #--- calculate V and its inverse
        V_Beta = T_Beta * M * np.transpose(T_Beta)
        V_Alfa = T_Alfa * M * np.transpose(T_Alfa)
                 
        betas = []
        betas = [x[0] for x in betadata]
        
        try:
            V_Beta_inv = np.linalg.pinv(V_Beta)
        except LinAlgError:
            V_Beta_inv = np.zeros(V.shape)
            np.fill_diagonal(V_Beta_inv, 1.0)
            np.fill_diagonal(V_Beta, 1000.0)
            print "WARN: LinAlgEror in V_Beta_inv for " + probed_bpm_name
            
        try:
            V_Alfa_inv = np.linalg.pinv(V_Alfa)
        except LinAlgError:
            V_Alfa_inv = np.zeros(V.shape)
            np.fill_diagonal(V_Alfa, 1000.0)
            np.fill_diagonal(V_Alfa_inv, 1.0)
            print "WARN: LinAlgEror in V_Alfa_inv for " + probed_bpm_name
            
        len_w = len(betas)
       
        #--- calculate weights, weighted beta and beta_error
        # prepare calculating
        w = np.zeros(len_w)
        alferr = 0.0
        beterr = 0.0
        walfa = np.zeros(len_w)
        VBeta_inv_row_sum = V_Beta_inv.sum(axis=1, dtype='float')
        VBeta_inv_sum = V_Beta_inv.sum(dtype='float')
        VAlfa_inv_row_sum = V_Alfa_inv.sum(axis=1, dtype='float')
        VAlfa_inv_sum = V_Alfa_inv.sum(dtype='float')
        
            #--- calculate weights
        for i in range(len(w)):
            w[i] = VBeta_inv_row_sum[i] / VBeta_inv_sum
            walfa[i] = VAlfa_inv_row_sum[i] / VAlfa_inv_sum
        
        beti = float(sum([w[i] * betas[i] for i in range(len_w)]))
        alfi = float(sum([walfa[i] * alfadata[i][0] for i in range(len_w)]))
        
            #--- calculate errors
        for i in range(len_w):
            for j in range(len_w):
                beterr += w[i] * w[j] * V_Beta.item(i, j)
                alferr += walfa[i] * walfa[j] * V_Alfa.item(i, j)
                
        if beterr < 0:
            beterr = DEFAULT_WRONG_BETA
        else:
            beterr = np.sqrt(float(beterr))
        if alferr < 0:
            alferr = DEFAULT_WRONG_BETA
        else:
            alferr = np.sqrt(float(alferr))
                  
            #--- calculate correlation coefficient
        rho_alfa_beta = 0.0
        for i in range(M.shape[0]):
            betaterm = 0.0
            alfaterm = 0.0
            for k in range(len(betas)):
                betaterm += w[k] * T_rows_Beta[k][i]
                alfaterm -= walfa[k] * T_rows_Alfa[k][i]
            rho_alfa_beta += betaterm * alfaterm * M[i][i]
        rho_alfa_beta /= (beterr * alferr)
        
        if beterr > DEFAULT_WRONG_BETA and beterr > 100 * beti:
            beterr = DEFAULT_WRONG_BETA
 
        # so far, beta_syst and beta_stat are not separated
        beta[probed_bpm_name] = beti, 0, 0, beterr
        alfa[probed_bpm_name] = alfi, 0, 0, alferr
        corr[probed_bpm_name] = rho_alfa_beta
        delbeta.append((beti - betmdl1) / betmdl1)
                
        #--- DEBUG
        if DEBUG:
            debugfile.write("\n\nbegin BPM " + probed_bpm_name + " :\n")
            
            printMatrix(debugfile, T_Beta, "T_b")
            printMatrix(debugfile, T_Alfa, "T_Alfa")
            printMatrix(debugfile, M, "M")
       
            printMatrix(debugfile, V_Beta, "V")
            printMatrix(debugfile, V_Alfa, "V_a")
                    
            Zero = V_Beta * V_Beta_inv * V_Beta - V_Beta
            sumnorm = Zero.sum(dtype='float') / (Zero.shape[0] * Zero.shape[1])
            debugfile.write("Zeros sum norm: " + str(sumnorm) + "\n")
            
            printMatrix(debugfile, Zero, "Zero")
            Einheit = np.dot(V_Beta, V_Beta_inv)
            printMatrix(debugfile, Einheit, "V_inv*V")
            debugfile.write("\ncombinations:\t")
            for i in range(len_w):
                debugfile.write(betadata[i][3] + "\t")
            
            debugfile.write("\n")
            debugfile.write("\nweights:\t")
        
            for i in range(len_w):
                debugfile.write("{:.7f}".format(w[i]) + "\t")
            
            debugfile.write("\nbeta_values:\t")
            for i in range(len_w):
                debugfile.write(str(betas[i]) + "\t")
            
            debugfile.write("\n")
            debugfile.write("averaged beta: " + str(beti) + "\n")
            
            debugfile.write("\nalfa_values:\t")
            for i in range(len_w):
                debugfile.write(str(alfadata[i][0]) + "\t")
            debugfile.write("\n")
       
            debugfile.write("end\n")
        # END DEBUG
    endProgress()
     
    if DEBUG:
        debugfile.close()
    delbeta = np.array(delbeta)
    rmsbb = math.sqrt(np.average(delbeta * delbeta))
    return rmsbb, errors_method


def get_beta_from_phase_systematic_errors(madTwiss, errorfile, phase, plane, commonbpms,
                                          list_of_Ks, CurrentIndex, range_of_bpms,
                                          ABB_combo, BAB_combo, BBA_combo):
    '''
    Calculates the beta function at one BPM for all combinations.
    If less than 7 BPMs are available it will fall back to using only next neighbours.
    :Parameters:
        'madTwiss':twiss
            model twiss file
        'madTwiss':twiss
            final error twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'commonbpms':list
            intersection of common BPMs in measurement files and model
        'list_of_Ks':vector (of vectors)
            contains information about the errors the i-th entry in list_of_Ks yields the errors of all the lattice
            elements that come after the i-th BPM
        'CurrentIndex': integer
            current iterator in the loop of all BPMs
        'xyz_combo':vector
            contain all the BPM combinations for the three different cases ABB, BAB, BBA
    :Return: tupel(T_trans, betadata, bpm_name[probed_index], M)
        'T_Trans':np.matrix
            the T matrix to transform the variance matrix M into the covariance matrix V.
            In comparision with Andy's paper, the transposed is calculated, thus the name T_Trans
        'betadata':list
            contains calculated betas with information about the combination that was used
            consists of: betafunction, name of first used bpm, name of second used bpm, patternstring
            the pattern string is primarily for debugging purposes, to see which combination got which weight
            should be discarded afterwards
        'M':np-matrix
            variance matrix for all error kinds.
    '''
       
    RANGE = int(range_of_bpms)
    probed_index = int((RANGE - 1) / 2.)
      
    #--- Make a dictionary<int, string> to get the names of the BPMs
    bpm_name = {}
    for n in range(RANGE):
        bpm_name[n] = str.upper(commonbpms[(CurrentIndex + n) % len(commonbpms)][1])
        phase_err = {}
    if plane == 'H':
        for i in range(RANGE):
            if i < probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[i]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]])
            elif i > probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[probed_index], bpm_name[i]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[i]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]])
        phase_err[probed_index] = min([phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETX[madTwiss.indx[bpm_name[i]]]) for i in range(probed_index)] + [phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + 1 + i]])][1] / np.sqrt(1 + madTwiss.BETX[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETX[madTwiss.indx[bpm_name[probed_index + 1 + i]]]) for i in range(probed_index)])
    if plane == 'V':
        for i in range(RANGE):
            if i < probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[i]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]])
            if i > probed_index:
                phase_err[i] = phase["".join([plane, bpm_name[probed_index], bpm_name[i]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[i]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]])
        phase_err[probed_index] = min([phase["".join([plane, bpm_name[i], bpm_name[probed_index]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETY[madTwiss.indx[bpm_name[i]]]) for i in range(probed_index)] + [phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + 1 + i]])][1] / np.sqrt(1 + madTwiss.BETY[madTwiss.indx[bpm_name[probed_index]]] / madTwiss.BETY[madTwiss.indx[bpm_name[probed_index + 1 + i]]]) for i in range(probed_index)])

    #---- calculate the size of the M matrix = M_phi (+) M_K (+) M_X (+) M_S
        #---- the first block is M_phi the variance matrix of the phase errors
        
    if USE_TWOSTEPMATRIX:
        sizeOfMatrix = RANGE - 1
    else:
        sizeOfMatrix = RANGE
    
        #---- add the block M_K
    for k in range(RANGE):
        sizeOfMatrix += len(list_of_Ks[(CurrentIndex + k) % len(list_of_Ks)][0])
        
        #---- add the block M_X, the sextupole transversal missalignments
    for k in range(RANGE):
        sizeOfMatrix += len(list_of_Ks[(CurrentIndex + k) % len(list_of_Ks)][1])
    
        #---- add the block M_S, the quadrupole longitudinal missalignments
    for k in range(RANGE):
        sizeOfMatrix += len(list_of_Ks[(CurrentIndex + k) % len(list_of_Ks)][2])
        
        #---- add the block M_BPM, the BPM missalignment errors
    sizeOfMatrix += RANGE
          
    M = np.zeros([sizeOfMatrix, sizeOfMatrix])
    
    #---- assign the variances:
        #---- assign phase errors
        
    if USE_TWOSTEPMATRIX:
            
        for k in range(RANGE - 1):
            for l in range(RANGE - 1):
                if k == l and k < probed_index:
                    M[k][l] = TWOPI ** 2 * phase["".join([plane, bpm_name[probed_index], bpm_name[probed_index + k + 1]])][1] ** 2
                elif k == l and k >= probed_index:
                    M[k][l] = TWOPI ** 2 * phase["".join([plane, bpm_name[RANGE - 2 - k], bpm_name[probed_index]])][1] ** 2
                elif (k < probed_index and l >= probed_index) or (k >= probed_index and l < probed_index):
                    M[k][l] = -TWOPI ** 2 * phase_err[probed_index] ** 2
                else:
                    M[k][l] = TWOPI ** 2 * phase_err[probed_index] ** 2
        position = RANGE - 1
    else:
        for k in range(RANGE):
            M[k][k] = (TWOPI * phase_err[k]) ** 2
        position = RANGE

        #---- assign field errors
    for j in range(RANGE):
        index = (CurrentIndex + j) % len(list_of_Ks)
        for k in range(len(list_of_Ks[index][0])):
            M[k + position][k + position] = errorfile.dK1[list_of_Ks[index][0][k]] ** 2
        position += len(list_of_Ks[index][0])
        
        #---- assign sextupole transversal missalignments
    for j in range(RANGE):
        index = (CurrentIndex + j) % len(list_of_Ks)
        for k in range(len(list_of_Ks[index][1])):
            M[k + position][k + position] = errorfile.dX[list_of_Ks[index][1][k]] ** 2
        position += len(list_of_Ks[index][1])
        
        #---- assign longitudinal missalignments
    for j in range(RANGE):
        index = (CurrentIndex + j) % len(list_of_Ks)
        for k in range(len(list_of_Ks[index][2])):
            M[k + position][k + position] = errorfile.dS[list_of_Ks[index][2][k]] ** 2
        position += len(list_of_Ks[index][2])
        
        #---- assign BPM missalignments
    for j in range(RANGE):
        M[j + position][j + position] = errorfile.dS[errorfile.indx[bpm_name[j]]] ** 2
               
    #---- calculate betas_from_phase for the three cases.
    #     and add matrix_row for the given combination
    matrix_rows_Beta = []
    matrix_rows_Alfa = []
    
    betadata = []
    alfadata = []
    
    for n in BBA_combo:
        n0 = probed_index + n[0]
        n1 = probed_index + n[1]

        tbet, talf, alfstd, TrowBeta, TrowAlfa, patternstr = BetaFromPhase_BPM_BBA_with_systematicerrors(CurrentIndex,
                                                                                             bpm_name[n0], bpm_name[n1], bpm_name[probed_index], n0, n1, probed_index,
                                                                                             madTwiss, errorfile, phase, plane,
                                                                                             list_of_Ks, sizeOfMatrix, RANGE)
        betadata.append([tbet, bpm_name[n0], bpm_name[n1], patternstr])
        alfadata.append([talf, alfstd])
        matrix_rows_Beta.append(TrowBeta)
        matrix_rows_Alfa.append(TrowAlfa)

    for n in BAB_combo:
        n0 = probed_index + n[0]
        n1 = probed_index + n[1]

        tbet, talf, alfstd, TrowBeta, TrowAlfa, patternstr = BetaFromPhase_BPM_BAB_with_systematicerrors(CurrentIndex,
                                                                                          bpm_name[n0], bpm_name[probed_index], bpm_name[n1], n0, probed_index, n1,
                                                                                          madTwiss, errorfile, phase, plane,
                                                                                          list_of_Ks, sizeOfMatrix, RANGE)
        betadata.append([tbet, bpm_name[n0], bpm_name[n1], patternstr])
        alfadata.append([talf, alfstd])
        matrix_rows_Alfa.append(TrowAlfa)
        matrix_rows_Beta.append(TrowBeta)
             
    for n in ABB_combo:
        n0 = probed_index + n[0]
        n1 = probed_index + n[1]
        
        tbet, talf, alfstd, TrowBeta, TrowAlfa, patternstr = BetaFromPhase_BPM_ABB_with_systematicerrors(CurrentIndex,
                                                                                           bpm_name[probed_index], bpm_name[n0], bpm_name[n1], probed_index, n0, n1,
                                                                                           madTwiss, errorfile, phase, plane,
                                                                                           list_of_Ks, sizeOfMatrix, RANGE)
        betadata.append([tbet, bpm_name[n0], bpm_name[n1], patternstr])
        alfadata.append([talf, alfstd])
        matrix_rows_Alfa.append(TrowAlfa)
        matrix_rows_Beta.append(TrowBeta)
    
    return matrix_rows_Alfa, matrix_rows_Beta, betadata, alfadata, bpm_name[probed_index], M


def BetaFromPhase_BPM_ABB_with_systematicerrors(I, bn1, bn2, bn3, bi1, bi2, bi3, madTwiss, errorfile, phase, plane, list_of_Ks, matrixSize, RANGE):
    '''
       Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is left of the other two BPMs (case ABB)
    Calculates also the corresponding column of the T-matrix. (awegsche June 2016)
    
    :Parameters:
        'bn1,bn2,bn3':string
            the names of the three BPMs
        'bi1,bi2,bi3':string
            the indices of the three BPMs (important to find the errors)
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'list_of_Ks':vector (of vectors)
            contains information about the errors the i-th entry in list_of_Ks yields the errors of all the lattice
            elements that come after the i-th BPM
        'matrixSize':int
            the size of the T-matrix
        'RANGE':int
            the range of BPMs
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'alf':float
            calculated error on beta function at probed BPM
        '0':float
            0
        'T':numpy matrix
            column of the T-matrix
        'T_Alf':numpy matrix
            column of the T-matrix for alfa
        'patternstring':string
            [For Debugging] string which represents the combination used
            For example AxxBxB
    '''
    I1 = madTwiss.indx[bn1]
    I2 = madTwiss.indx[bn2]
    I3 = madTwiss.indx[bn3]
    
    ph2pi12 = TWOPI * phase["".join([plane, bn1, bn2])][0]
    ph2pi13 = TWOPI * phase["".join([plane, bn1, bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl12 = TWOPI * phase["".join([plane, bn1, bn2])][2]
    phmdl13 = TWOPI * phase["".join([plane, bn1, bn3])][2]
    if plane == 'H':
        betmdl1 = madTwiss.BETX[I1]
        betmdl2 = madTwiss.BETX[I2]
        betmdl3 = madTwiss.BETX[I3]
        alfmdl1 = madTwiss.ALFX[I1]
    elif plane == 'V':
        betmdl1 = madTwiss.BETY[madTwiss.indx[bn1]]
        betmdl2 = madTwiss.BETY[madTwiss.indx[bn2]]
        betmdl3 = madTwiss.BETY[madTwiss.indx[bn3]]
        alfmdl1 = madTwiss.ALFY[madTwiss.indx[bn1]]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    #--- Calculate beta
    denom = (1.0 / tan(phmdl12) - 1.0 / tan(phmdl13) + EPSILON) / betmdl1
    numer = 1.0 / tan(ph2pi12) - 1.0 / tan(ph2pi13)
    bet = numer / denom
    
    #--- Calculate alfa
    mdlterm = 1.0 / tan(phmdl12) + 1.0 / tan(phmdl13)
    denomalf = (mdlterm + 2.0 * alfmdl1) / betmdl1
    numeralf = 1.0 / tan(ph2pi12) + 1.0 / tan(ph2pi13)
    
    alf = 0.5 * (denomalf * bet - numeralf)
    
    T = [0] * matrixSize
    T_Alf = [0] * matrixSize
    
    phi_2 = madTwiss.MUX[I2] * TWOPI
    phi_3 = madTwiss.MUX[I3] * TWOPI
     
    s_i2 = sin(phmdl12) ** 2
    s_i3 = sin(phmdl13) ** 2
          
    #--- Phase Advance
  
    if USE_TWOSTEPMATRIX:
        phi_err1 = 1.0 / sin(phmdl12) ** 2 / denom
        phi_err2 = -1.0 / sin(phmdl13) ** 2 / denom
     
        T[bi2 - 1 - bi1] = phi_err1
        T[bi3 - 1 - bi1] = phi_err2
          
        T_Alf[bi2 - 1 - bi1] = A_FACT / sin(phmdl12) ** 2
        T_Alf[bi3 - 1 - bi1] = A_FACT / sin(phmdl13) ** 2
         
        T_Alf[bi2 - 1 - bi1] += 0.5 * phi_err1 * denomalf
        T_Alf[bi3 - 1 - bi1] += 0.5 * phi_err2 * denomalf
    else:
        
        phi_err1 = (1.0 / s_i2 - 1.0 / s_i3) / denom
        phi_err2 = (-1.0 / s_i2) / denom
        phi_err3 = 1.0 / s_i3 / denom
        
        T[bi1] = phi_err1
        T[bi2] = phi_err2
        T[bi3] = phi_err3
        
        T_Alf[bi1] = A_FACT * (-1.0 / s_i2 - 1.0 / s_i3 + phi_err1 * denomalf)
        T_Alf[bi2] = A_FACT * (1.0 / s_i2 + phi_err2 * denomalf)
        T_Alf[bi3] = A_FACT * (1.0 / s_i3 + phi_err3 * denomalf)
    
    frac = 1.0 / denom
    if plane == 'V':
        frac *= -1.0
        phi_2 = madTwiss.MUY[I2] * TWOPI
        phi_3 = madTwiss.MUY[I3] * TWOPI
        
    # the first columns belong to the phase errors:
    if USE_TWOSTEPMATRIX:
        K_offset = RANGE - 1
    else:
        K_offset = RANGE
        
    # then we jump to the first non-zero column in the K1 errors
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])
    K_begin = K_offset
       
    #--- Quad Fielderrors
    # assign T matrix elements for phase errors between BPM 1 and 2
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][0])):
            idx_k = list_of_Ks[which_k][0][w]
            err_beta = -frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += 0.5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += 0.5 * err_beta * denomalf
            
        K_offset += len(list_of_Ks[which_k][0])
    
    # go back because the second h_ij begins at 1
    # and assign the T matrix alements between BPM 1 and 3
    K_offset = K_begin
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][0])):
            idx_k = list_of_Ks[which_k][0][w]
            err_beta = frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += 0.5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T_Alf[K_offset + w] += 0.5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][0])
            
    #--- Sext Transverse Missalignments
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    K_begin = K_offset

    # assign T matrix elements for phase errors between BPM 1 and 2
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][1])):
            idx_k = list_of_Ks[which_k][1][w]
            err_beta = -SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -0.5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += 0.5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][1])
    
    # go back because the second h_ij begins at 1
    # and assign the T matrix alements between BPM 1 and 3
    K_offset = K_begin
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][1])):
            idx_k = list_of_Ks[which_k][1][w]
            err_beta = SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -0.5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T_Alf[K_offset + w] += 0.5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][1])
        
    #--- Quad Longitudinal Missalignments
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
    K_begin = K_offset
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][2])):
            idx_k = list_of_Ks[which_k][2][w]
            err_beta = -frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += 0.5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += 0.5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][2])
    
    # go back because the second h_ij begins at 1
    # and assign the T matrix alements between BPM 1 and 3
    K_offset = K_begin
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][2])):
            idx_k = list_of_Ks[which_k][2][w]
            T[K_offset + w] += frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T_Alf[K_offset + w] += 0.5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
        K_offset += len(list_of_Ks[which_k][2])
           
    #--- BPM Missalignments
    # jump to end of RANGE
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
          
    errindx1 = errorfile.indx[bn1]
    errindx2 = errorfile.indx[bn2]
    errindx3 = errorfile.indx[bn3]
      
    if errorfile.dS[errindx1] != 0:
        numerphi = -1.0 / (betmdl2 * sin(phmdl12) ** 2) + 1.0 / (betmdl3 * sin(phmdl13) ** 2)
        T[K_offset + bi1] = numerphi / denom
          
    if errorfile.dS[errindx2] != 0:
        numerphi = 1.0 / (betmdl2 * sin(phmdl12) ** 2)
        T[K_offset + bi2] = numerphi / denom
       
    if errorfile.dS[errindx3] != 0:
        numerphi = -1.0 / (betmdl3 * sin(phmdl13) ** 2)
        T[K_offset + bi3] = numerphi / denom
         
    patternstr = ["x"] * RANGE
    patternstr[bi1] = "A"
    patternstr[bi2] = "B"
    patternstr[bi3] = "B"

    return bet, alf, 0, T, T_Alf, "".join(patternstr)


def BetaFromPhase_BPM_BAB_with_systematicerrors(I, bn1, bn2, bn3, bi1, bi2, bi3, madTwiss, errorfile, phase, plane, list_of_Ks, matrixSize, RANGE):
    '''
    Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is betweeb the other two BPMs (case BAB)
    Calculates also the corresponding column of the T-matrix. (awegsche June 2016)
    
    :Parameters:
        'bn1,bn2,bn3':string
            the names of the three BPMs
        'bi1,bi2,bi3':string
            the indices of the three BPMs (important to find the errors)
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'matrixSize':int
            the size of the T-matrix
        'RANGE':int
            the range of BPMs
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'alf':float
            calculated error on beta function at probed BPM
        '0':float
            0
        'T':numpy matrix
            column of the T-matrix
        'T_Alf':numpy matrix
            column of the T-matrix for alfa
        'patternstring':string
            [For Debugging] string which represents the combination used
            For example AxxBxB
    '''
    
    I1 = madTwiss.indx[bn1]
    I2 = madTwiss.indx[bn2]
    I3 = madTwiss.indx[bn3]
    
    ph2pi21 = -TWOPI * phase["".join([plane, bn1, bn2])][0]
    ph2pi23 = TWOPI * phase["".join([plane, bn2, bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl21 = -TWOPI * phase["".join([plane, bn1, bn2])][2]
    phmdl23 = TWOPI * phase["".join([plane, bn2, bn3])][2]
    if plane == 'H':
        betmdl1 = madTwiss.BETX[I1]
        betmdl2 = madTwiss.BETX[I2]
        betmdl3 = madTwiss.BETX[I3]
        alpmdl2 = madTwiss.ALFX[I2]
    elif plane == 'V':
        betmdl1 = madTwiss.BETY[madTwiss.indx[bn1]]
        betmdl2 = madTwiss.BETY[madTwiss.indx[bn2]]
        betmdl3 = madTwiss.BETY[madTwiss.indx[bn3]]
        alpmdl2 = madTwiss.ALFY[I2]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    #--- Calculate beta
    denom = (1.0 / tan(phmdl21) - 1.0 / tan(phmdl23) + EPSILON) / betmdl2
    numer = 1.0 / tan(ph2pi21) - 1.0 / tan(ph2pi23)
    bet = numer / denom
    
    #--- Calculate alfa
    mdlterm = 1.0 / tan(phmdl21) + 1.0 / tan(phmdl23)
    denomalf = (mdlterm + 2.0 * alpmdl2) / betmdl2
    numeralf = 1.0 / tan(ph2pi21) + 1.0 / tan(ph2pi23)
    alf = 0.5 * (denomalf * bet - numeralf)
      
    s_i1 = sin(phmdl21) ** 2
    s_i3 = sin(phmdl23) ** 2
     
    T = [0] * (matrixSize)
    T_Alf = [0] * matrixSize
    
    #--- Phase Advance
    
    if USE_TWOSTEPMATRIX:
     
        phi_err1 = 1.0 / sin(phmdl21) ** 2 / denom
        phi_err2 = -1.0 / sin(phmdl23) ** 2 / denom
     
        T[RANGE - 2 - bi1] = phi_err1
        T[bi3 - 1 - bi2] = phi_err2
         
        T_Alf[RANGE - 2 - bi1] = A_FACT / sin(phmdl21) ** 2
        T_Alf[bi3 - 1 - bi2] = A_FACT / sin(phmdl23) ** 2  # sign
         
        T_Alf[RANGE - 2 - bi1] += 0.5 * phi_err1 * denomalf
        T_Alf[bi3 - 1 - bi2] += 0.5 * phi_err2 * denomalf
    else:
        phi_err1 = (-1.0 / s_i1) / denom
        phi_err2 = (1.0 / s_i1 - 1.0 / s_i3) / denom
        phi_err3 = 1.0 / s_i3 / denom
        
        T[bi1] = phi_err1
        T[bi2] = phi_err2
        T[bi3] = phi_err3
        
        T_Alf[bi1] = A_FACT * (1.0 / s_i1 + phi_err1 * denomalf)
        T_Alf[bi2] = A_FACT * (-1.0 / s_i1 - 1.0 / s_i3 + phi_err2 * denomalf)
        T_Alf[bi3] = A_FACT * (1.0 / s_i3 + phi_err3 * denomalf)
        
    phi_1 = madTwiss.MUX[I1] * TWOPI
    phi_3 = madTwiss.MUX[I3] * TWOPI
    
    frac = 1.0 / denom
    if plane == 'V':
        frac *= -1.0
        phi_1 = madTwiss.MUY[I1] * TWOPI
        phi_3 = madTwiss.MUY[I3] * TWOPI
    # the first columns belong to the phase errors:
    if USE_TWOSTEPMATRIX:
        K_offset = RANGE - 1
    else:
        K_offset = RANGE
    
    # then we jump to the first non-zero column in the K1 errors
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])

    #--- Quad Fielderrors
    # assign T matrix elements for phase errors between BPM 1 and 2
    for k in range(bi1, bi2):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][0])):
            idx_k = list_of_Ks[whichK][0][w]
            err_beta = frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf

        K_offset += len(list_of_Ks[whichK][0])
       
    # assign T matrix elements for phase errors between BPM 2 and 3
    # the two h_ij, h_12 and h_23 don't overlap, so we don't need to jump back.
    # K_offset is automatically set to the right value
    for k in range(bi2, bi3):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][0])):
            idx_k = list_of_Ks[whichK][0][w]
            err_beta = frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += .5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
                
        K_offset += len(list_of_Ks[whichK][0])
        
    #--- Sext Transverse Missalignments
    
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    #K_begin = K_offset
    
    for k in range(bi1, bi2):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][1])):
            idx_k = list_of_Ks[whichK][1][w]
            err_beta = -SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += .5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[whichK][1])
       
    # assign T matrix elements for phase errors between BPM 2 and 3
    # the two h_ij, h_12 and h_23 don't overlap, so we don't need to jump back.
    # K_offset is automatically set to the right value
    for k in range(bi2, bi3):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][1])):
            idx_k = list_of_Ks[whichK][1][w]
            err_beta = -SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
                
            #T_K.append(entry)
        K_offset += len(list_of_Ks[whichK][1])
 
    #--- Quad Longitudinal Missalignments
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
    
    for k in range(bi1, bi2):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][2])):
            idx_k = list_of_Ks[whichK][2][w]
            err_beta = frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T[K_offset + w] += -.5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[whichK][2])
       
    # assign T matrix elements for phase errors between BPM 2 and 3
    # the two h_ij, h_12 and h_23 don't overlap, so we don't need to jump back.
    # K_offset is automatically set to the right value
    for k in range(bi2, bi3):
        whichK = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[whichK][2])):
            idx_k = list_of_Ks[whichK][2][w]
            err_beta = frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += err_beta
            T[K_offset + w] += .5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_3) ** 2 / s_i3)
            T[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[whichK][2])
    
    #--- BPM Missalignments
    # jump to end of RANGE
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
          
    errindx1 = errorfile.indx[bn1]
    errindx2 = errorfile.indx[bn2]
    errindx3 = errorfile.indx[bn3]
      
    if errorfile.dS[errindx2] != 0:
        numerphi = -1.0 / (betmdl1 * sin(phmdl21) ** 2) + 1.0 / (betmdl3 * sin(phmdl23) ** 2)
        T[K_offset + bi2] = numerphi / denom
          
    if errorfile.dS[errindx1] != 0:
        numerphi = 1.0 / (betmdl1 * sin(phmdl21) ** 2)
        T[K_offset + bi1] = numerphi / denom
       
    if errorfile.dS[errindx3] != 0:
        numerphi = -1.0 / (betmdl3 * sin(phmdl23) ** 2)
        T[K_offset + bi3] = numerphi / denom
     
    patternstr = ["x"] * RANGE
    patternstr[bi1] = "B"
    patternstr[bi2] = "A"
    patternstr[bi3] = "B"

    return bet, alf, 0, T, T_Alf, "".join(patternstr)


def BetaFromPhase_BPM_BBA_with_systematicerrors(I, bn1, bn2, bn3, bi1, bi2, bi3, madTwiss, errorfile, phase, plane, list_of_Ks, matrixSize, RANGE):
    '''
        Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is right of the other two BPMs (case BBA)
    Calculates also the corresponding column of the T-matrix. (awegsche June 2016)
    
    :Parameters:
        'bn1,bn2,bn3':string
            the names of the three BPMs
        'bi1,bi2,bi3':string
            the indices of the three BPMs (important to find the errors)
        'madTwiss':twiss
            model twiss file
        'phase':dict
            measured phase advances
        'plane':string
            'H' or 'V'
        'matrixSize':int
            the size of the T-matrix
        'RANGE':int
            the range of BPMs
    :Return:tupel (bet,betstd,alf,alfstd)
        'bet':float
            calculated beta function at probed BPM
        'alf':float
            calculated error on beta function at probed BPM
        '0':float
            0
        'T':numpy matrix
            column of the T-matrix
        'T_Alf':numpy matrix
            column of the T-matrix for alfa
        'patternstring':string
            [For Debugging] string which represents the combination used
            For example AxxBxB
    '''
    
    I1 = madTwiss.indx[bn1]
    I2 = madTwiss.indx[bn2]
    I3 = madTwiss.indx[bn3]
    
    ph2pi32 = -TWOPI * phase["".join([plane, bn2, bn3])][0]
    ph2pi31 = -TWOPI * phase["".join([plane, bn1, bn3])][0]

    # Find the model transfer matrices for beta1
    phmdl32 = -TWOPI * phase["".join([plane, bn2, bn3])][2]
    phmdl31 = -TWOPI * phase["".join([plane, bn1, bn3])][2]
    if plane == 'H':
        betmdl1 = madTwiss.BETX[I1]
        betmdl2 = madTwiss.BETX[I2]
        betmdl3 = madTwiss.BETX[I3]
        alpmdl3 = madTwiss.ALFX[I3]
    elif plane == 'V':
        betmdl1 = madTwiss.BETY[I1]
        betmdl2 = madTwiss.BETY[I2]
        betmdl3 = madTwiss.BETY[I3]
        alpmdl3 = madTwiss.ALFY[I3]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)
        
    #--- Calculate beta
    denom = (1.0 / tan(phmdl32) - 1.0 / tan(phmdl31) + EPSILON) / betmdl3
    numer = 1.0 / tan(ph2pi32) - 1.0 / tan(ph2pi31)
    bet = numer / denom
  
    #--- Calculate alfa
    mdlterm = 1.0 / tan(phmdl32) + 1.0 / tan(phmdl31)
    denomalf = (mdlterm + 2.0 * alpmdl3) / betmdl3
    numeralf = 1.0 / tan(ph2pi32) + 1.0 / tan(ph2pi31)
    alf = 0.5 * (denomalf * bet - numeralf)
    
    s_i2 = sin(phmdl32) ** 2
    s_i1 = sin(phmdl31) ** 2
    
    T = [0] * matrixSize
    T_Alf = [0] * matrixSize
        
    #--- Phase Advance
   
    if USE_TWOSTEPMATRIX:
        phi_err1 = -1.0 / sin(phmdl31) ** 2 / denom
        phi_err2 = 1.0 / sin(phmdl32) ** 2 / denom
     
        T[RANGE - 2 - bi1] = phi_err1
        T[RANGE - 2 - bi2] = phi_err2
            
        T_Alf[RANGE - 2 - bi1] = A_FACT / sin(phmdl31) ** 2   # sign
        T_Alf[RANGE - 2 - bi2] = A_FACT / sin(phmdl32) ** 2   # sign
         
        T_Alf[RANGE - 2 - bi1] += 0.5 * phi_err1 * denomalf
        T_Alf[RANGE - 2 - bi2] += 0.5 * phi_err2 * denomalf
    else:
        phi_err1 = 1.0 / s_i1 / denom
        phi_err2 = -1.0 / s_i2 / denom
        phi_err3 = -(1.0 / s_i1 - 1.0 / s_i2) / denom
       
        T[bi1] = phi_err1
        T[bi2] = phi_err2
        T[bi3] = phi_err3
        
        T_Alf[bi1] = A_FACT * (1.0 / s_i1 + phi_err1 * denomalf)
        T_Alf[bi2] = A_FACT * (1.0 / s_i2 + phi_err2 * denomalf)
        T_Alf[bi3] = A_FACT * (-1.0 / s_i1 - 1.0 / s_i2 + phi_err3 * denomalf)
                               
    phi_2 = madTwiss.MUX[I2] * TWOPI
    phi_1 = madTwiss.MUX[I1] * TWOPI
    
    frac = 1.0 / denom
    if plane == 'V':
        frac *= -1.0
        phi_2 = madTwiss.MUY[I2] * TWOPI
        phi_1 = madTwiss.MUY[I1] * TWOPI
           
    # the first columns belong to the phase errors:
    if USE_TWOSTEPMATRIX:
        K_offset = RANGE - 1
    else:
        K_offset = RANGE
        
    #--- Quad Fielderrors
    # then we jump to the first non-zero column in the K1 errors
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])
    K_begin = K_offset
    #K_offset = RANGE
    
    # assign T matrix elements for phase errors between BPM 1 and 3
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][0])):
            idx_k = list_of_Ks[which_k][0][w]
            err_beta = -frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][0])
    
    # go back because the second h_ij begins at 2
    # so we have to find the position of BPM2 in the matrix
    K_offset = K_begin
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        K_offset += len(list_of_Ks[which_k][0])
    # and assign the T matrix alements between BPM 1 and 3
    for k in range(bi2, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][0])):
            idx_k = list_of_Ks[which_k][0][w]
            err_beta = frac * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][0])
    
    #--- Sext Trasverse Missalignments
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][0])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    K_begin = K_offset
    
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][1])):
            idx_k = list_of_Ks[which_k][1][w]
            err_beta = SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += .5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][1])
        
    K_offset = K_begin
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        K_offset += len(list_of_Ks[which_k][1])
    # and assign the T matrix alements between BPM 1 and 3
    for k in range(bi2, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][1])):
            idx_k = list_of_Ks[which_k][1][w]
            err_beta = -SEXT_FACT * frac * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += .5 * SEXT_FACT * errorfile.K2L[idx_k] * errorfile.BET[idx_k] * (sin(errorfile.MU[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][1])
    
    #--- Quad Longitudinal Missalignments
    # jump to the end of RANGE then to b1
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][1])
    for k in range(bi1):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
    K_begin = K_offset
      
    for k in range(bi1, bi3):
        which_k = (k + I) % len(list_of_Ks)
        for w in range(len(list_of_Ks[which_k][2])):
            idx_k = list_of_Ks[which_k][2][w]
            err_beta = -frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_1) ** 2 / s_i1)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][2])
        
    K_offset = K_begin
    for k in range(bi1, bi2):
        which_k = (k + I) % len(list_of_Ks)
        K_offset += len(list_of_Ks[which_k][2])
    # and assign the T matrix alements between BPM 1 and 3
    for k in range(bi2, bi3):
        which_k = (k + I) % len(list_of_Ks)
        
        for w in range(len(list_of_Ks[which_k][2])):
            idx_k = list_of_Ks[which_k][2][w]
            err_beta = frac * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T[K_offset + w] += err_beta
            T_Alf[K_offset + w] += -.5 * errorfile.K1LEND[idx_k] * errorfile.BETEND[idx_k] * (sin(errorfile.MUEND[idx_k] * TWOPI - phi_2) ** 2 / s_i2)
            T_Alf[K_offset + w] += .5 * err_beta * denomalf
        K_offset += len(list_of_Ks[which_k][2])
        
    #--- BPM Missalignments
    # jump to end of RANGE
    for k in range(bi3, RANGE):
        K_offset += len(list_of_Ks[(k + I) % len(list_of_Ks)][2])
          
    errindx1 = errorfile.indx[bn1]
    errindx2 = errorfile.indx[bn2]
    errindx3 = errorfile.indx[bn3]
      
    if errorfile.dS[errindx3] != 0:
        numerphi = -1.0 / (betmdl2 * sin(phmdl32) ** 2) + 1.0 / (betmdl1 * sin(phmdl31) ** 2)
        T[K_offset + bi3] = numerphi / denom
          
    if errorfile.dS[errindx2] != 0:
        numerphi = 1.0 / (betmdl2 * sin(phmdl32) ** 2)
        T[K_offset + bi2] = numerphi / denom
       
    if errorfile.dS[errindx1] != 0:
        numerphi = -1.0 / (betmdl1 * sin(phmdl31) ** 2)
        T[K_offset + bi1] = numerphi / denom
            
    patternstr = ["x"] * RANGE
    patternstr[bi1] = "B"
    patternstr[bi2] = "B"
    patternstr[bi3] = "A"

    return bet, alf, 0, T, T_Alf, "".join(patternstr)

#===================================================================================================
#--- ac-dipole stuff
#===================================================================================================


def _get_free_beta(modelfree, modelac, betal, rmsbb, alfal, bpms, plane):  # to check "+"
    if DEBUG:
        print "Calculating free beta using model"
    bpms = Utilities.bpm.model_intersect(bpms, modelfree)
    bpms = Utilities.bpm.model_intersect(bpms, modelac)
    betan = {}
    alfan = {}
    for bpma in bpms:
        bpm = bpma[1].upper()
        beta, betsys, betstat, beterr = betal[bpm]
        alfa, alfsys, alfstat, alferr = alfal[bpm]

        if plane == "H":
            betmf = modelfree.BETX[modelfree.indx[bpm]]
            betma = modelac.BETX[modelac.indx[bpm]]
            bb = (betma - betmf) / betmf
            alfmf = modelfree.ALFX[modelfree.indx[bpm]]
            alfma = modelac.ALFX[modelac.indx[bpm]]
            aa = (alfma - alfmf) / alfmf
        else:
            betmf = modelfree.BETY[modelfree.indx[bpm]]
            betma = modelac.BETY[modelac.indx[bpm]]
            alfmf = modelfree.ALFY[modelfree.indx[bpm]]
            alfma = modelac.ALFY[modelac.indx[bpm]]
            bb = (betma - betmf) / betmf
            aa = (alfma - alfmf) / alfmf

        betan[bpm] = beta * (1 + bb), betsys, betstat, beterr  # has to be plus!
        alfan[bpm] = alfa * (1 + aa), alfsys, alfstat, alferr

    return betan, rmsbb, alfan, bpms


def _get_free_amp_beta(betai, rmsbb, bpms, inv_j, mad_ac, mad_twiss, plane):
    #
    # Why difference in betabeta calculation ??
    #
    #
    betas = {}

    if DEBUG:
        print "Calculating free beta from amplitude using model"

    for bpm in bpms:
        bpmm = bpm[1].upper()
        beta = betai[bpmm][0]

        if plane == "H":
            betmf = mad_twiss.BETX[mad_twiss.indx[bpmm]]
            betma = mad_ac.BETX[mad_ac.indx[bpmm]]
            bb = (betmf - betma) / betma
        else:
            betmf = mad_twiss.BETY[mad_twiss.indx[bpmm]]
            betma = mad_ac.BETY[mad_ac.indx[bpmm]]
            bb = (betmf - betma) / betma

        betas[bpmm] = [beta * (1.0 + bb), betai[bpmm][1], betai[bpmm][2]]

    return betas, rmsbb, bpms, inv_j

#=======================================================================================================================
#--- Helper / Debug Functions
#=======================================================================================================================


def create_errorfile(errordefspath, model, twiss_full, twiss_full_centre, commonbpms, plane):
    '''
    Creates a file in Twiss format that contains the information about the expected errors for each element .
    
    There has to be an error definition file called "errordefs".
    
    There has to be a twiss model file called "twiss_full.dat" with all the elments in the lattice (also drift spaces) which contains the
    following columns:
    NAME, S, BETX, BETY, MUX, MUY, K1L, K2L
    '''
    
    if errordefspath == None:
        return None
    
    bpms = []
    for bpm in commonbpms:
        bpms.append(bpm[1])
    
    print "\33[36mSTART\33[0m Creating errorfile"
    
    # if something in loading / writing the files goes wrong, return None
    # which forces the script to fall back to 3bpm
    try:
        definitions = Python_Classes4MAD.metaclass.twiss(errordefspath)
        filename = "error_elements_" + plane + ".dat"
        errorfile = Utilities.tfs_file_writer.TfsFileWriter(filename)
    except:
        return None
     
    errorfile.add_column_names(     ["NAME",    "BET",  "BETEND",   "MU",   "MUEND",    "dK1",  "K1L",  "K1LEND",   "K2L",  "dX",   "dS"])  #@IgnorePep8
    errorfile.add_column_datatypes( ["%s",      "%le",  "%le",      "%le",  "%le",      "%le",  "%le",  "%le",      "%le",  "%le",  "%le"])  #@IgnorePep8
    
    mainfield = definitions.RELATIVE == "MAINFIELD"
    
    regex_list = []
    for pattern in definitions.PATTERN:
        regex_list.append(re.compile(pattern))

    # OLD:
    for index_twissfull in range(len(twiss_full.NAME)):

        BET = twiss_full_centre.BETX[index_twissfull]
        MU = twiss_full_centre.MUX[index_twissfull]

        if plane == 'V':
            BET = twiss_full_centre.BETY[index_twissfull]
            MU = twiss_full_centre.MUY[index_twissfull]
            
        BET_end = twiss_full.BETX[index_twissfull]
        MU_end = twiss_full.MUX[index_twissfull]
        BETminus1_end = twiss_full.BETX[index_twissfull - 1]
        MUminus1_end = twiss_full.MUX[index_twissfull - 1]

        if plane == 'V':
            BET_end = twiss_full.BETY[index_twissfull]
            MU_end = twiss_full.MUY[index_twissfull]
            BETminus1_end = twiss_full.BETY[index_twissfull - 1]
            MUminus1_end = twiss_full.MUY[index_twissfull - 1]

        found = False
        for index_defs in range(len(definitions.PATTERN)):
            regex = regex_list[index_defs]
            if regex.match(twiss_full.NAME[index_twissfull]):

                found = True
                isQuad = False
                MF = 1000
                if mainfield:
                    if definitions.MAINFIELD[index_defs] == "QUAD":
                        MF = twiss_full_centre.K1L[index_twissfull]
                        isQuad = True
                    elif definitions.MAINFIELD[index_defs] == "SEXT":
                        MF = twiss_full_centre.K2L[index_twissfull]
                    elif definitions.MAINFIELD[index_defs] == "DIPL":
                        MF = twiss_full_centre.K0L[index_twissfull]
                else:
                    MF = twiss_full.K1L[index_twissfull]
               
                errorfile.add_table_row([
                                         twiss_full.NAME[index_twissfull],
                                         BET,
                                         BET_end,
                                         MU,
                                         MU_end,
                                         definitions.dK1[index_defs] * MF,
                                         twiss_full_centre.K1L[index_twissfull],
                                         twiss_full.K1L[index_twissfull],
                                         twiss_full_centre.K2L[index_twissfull],
                                         definitions.dX[index_defs],
                                         definitions.dS[index_defs]
                                         ])
                if definitions.dS[index_defs] != 0 and isQuad:
                    errorfile.add_table_row([
                                             twiss_full.NAME[index_twissfull - 1],
                                             0,     # BET
                                             BETminus1_end,
                                             0,     # MU
                                             MUminus1_end,
                                             0,     # dK1,
                                             0,     # K1L,
                                             - twiss_full.K1L[index_twissfull],  # same index
                                             0,     # K2L
                                             0,     # dX
                                             definitions.dS[index_defs]  # here no -1 because the same dS applies
                                             ])

        if not found:  # if element doesn't have any error add it nevertheless if it is a BPM
            if twiss_full.NAME[index_twissfull] in bpms:
                index_model = model.indx[twiss_full.NAME[index_twissfull]]
                errorfile.add_table_row([
                                         model.NAME[index_model],
                                         BET,
                                         0,  # BETEND
                                         MU,
                                         0,  # MUEND
                                         0,  # dK1
                                         0,  # K1L
                                         0,  # K1LEND
                                         0,  # K2L
                                         0,  # dX
                                         0   # dS
                                         ])
    errorfile.write_to_file(True)

    print "DONE creating errofile."

    return Python_Classes4MAD.metaclass.twiss(filename)


def printMatrix(debugfile, M, name):
    debugfile.write("begin Matrix " + name + "\n" + str(M.shape[0]) + " " + str(M.shape[1]) + "\n")

    np.savetxt(debugfile, M, fmt="%13.5e")
    debugfile.write("\nend\n")
