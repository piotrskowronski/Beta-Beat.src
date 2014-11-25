'''
This script calculates the bet_deviations.npy binary file to improve the betas calculation.

It uses two madx mask: error_table.mask and job.systematic.mask, that must be processed before running this script.
The labels to be replaced are:

- %PATH -> The path to the modifiers.madx file
- %QMX and %QMY -> The tunes of the beam for that optic.
- %ENERGY -> The energy of the beam. It must be: 0.35TeV, 3.5TeV, 4TeV or 6.5TeV.

The modified masks must be placed in the same directory where the model is.

@author: alangner, jcoellod
'''

import __init__  # @UnusedImport
import os
import multiprocessing
import time
import numpy as np
from optparse import OptionParser
from Utilities import iotools
from Python_Classes4MAD import madxrunner, metaclass
import math
import sys

CURRENT_PATH = os.path.abspath(os.path.dirname(__file__))

NUM_SIMULATIONS = 1000  # Default number of simulations, used if no input argument is found
NUM_PROCESSES = multiprocessing.cpu_count()  # Default number of processes to use in simulations


def _parse_args():
    parser = OptionParser()
    parser.add_option("-m", "--model",
                    help="Model twiss file to use.",
                    metavar="model", dest="model_twiss")
    parser.add_option("-o", "--output",
                    help="Output directory for the results.",
                    metavar="output", default="", dest="output_dir")
    parser.add_option("-n", "--numsim",
                    help="Number of simulations to run",
                    metavar="numsim", default=NUM_SIMULATIONS, dest="num_simulations")
    parser.add_option("-p", "--processes",
                    help="Number of parallel processes to use in the simulation.",
                    metavar="numproc", default=NUM_PROCESSES, dest="num_processes")
    parser.add_option("-b", "--beam",
                    help="Beam to use, either LHCB1 or LHCB2.",
                    metavar="BEAM", dest="beam")
    options, _ = parser.parse_args()

    if options.output_dir == "":
        options.output_dir = os.path.dirname(options.model_twiss)
    if not os.path.isfile(os.path.join(os.path.dirname(options.model_twiss), "error_table.mask")):
        print >> sys.stderr, "Cannot find the error_table.mask file in the model directory."
        sys.exit(-1)
    if not os.path.isfile(os.path.join(os.path.dirname(options.model_twiss), "job.systematic.mask")):
        print >> sys.stderr, "Cannot find the job.systematic.mask file in the model directory."
        sys.exit(-1)
    if options.beam is None:
        print >> sys.stderr, "Beam sequence must be defined, it must be LHCB1 or LHCB2."
        sys.exit(-1)
    beam = options.beam.upper().replace("LHC", "")
    if(beam not in ["B1", "B2"]):
        print >> sys.stderr, "Incorrect beam sequence, it must be LHCB1 or LHCB2."
        sys.exit(-1)
    return options.model_twiss, int(options.num_simulations), int(options.num_processes), options.output_dir, beam


def get_systematic_errors(model_twiss, num_simulations, num_processes, output_dir, beam):
    print "Started systematic error script, using " + str(num_processes) + " processes for " + str(num_simulations) + " simulations"
    model_dir_path = os.path.dirname(model_twiss)
    run_data_path = os.path.join(output_dir, "RUN_DATA")
    errors_path = os.path.join(CURRENT_PATH, "..", "..", "MODEL", "LHC" + beam, "dipole_b2_errors")
    iotools.create_dirs(run_data_path)
    try:
        os.symlink("/afs/cern.ch/eng/lhc/optics/V6.503", "db5")
    except(OSError):
        pass

    pool = multiprocessing.Pool(processes=num_processes)

    print "Running simulations..."
    start_time = time.time()
    times = _run_parallel_simulations(run_data_path, model_dir_path, num_simulations, errors_path, beam, pool)
    _show_time_statistics(times)
    end_time = time.time()
    print "Done (" + str(end_time - start_time) + " seconds)\n"

    try:
        os.unlink("db5")
        os.unlink("ats")
    except(OSError):
        pass

    print "Calculating systematic error bars..."
    start_time = time.time()
    _parallel_get_systematic_errors_binary_file(model_twiss, run_data_path, output_dir, pool, num_simulations)
    end_time = time.time()
    print "Done (" + str(end_time - start_time) + " seconds)\n"

    print "Cleaning output directory..."
    iotools.delete_item(run_data_path)
    print "All done."


def _run_parallel_simulations(run_data_path, model_dir_path, num_simulations, errors_path, beam, pool):
    times = []
    args = [(seed, run_data_path, model_dir_path, errors_path, beam) for seed in range(1, num_simulations + 1)]
    tasks = pool.map_async(_run_single_madx_simulation, args, callback=times.append)
    tasks.wait()
    return times


def _run_single_madx_simulation(seed_path_tuple):
    seed = seed_path_tuple[0]
    run_data_path = seed_path_tuple[1]
    model_dir_path = seed_path_tuple[2]
    errors_path = seed_path_tuple[3]
    beam = seed_path_tuple[4]
    madx_job = ""
    with open(os.path.join(model_dir_path, 'job.systematic.mask'), 'r') as infile:
        for line in infile:
            err_num = str((seed % 60) + 1).zfill(4)
            new_line = line

            if line.startswith('eoption, seed= SEEDR + 50  ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(1 + seed * 9) + '  ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 2    ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(2 + seed * 9) + '    ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 4    ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(3 + seed * 9) + '    ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 5    ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(4 + seed * 9) + '    ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 6    ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(5 + seed * 9) + '    ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 7    ; exec SetEfcomp_Q;'):
                new_line = 'eoption, seed= SEEDR + ' + str(6 + seed * 9) + '    ; exec SetEfcomp_Q;'
            elif line.startswith('eoption, seed= SEEDR + 8;'):
                new_line = 'eoption, seed= SEEDR + ' + str(7 + seed * 9) + ';'
            elif line.startswith('eoption, seed= SEEDR + 9;'):
                new_line = 'eoption, seed= SEEDR + ' + str(8 + seed * 9) + ';'
            elif line.startswith('eoption, seed= SEEDR + 10;'):
                new_line = 'eoption, seed= SEEDR + ' + str(9 + seed * 9) + ';'

            new_line = new_line.replace("%ERR_NUM", str(err_num))
            new_line = new_line.replace("%SEED", str(seed))
            new_line = new_line.replace("%RUN_DATA_PATH", run_data_path)
            new_line = new_line.replace("%ERRORS_PATH", errors_path)
            new_line = new_line.replace("%BEAM", beam)
            madx_job += new_line + "\n"

    start_time = time.time()
    madxrunner.runForInputString(madx_job, stdout=open(os.devnull, "w"))
    end_time = time.time()
    return end_time - start_time


def _show_time_statistics(times):
    times = times[0]
    average_time = 0
    max_time = 0
    min_time = sys.float_info.max
    for time in times:
        average_time += time
        if time > max_time:
            max_time = time
        if time < min_time:
            min_time = time
    average_time = average_time / len(times)
    print "Average simulation time: " + str(average_time) + " seconds"
    print "Max simulation time: " + str(max_time) + " seconds"
    print "Min simulation time: " + str(min_time) + " seconds"


def _parallel_get_systematic_errors_binary_file(model_twiss_path, run_data_path, output_path, pool, num_simulations):
    model_twiss = metaclass.twiss(model_twiss_path)

    list_of_bpm = []
    for i in model_twiss.NAME:
        if "BPM" in i and i not in list_of_bpm:
            list_of_bpm.append(i)

    final_list = [{}, {}, 0]  # This list is used to pass the parameters "by reference" to the callback method

    args = [(run_data_path, model_twiss, list_of_bpm, sim_num) for sim_num in range(1, num_simulations + 1)]
    for run_data_path, model_twiss, list_of_bpm, sim_num in args:
        pool.apply_async(_get_error_bar_for_single_simulation, (run_data_path, model_twiss, list_of_bpm, sim_num),
                         callback=lambda result: _merge_betas_dict(final_list, result))
    pool.close()
    pool.join()

    sys.stdout.write("\n")

    final_beta_hor, final_beta_ver, final_num_valid_data = final_list

    for key, value in final_beta_hor.iteritems():
        final_beta_hor[key] = np.sqrt(value / final_num_valid_data)
    for key, value in final_beta_ver.iteritems():
        final_beta_ver[key] = np.sqrt(value / final_num_valid_data)

    np.save(os.path.join(output_path, 'bet_deviations'), [final_beta_hor, final_beta_ver])


def _get_error_bar_for_single_simulation(run_data_path, model_twiss, list_of_bpm, sim_num):
    beta_hor = {}
    beta_ver = {}
    num_valid_data = 0
    try:
        error_twiss = metaclass.twiss(os.path.join(run_data_path, 'twiss' + str(sim_num) + '.dat'))
        for probed_bpm in range(len(list_of_bpm)):
            for i in range(5):
                for j in range(5 - i):
                    beta_hor[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 6 + i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 1 - j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_right(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                               list_of_bpm[(probed_bpm - 6 + i) % len(list_of_bpm)],
                                                               list_of_bpm[(probed_bpm - 1 - j) % len(list_of_bpm)],
                                                               model_twiss, error_twiss, 'H') -
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2

                    beta_ver[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 6 + i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 1 - j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_right(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                               list_of_bpm[(probed_bpm - 6 + i) % len(list_of_bpm)],
                                                               list_of_bpm[(probed_bpm - 1 - j) % len(list_of_bpm)],
                                                               model_twiss, error_twiss, 'V') -
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2

                    beta_hor[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 6 - i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_left(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                              list_of_bpm[(probed_bpm + 6 - i) % len(list_of_bpm)],
                                                              list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)],
                                                              model_twiss, error_twiss, 'H') -
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2

                    beta_ver[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 6 - i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_left(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                              list_of_bpm[(probed_bpm + 6 - i) % len(list_of_bpm)],
                                                              list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)],
                                                              model_twiss, error_twiss, 'V') -
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2

            for i in range(6):
                for j in range(6):
                    beta_hor[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 1 - i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_mid(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                             list_of_bpm[(probed_bpm - 1 - i) % len(list_of_bpm)],
                                                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)],
                                                             model_twiss, error_twiss, 'H') -
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETX[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2

                    beta_ver[list_of_bpm[(probed_bpm) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm - 1 - i) % len(list_of_bpm)] +
                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)]] = \
                                      ((BetaFromPhase_BPM_mid(list_of_bpm[(probed_bpm) % len(list_of_bpm)],
                                                             list_of_bpm[(probed_bpm - 1 - i) % len(list_of_bpm)],
                                                             list_of_bpm[(probed_bpm + 1 + j) % len(list_of_bpm)],
                                                             model_twiss, error_twiss, 'V') -
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) /
                                       error_twiss.BETY[error_twiss.indx[list_of_bpm[probed_bpm]]]) ** 2
        num_valid_data = num_valid_data + 1
    except:
        print >> sys.stderr, "Cannot read ", "twiss" + str(sim_num) + ".dat, something went wrong."
    return beta_hor, beta_ver, num_valid_data


def _merge_betas_dict(final_list, result):
    beta_hor, beta_ver, num_valid_data = result
    for key, value in beta_hor.iteritems():
        if not key in final_list[0]:
            final_list[0][key] = value
        else:
            final_list[0][key] += value
    for key, value in beta_ver.iteritems():
        if not key in final_list[1]:
            final_list[1][key] = value
        else:
            final_list[1][key] += value
    final_list[2] += num_valid_data
    sys.stdout.write("Done for: " + str(final_list[2]) + " files.\r")
    sys.stdout.flush()


def _TEST_compare_with_template(dict_list):
    template = np.load(os.path.join(CURRENT_PATH, "test_bet_deviations_good.npy"))
    t_beta_hor = template[0]
    t_beta_ver = template[1]
    beta_hor = dict_list[0]
    beta_ver = dict_list[1]
    n = 0
    for key, value in beta_hor.iteritems():
        if abs(t_beta_hor[key] - value) > 0.000000000001:
            n += 1
            print "Error for hor values: "
            print repr(t_beta_hor[key])
            print repr(value)
            print abs(t_beta_hor[key] - value)
    for key, value in beta_ver.iteritems():
        if abs(t_beta_ver[key] - value) > 0.000000000001:
            print "Error for ver values: "
            print repr(t_beta_hor[key])
            print repr(value)
            print abs(t_beta_ver[key] - value)
    print n


def BetaFromPhase_BPM_left(bn1, bn3, bn2, MADTwiss, ERRTwiss, plane):
    '''
    Calculates the beta/alfa function and their errors using the
    phase advance between three BPMs for the case that the probed BPM is left of the other two BPMs
    :Parameters:
        'bn1':string
            Name of probed BPM
        'bn2':string
            Name of first BPM right of the probed BPM
        'bn3':string
            Name of second BPM right of the probed BPM
        'MADTwiss':twiss
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

    if plane == 'H':
        ph2pi12 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn2]] - ERRTwiss.MUX[ERRTwiss.indx[bn1]]) % ERRTwiss.Q1
        ph2pi13 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn3]] - ERRTwiss.MUX[ERRTwiss.indx[bn1]]) % ERRTwiss.Q1
        phmdl12 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn2]] - MADTwiss.MUX[MADTwiss.indx[bn1]]) % MADTwiss.Q1
        phmdl13 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn3]] - MADTwiss.MUX[MADTwiss.indx[bn1]]) % MADTwiss.Q1

        betmdl1 = MADTwiss.BETX[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETX[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETX[MADTwiss.indx[bn3]]
        alpmdl1 = MADTwiss.ALFX[MADTwiss.indx[bn1]]
    elif plane == 'V':
        ph2pi12 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn2]] - ERRTwiss.MUY[ERRTwiss.indx[bn1]]) % ERRTwiss.Q2
        ph2pi13 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn3]] - ERRTwiss.MUY[ERRTwiss.indx[bn1]]) % ERRTwiss.Q2
        phmdl12 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn2]] - MADTwiss.MUY[MADTwiss.indx[bn1]]) % MADTwiss.Q2
        phmdl13 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn3]] - MADTwiss.MUY[MADTwiss.indx[bn1]]) % MADTwiss.Q2

        betmdl1 = MADTwiss.BETY[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETY[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETY[MADTwiss.indx[bn3]]
        alpmdl1 = MADTwiss.ALFY[MADTwiss.indx[bn1]]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta1 and alpha1 from phases assuming model transfer matrix
    # Matrix M: BPM1-> BPM2
    # Matrix N: BPM1-> BPM3
    M11 = math.sqrt(betmdl2 / betmdl1) * (np.cos(phmdl12) + alpmdl1 * np.sin(phmdl12))
    M12 = math.sqrt(betmdl1 * betmdl2) * np.sin(phmdl12)
    N11 = math.sqrt(betmdl3 / betmdl1) * (np.cos(phmdl13) + alpmdl1 * np.sin(phmdl13))
    N12 = math.sqrt(betmdl1 * betmdl3) * np.sin(phmdl13)

    denom = M11 / M12 - N11 / N12 + 1e-16
    numer = 1 / np.tan(ph2pi12) - 1 / np.tan(ph2pi13)
    bet = numer / denom

    return bet


def BetaFromPhase_BPM_mid(bn2, bn1, bn3, MADTwiss, ERRTwiss, plane):
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
        'MADTwiss':twiss
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
    if plane == 'H':
        ph2pi12 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn2]] - ERRTwiss.MUX[ERRTwiss.indx[bn1]]) % ERRTwiss.Q1
        ph2pi23 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn3]] - ERRTwiss.MUX[ERRTwiss.indx[bn2]]) % ERRTwiss.Q1
        phmdl12 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn2]] - MADTwiss.MUX[MADTwiss.indx[bn1]]) % MADTwiss.Q1
        phmdl23 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn3]] - MADTwiss.MUX[MADTwiss.indx[bn2]]) % MADTwiss.Q1

        betmdl1 = MADTwiss.BETX[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETX[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETX[MADTwiss.indx[bn3]]
        alpmdl2 = MADTwiss.ALFX[MADTwiss.indx[bn2]]
    elif plane == 'V':
        ph2pi12 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn2]] - ERRTwiss.MUY[ERRTwiss.indx[bn1]]) % ERRTwiss.Q2
        ph2pi23 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn3]] - ERRTwiss.MUY[ERRTwiss.indx[bn2]]) % ERRTwiss.Q2
        phmdl12 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn2]] - MADTwiss.MUY[MADTwiss.indx[bn1]]) % MADTwiss.Q2
        phmdl23 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn3]] - MADTwiss.MUY[MADTwiss.indx[bn2]]) % MADTwiss.Q2

        betmdl1 = MADTwiss.BETY[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETY[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETY[MADTwiss.indx[bn3]]
        alpmdl2 = MADTwiss.ALFY[MADTwiss.indx[bn2]]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta2 and alpha2 from phases assuming model transfer matrix
    # Matrix M: BPM1-> BPM2
    # Matrix N: BPM2-> BPM3
    M22 = math.sqrt(betmdl1 / betmdl2) * (np.cos(phmdl12) - alpmdl2 * np.sin(phmdl12))
    M12 = math.sqrt(betmdl1 * betmdl2) * np.sin(phmdl12)
    N11 = math.sqrt(betmdl3 / betmdl2) * (np.cos(phmdl23) + alpmdl2 * np.sin(phmdl23))
    N12 = math.sqrt(betmdl2 * betmdl3) * np.sin(phmdl23)

    denom = M22 / M12 + N11 / N12 + 1e-16
    numer = 1 / np.tan(ph2pi12) + 1 / np.tan(ph2pi23)
    bet = numer / denom

    return bet


def BetaFromPhase_BPM_right(bn3, bn1, bn2, MADTwiss, ERRTwiss, plane):
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
        'MADTwiss':twiss
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
    if plane == 'H':
        ph2pi23 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn3]] - ERRTwiss.MUX[ERRTwiss.indx[bn2]]) % ERRTwiss.Q1
        ph2pi13 = 2. * np.pi * (ERRTwiss.MUX[ERRTwiss.indx[bn3]] - ERRTwiss.MUX[ERRTwiss.indx[bn1]]) % ERRTwiss.Q1
        phmdl23 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn3]] - MADTwiss.MUX[MADTwiss.indx[bn2]]) % MADTwiss.Q1
        phmdl13 = 2. * np.pi * (MADTwiss.MUX[MADTwiss.indx[bn3]] - MADTwiss.MUX[MADTwiss.indx[bn1]]) % MADTwiss.Q1

        betmdl1 = MADTwiss.BETX[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETX[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETX[MADTwiss.indx[bn3]]
        alpmdl3 = MADTwiss.ALFX[MADTwiss.indx[bn3]]
    elif plane == 'V':
        ph2pi23 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn3]] - ERRTwiss.MUY[ERRTwiss.indx[bn2]]) % ERRTwiss.Q2
        ph2pi13 = 2. * np.pi * (ERRTwiss.MUY[ERRTwiss.indx[bn3]] - ERRTwiss.MUY[ERRTwiss.indx[bn1]]) % ERRTwiss.Q2
        phmdl23 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn3]] - MADTwiss.MUY[MADTwiss.indx[bn2]]) % MADTwiss.Q2
        phmdl13 = 2. * np.pi * (MADTwiss.MUY[MADTwiss.indx[bn3]] - MADTwiss.MUY[MADTwiss.indx[bn1]]) % MADTwiss.Q2

        betmdl1 = MADTwiss.BETY[MADTwiss.indx[bn1]]
        betmdl2 = MADTwiss.BETY[MADTwiss.indx[bn2]]
        betmdl3 = MADTwiss.BETY[MADTwiss.indx[bn3]]
        alpmdl3 = MADTwiss.ALFY[MADTwiss.indx[bn3]]
    if betmdl3 < 0 or betmdl2 < 0 or betmdl1 < 0:
        print >> sys.stderr, "Some of the off-momentum betas are negative, change the dpp unit"
        sys.exit(1)

    # Find beta3 and alpha3 from phases assuming model transfer matrix
    # Matrix M: BPM2-> BPM3
    # Matrix N: BPM1-> BPM3
    M22 = math.sqrt(betmdl2 / betmdl3) * (np.cos(phmdl23) - alpmdl3 * np.sin(phmdl23))
    M12 = math.sqrt(betmdl2 * betmdl3) * np.sin(phmdl23)
    N22 = math.sqrt(betmdl1 / betmdl3) * (np.cos(phmdl13) - alpmdl3 * np.sin(phmdl13))
    N12 = math.sqrt(betmdl1 * betmdl3) * np.sin(phmdl13)

    denom = M22 / M12 - N22 / N12 + 1e-16
    numer = 1 / np.tan(ph2pi23) - 1 / np.tan(ph2pi13)
    bet = numer / denom

    return bet


if __name__ == "__main__":
    _model_twiss, _num_simulations, _num_processes, _output_dir, _beam = _parse_args()
    get_systematic_errors(_model_twiss, _num_simulations, _num_processes, _output_dir, _beam)