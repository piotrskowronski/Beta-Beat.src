import __init__  # @UnusedImport
import os
import SegmentBySegment
import numpy as np
import math

from math import sqrt
from Utilities import tfs_file_writer


def write_dispersion(element_name, is_element, measured_hor_disp, measured_ver_disp, measured_norm_disp, input_model, propagated_models, save_path, dispersion_summary_file):
    file_disp_x, file_norm_disp_x, file_disp_y = _get_dispersion_tfs_files(element_name, is_element, save_path)

    model_propagation = propagated_models.propagation
    model_back_propagation = propagated_models.back_propagation
    model_cor = propagated_models.corrected

    if not is_element:
        bpms_list = SegmentBySegment.intersect([measured_hor_disp, model_propagation, input_model, model_back_propagation])
    else:
        bpms_list = SegmentBySegment.intersect([model_propagation, input_model, model_back_propagation])

    summary_data_x = _write_dispersion_for_plane(file_disp_x, "X", element_name, bpms_list, measured_hor_disp, input_model, model_cor, model_propagation, model_back_propagation, is_element)

    summary_data_nx = _write_normalized_hor_dispersion(file_norm_disp_x, element_name, bpms_list, measured_norm_disp, input_model, model_cor, model_propagation, model_back_propagation, is_element)

    summary_data_y = _write_dispersion_for_plane(file_disp_y, "Y", element_name, bpms_list, measured_ver_disp, input_model, model_cor, model_propagation, model_back_propagation, is_element)

    if is_element:
        _write_summary_data(dispersion_summary_file, summary_data_x, summary_data_nx, summary_data_y)


def get_dispersion_summary_file(save_path):
        dispersion_summary_file = tfs_file_writer.TfsFileWriter.open(os.path.join(save_path, "sbs_summary_disp.out"))
        dispersion_summary_file.add_column_names(["NAME", "S",
                                                  "DXPROP", "DXPROPERR", "DPXPROP", "DPXPROPERR",
                                                  "DYPROP", "DYPROPERR", "DPYPROP", "DPYPROPERR",
                                                  "NDXPROP", "NDXPROPERR",
                                                  "DXMODEL", "DYMODEL", "NDXMODEL", "DPXMODEL", "DYPMODEL", "MODEL_S"])
        dispersion_summary_file.add_column_datatypes(["%bpm_s", "%le",
                                                      "%le", "%le", "%le", "%le",
                                                      "%le", "%le", "%le", "%le",
                                                      "%le", "%le",
                                                      "%le", "%le", "%le", "%le", "%le", "%le"])
        return dispersion_summary_file


def _write_summary_data(dispersion_summary_file, summary_data_x, summary_data_nx, summary_data_y):
    dispersion_summary_file.add_table_row([summary_data_x[0], summary_data_x[1],
                                           summary_data_x[2], summary_data_x[3], summary_data_x[4], summary_data_x[5],
                                           summary_data_y[2], summary_data_y[3], summary_data_y[4], summary_data_y[5],
                                           summary_data_nx[0], summary_data_nx[1],
                                           summary_data_x[6], summary_data_y[6], summary_data_nx[2], summary_data_x[7], summary_data_y[7], summary_data_x[8]])


def _get_dispersion_tfs_files(element_name, is_element, save_path):

    file_disp_x = tfs_file_writer.TfsFileWriter.open(os.path.join(save_path, "sbsDx_" + element_name + ".out"))
    file_norm_disp_x = tfs_file_writer.TfsFileWriter.open(os.path.join(save_path, "sbsNDx_" + element_name + ".out"))
    file_disp_y = tfs_file_writer.TfsFileWriter.open(os.path.join(save_path, "sbsDy_" + element_name + ".out"))

    if not is_element:
        file_disp_x.add_column_names(["NAME", "S", "DXPROP", "DXPROPERR", "DXCOR", "DXCORERR", "DXBACK", "DXBACKERR", "DPXPROP", "DPXPROPERR", "DPXCOR", "DPXCORERR", "DXMODEL", "DPXMODEL", "MODEL_S"])
        file_disp_x.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])

        file_norm_disp_x.add_column_names(["NAME", "S", "NDXPROP", "NDXPROPERR", "NDXCOR", "NDXCORERR", "NDXBACK", "NDXBACKERR", "NDXMODEL", "MODEL_S"])
        file_norm_disp_x.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])

        file_disp_y.add_column_names(["NAME", "S", "DYPROP", "DYPROPERR", "DYCOR", "DYCORERR", "DYBACK", "DYBACKERR", "DPYPROP", "DPYPROPERR", "DPYCOR", "DPYCORERR", "DYMODEL", "DPYMODEL", "MODEL_S"])
        file_disp_y.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])
    else:
        file_disp_x.add_column_names(["NAME", "S", "DXPROP", "DXPROPERR", "DPXPROP", "DPXPROPERR", "DXMODEL", "DPXMODEL", "MODEL_S"])
        file_disp_x.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])

        file_norm_disp_x.add_column_names(["NAME", "S", "NDXPROP", "NDXPROPERR", "NDXMODEL", "MODEL_S"])
        file_norm_disp_x.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le"])

        file_disp_y.add_column_names(["NAME", "S", "DYPROP", "DYPROPERR", "DPYPROP", "DPYPROPERR", "DYMODEL", "DPYMODEL", "MODEL_S"])
        file_disp_y.add_column_datatypes(["%bpm_s", "%le", "%le", "%le", "%le", "%le", "%le", "%le", "%le"])

    return file_disp_x, file_norm_disp_x, file_disp_y


def _write_dispersion_for_plane(file_dispersion, plane, element_name, bpms_list, measured_dispersion, input_model, model_cor, model_propagation, model_back_propagation, is_element):

    summary_data = []

    for bpm in bpms_list:
        bpm_s = bpm[0]
        bpm_name = bpm[1]

        first_bpm = bpms_list[0][1]
        last_bpm = bpms_list[-1][1]

        model_disp = input_model.DX[input_model.indx[bpm_name]]
        model_s = input_model.S[input_model.indx[bpm_name]]
        model_disp_p = input_model.DPX[input_model.indx[bpm_name]]

        delta_phase = (getattr(model_propagation, "MU" + plane)[model_propagation.indx[bpm_name]]) % 1
        delta_phase_back = (getattr(model_back_propagation, "MU" + plane)[model_back_propagation.indx[bpm_name]]) % 1
        delta_phase_corr = (getattr(model_cor, "MU" + plane)[model_cor.indx[bpm_name]]) % 1

        normal_prop_disp = getattr(model_propagation, "D" + plane)[model_propagation.indx[bpm_name]]
        back_prop_disp = getattr(model_back_propagation, "D" + plane)[model_back_propagation.indx[bpm_name]]

        prop_disp_p = getattr(model_propagation, "DP" + plane)[model_propagation.indx[bpm_name]]
        back_prop_disp_p = getattr(model_back_propagation, "DP" + plane)[model_back_propagation.indx[bpm_name]]
        prop_disp_p_err = 1e-8  # TODO: Propagate?

        normal_prop_disp_err = _propagate_error_dispersion(getattr(measured_dispersion, "STDD" + plane)[measured_dispersion.indx[first_bpm]],
                                                           getattr(model_propagation, "BET" + plane)[model_propagation.indx[first_bpm]],
                                                           getattr(model_propagation, "BET" + plane)[model_propagation.indx[bpm_name]],
                                                           delta_phase,
                                                           getattr(model_propagation, "ALF" + plane)[model_propagation.indx[first_bpm]])

        back_prop_disp_err = _propagate_error_dispersion(getattr(measured_dispersion, "STDD" + plane)[measured_dispersion.indx[last_bpm]],
                                                         getattr(model_back_propagation, "BET" + plane)[model_back_propagation.indx[last_bpm]],
                                                         getattr(model_back_propagation, "BET" + plane)[model_back_propagation.indx[bpm_name]],
                                                         delta_phase_back,
                                                         getattr(model_back_propagation, "ALF" + plane)[model_back_propagation.indx[last_bpm]])

        if not is_element:
            corr_disp = getattr(model_cor, "D" + plane)[model_cor.indx[bpm_name]]
            corr_disp_err = _propagate_error_dispersion(getattr(measured_dispersion, "STDD" + plane)[measured_dispersion.indx[last_bpm]],
                                                         getattr(model_cor, "BET" + plane)[model_cor.indx[last_bpm]],
                                                         getattr(model_cor, "BET" + plane)[model_cor.indx[bpm_name]],
                                                         delta_phase_corr,
                                                         getattr(model_back_propagation, "ALF" + plane)[model_cor.indx[last_bpm]])

            corr_disp_p = getattr(model_cor, "DP" + plane)[model_cor.indx[bpm_name]]
            corr_disp_p_err = 0  # TODO: propagate?

            file_dispersion.add_table_row([bpm_name, bpm_s, normal_prop_disp, normal_prop_disp_err, corr_disp, corr_disp_err, back_prop_disp, back_prop_disp_err, prop_disp_p, prop_disp_p_err, corr_disp_p, corr_disp_p_err, model_disp, model_disp_p, model_s])
        else:
            average_disp, final_disp_err = SegmentBySegment.weighted_average_for_SbS_elements(normal_prop_disp, normal_prop_disp_err, back_prop_disp, back_prop_disp_err)
            average_disp_p, final_disp_p_err = SegmentBySegment.weighted_average_for_SbS_elements(prop_disp_p, prop_disp_p_err, back_prop_disp_p, back_prop_disp_err)

            file_dispersion.add_table_row([bpm_name, bpm_s, average_disp, final_disp_err, average_disp_p, final_disp_p_err, model_disp, model_disp_p, model_s])
            if bpm_name == element_name:
                summary_data = [bpm_name, bpm_s, average_disp, final_disp_err, average_disp_p, final_disp_p_err, model_disp, model_disp_p, model_s]
    file_dispersion.write_to_file()
    return summary_data


def _write_normalized_hor_dispersion(file_norm_disp_x, element_name, bpms_list, measured_norm_disp, input_model, model_cor, model_propagation, model_back_propagation, is_element):

    summary_data = []

    for bpm in bpms_list:
        bpm_s = bpm[0]
        bpm_name = bpm[1]

        model_norm_disp = input_model.DX[input_model.indx[bpm_name]]
        model_s = input_model.S[input_model.indx[bpm_name]]

        prop_norm_disp = model_propagation.DX[model_propagation.indx[bpm_name]] / sqrt(model_propagation.BETX[model_propagation.indx[bpm_name]])
        back_prop_norm_disp = model_back_propagation.DX[model_back_propagation.indx[bpm_name]] / sqrt(model_back_propagation.BETX[model_propagation.indx[bpm_name]])

        prop_norm_disp_err = 1e-8  # TODO: Propagate
        back_prop_norm_disp_err = 1e-8  # TODO: Propagate

        if not is_element:
            corr_norm_disp = model_cor.DX[model_cor.indx[bpm_name]] / sqrt(model_cor.BETX[model_cor.indx[bpm_name]])
            err_corr_norm_disp = 1e-8  # TODO: Propagate

            file_norm_disp_x.add_table_row([bpm_name, bpm_s, prop_norm_disp, prop_norm_disp_err, corr_norm_disp, err_corr_norm_disp, back_prop_norm_disp, back_prop_norm_disp_err, model_norm_disp, model_s])
        else:
            average_norm_disp, final_norm_disp_err = SegmentBySegment.weighted_average_for_SbS_elements(prop_norm_disp, prop_norm_disp_err, back_prop_norm_disp, back_prop_norm_disp_err)
            file_norm_disp_x.add_table_row([bpm_name, bpm_s, average_norm_disp, final_norm_disp_err, model_norm_disp, model_s])
            if bpm_name == element_name:
                summary_data = [average_norm_disp, final_norm_disp_err, model_norm_disp]
    file_norm_disp_x.write_to_file()
    return summary_data

def _propagate_error_dispersion(std_D0, bet0, bets, dphi, alf0):
    return np.abs(std_D0 * math.sqrt(bets/bet0) * (np.cos(2*np.pi*dphi)+alf0*np.sin(2*np.pi*dphi)))  # @IgnorePep8
