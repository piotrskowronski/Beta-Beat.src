from collections import OrderedDict
import sys
import os
import logging
import pandas
import numpy as np
from utils import tfs_file_writer

LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

HEADER = "@"
NAMES = "*"
TYPES = "$"
COMMENTS = "#"
INDEX_ID = "INDEX&&&"

ID_TO_TYPE = {
    "%s": np.str,
    "%bpm_s": np.str,
    "%le": np.float64,
    "%f": np.float64,
    "%hd": np.int,
    "%d": np.int,
}

TYPE_TO_ID = {
    np.str: "%s",
    np.float64: "%le",
    float: "%le",
    np.int: "%d",
}


class TfsDataFrame(pandas.DataFrame):
    """
    Class to hold the information of the built Pandas DataFrame,
    together with a way of getting the headers of the TFS file.
    To get a header value do: data_frame["header_name"] or
    data_frame.header_name.
    """

    _metadata = ["headers", "indx"]

    def __init__(self, *args, **kwargs):
        self.headers = kwargs.pop("headers", {})
        self.indx = _Indx(self)
        super(TfsDataFrame, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        try:
            return super(TfsDataFrame, self).__getitem__(key)
        except KeyError:
            try:
                return self.headers[key]
            except KeyError:
                raise KeyError(str(key) +
                               " is not in the DataFrame or headers.")

    def __getattr__(self, name):
        try:
            return super(TfsDataFrame, self).__getattr__(name)
        except AttributeError:
            try:
                return self.headers[name]
            except KeyError:
                raise AttributeError(str(name) +
                                     " is not in the DataFrame or headers.")

    @property
    def _constructor(self):
        return TfsDataFrame


class _Indx(object):
    """
    Helper class to mock the metaclass twiss.indx["element_name"]
    behaviour.
    """
    def __init__(self, tfs_data_frame):
        self._tfs_data_frame = tfs_data_frame

    def __getitem__(self, key):
        name_series = self._tfs_data_frame.NAME
        return name_series[name_series == key].index[0]


def read_tfs(tfs_path, index=None):
    """
    Parses the TFS table present in tfs_path and returns a custom Pandas
    DataFrame (TfsDataFrame).
    :param tfs_path: Input filepath
    :param index: Name of the column to set as index. If not given looks for INDEX_ID-column
    :return: TFS_DataFrame object
    """
    LOGGER.debug("Reading path: " + tfs_path)
    headers = OrderedDict()
    column_names = column_types = None
    rows_list = []
    with open(tfs_path, "r") as tfs_data:
        for line in tfs_data:
            parts = line.split()
            if len(parts) == 0:
                continue
            if parts[0] == HEADER:
                headers[parts[1]] = _parse_header(
                    parts[2], " ".join(parts[3:]))
            elif parts[0] == NAMES:
                LOGGER.debug("Setting column names.")
                column_names = np.array(parts[1:])
            elif parts[0] == TYPES:
                LOGGER.debug("Setting column types.")
                column_types = _compute_types(parts[1:])
            elif parts[0] == COMMENTS:
                continue
            else:
                if column_names is None:
                    raise TfsFormatError("Column names have not been set.")
                if column_types is None:
                    raise TfsFormatError("Column types have not been set.")
                parts = [part.strip('"') for part in parts]
                rows_list.append(parts)
    data_frame = _create_data_frame(column_names, column_types, rows_list, headers)

    if index is not None:
        # Use given column as index
        data_frame = data_frame.set_index(index)
    else:
        # Try to find Index automatically
        index_column = [c for c in data_frame.columns if c.startswith(INDEX_ID)]
        if len(index_column) > 0:
            data_frame = data_frame.set_index(index_column)
            idx_name = index_column[0].replace(INDEX_ID, "")
            if idx_name == "":
                idx_name = None  # to remove it completely (Pandas makes a difference)
            data_frame = data_frame.rename_axis(idx_name)

    # not sure if this is needed in general but some of GetLLM's funstions try to access this
    headers["filename"] = tfs_path

    _validate(data_frame)
    return data_frame


def write_tfs(tfs_path, data_frame, headers_dict={}, save_index=False):
    """
    Writes the Pandas DataFrame data_frame into tfs_path with the headers_dict
    as headers dictionary. If you want to keep the order of the headers, use
    collections.OrderedDict.
    :param tfs_path: Output filepath
    :param data_frame: Data Frame to save
    :param headers_dict: Headers of the dataframe, if empty tries to use data_frame.headers
    :param save_index: bool or string. If True, saves the index of the data_frame to a column
    identifiable by INDEX_ID (will be loaded automatically by read_tfs). If string, it saves
    the index of the data_frame to a column named like the string given. Default: False
    """
    _validate(data_frame)

    if isinstance(save_index, basestring):
        # saves index into column by name given
        data_frame = data_frame.copy()
        data_frame[save_index] = data_frame.index
    elif save_index:
        # saves index into column, which can be found by INDEX identifier
        data_frame = data_frame.copy()
        try:
            full_name = INDEX_ID + data_frame.index.name
        except TypeError:
            full_name = INDEX_ID
        data_frame[full_name] = data_frame.index

    tfs_name = os.path.basename(tfs_path)
    tfs_dir = os.path.dirname(tfs_path)
    LOGGER.debug("Attempting to write file: " + tfs_name + " in " + tfs_dir)
    tfs_writer = tfs_file_writer.TfsFileWriter(tfs_name, outputpath=tfs_dir)
    column_names = _get_column_names(data_frame)
    column_types = _get_column_types(data_frame)

    if len(headers_dict) == 0:
        try:
            headers_dict = data_frame.headers
        except AttributeError:
            pass

    for head_name in headers_dict:
        if type(headers_dict[head_name]) is str:
            tfs_writer.add_string_descriptor(head_name, headers_dict[head_name])
        else:
            tfs_writer.add_float_descriptor(head_name, headers_dict[head_name])
    tfs_writer.add_column_names(column_names)
    tfs_writer.add_column_datatypes(column_types)
    for _, row in data_frame.iterrows():
        tfs_writer.add_table_row(row)
    tfs_writer.write_to_file()


def add_coupling(data_frame):
    """
    Computes the coupling for data_frame adding 3 columns to it:
    - f1001
    - f1010
    - gamma
    """
    df = data_frame
    j = np.array([[0., 1.],
                  [-1., 0.]])
    rs = np.reshape(df.as_matrix(columns=["R11", "R12",
                                          "R21", "R22"]),
                    (len(df), 2, 2))
    cs = np.einsum("ij,kjn,no->kio",
                   -j, np.transpose(rs, axes=(0, 2, 1)), j)
    cs = np.einsum("k,kij->kij", (1 / np.sqrt(1 + np.linalg.det(rs))), cs)

    g11a = 1 / np.sqrt(df.loc[:, "BETX"])
    g12a = np.zeros(len(df))
    g21a = df.loc[:, "ALFX"] / np.sqrt(df.loc[:, "BETX"])
    g22a = np.sqrt(df.loc[:, "BETX"])
    gas = np.reshape(np.array([g11a, g12a,
                               g21a, g22a]).T,
                     (len(df), 2, 2))

    ig11b = np.sqrt(df.loc[:, "BETY"])
    ig12b = np.zeros(len(df))
    ig21b = -df.loc[:, "ALFY"] / np.sqrt(df.loc[:, "BETY"])
    ig22b = 1. / np.sqrt(df.loc[:, "BETY"])
    igbs = np.reshape(np.array([ig11b, ig12b,
                                ig21b, ig22b]).T,
                      (len(df), 2, 2))
    cs = np.einsum("kij,kjl,kln->kin", gas, cs, igbs)
    gammas = np.sqrt(1 - np.linalg.det(cs))
    data_frame.loc[:, "gamma"] = gammas
    data_frame.loc[:, "f1001"] = ((cs[:, 0, 0] + cs[:, 1, 1]) * 1j +
                                  (cs[:, 0, 1] - cs[:, 1, 0])) / 4 / gammas
    data_frame.loc[:, "f1010"] = ((cs[:, 0, 0] - cs[:, 1, 1]) * 1j +
                                  (-cs[:, 0, 1]) - cs[:, 1, 0]) / 4 / gammas


class TfsFormatError(Exception):
    """
    Raised when wrong format is detected in the TFS file.
    """
    pass


def _create_data_frame(column_names, column_types, rows_list, headers):
    data_frame = TfsDataFrame(data=np.array(rows_list),
                              columns=column_names,
                              headers=headers)
    _assign_column_types(data_frame, column_names, column_types)
    return data_frame


def _assign_column_types(data_frame, column_names, column_types):
    names_to_types = dict(zip(column_names, column_types))
    for name in names_to_types:
        data_frame[name] = data_frame[name].astype(names_to_types[name])


def _compute_types(str_list):
    return [_id_to_type(string) for string in str_list]


def _parse_header(type_str, value_str):
    return _id_to_type(type_str)(value_str.strip('"'))


def _id_to_type(type_str):
    try:
        return ID_TO_TYPE[type_str]
    except KeyError:
        if type_str.startswith("%") and type_str.endswith("s"):
            return str
        _raise_unknown_type(type_str)


def _type_to_id(type_f):
    try:
        return TYPE_TO_ID[type_f]
    except KeyError:
        return "%s"


def _get_column_names(data_frame):
    return data_frame.columns.values


def _get_column_types(data_frame):
    types = []
    for column in data_frame.columns:
        type_f = data_frame[column].dtype
        types.append(_type_to_id(type_f.type))
    return types


def _raise_unknown_type(name):
    raise TfsFormatError("Unknown data type: " + name)


def _validate(data_frame):
    """ Check if Dataframe contains finite values only """
    def isnotfinite(x):
        try:
            return ~np.isfinite(x)
        except TypeError:
            # most likely string
            try:
                return np.zeros(x.shape, dtype=bool)
            except AttributeError:
                # single entry
                return np.zeros(1, dtype=bool)

    bool_df = data_frame.apply(isnotfinite)
    if bool_df.values.any():
        LOGGER.error("DataFrame contains non-physical values at Index: {:s}".format(
            str(bool_df.index[bool_df.any(axis='columns')].tolist())
        ))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    LOGGER.debug(read_tfs(sys.argv[1]))
