# -*- coding: utf-8 -*-

import pickle
import numpy as np
from scipy import signal
from scipy.interpolate import InterpolatedUnivariateSpline


def load_physio(physio, fs=None):
    """
    Returns ``Physio`` object with provided data

    Parameters
    ----------
    physio : array_like
        Input physiological data
    fs : float, optional
        Sampling rate of ``physio``

    Returns
    -------
    physio: peakdet.Physio
        Loaded physio object
    """
    pass


def check_physio(physio, ensure_fs=True):
    """
    Checks that ``physio`` is in correct format (i.e., ``peakdet.Physio``)

    Parameters
    ----------
    physio : Physio_like
    ensure_fs : bool, optional
        Make sure that ``physio`` has valid sampling rate attribute

    Returns
    -------
    physio : peakdet.Physio
        Loaded physio object
    """
    pass


def new_physio_like(ref_physio, data, fs=None):
    """
    Parameters
    ----------
    ref_physio : Physio_like
        Reference ``Physio`` object
    data : array_like
        Input physiological data
    fs : float, optional
        Sampling rate of ``data``. If not supplied, assumed to be the same as
        in ``ref_physio``

    Returns
    -------
    physio : peakdet.Physio
        Loaded physio object with provided ``data``
    """
    pass


def filter_physio(physio, cutoffs, method='bandpass'):
    """
    Performs frequency-based filtering on ``physio``

    Parameters
    ----------
    physio : Physio_like
        Input data to be filtered
    cutoffs : array_like
        Lower and/or upper bounds of filter (in Hz)
    method : str {'lowpass', 'highpass', 'bandpass', 'bandstop'}, optional
        Type of filter to use. Default: 'bandpass'

    Returns
    -------
    physio : peakdet.Physio
        Filtered input data
    """

    _valid_methods = ['lowpass', 'highpass', 'bandpass', 'bandstop']

    physio = check_physio(physio)
    if method not in _valid_methods:
        raise ValueError('Provided method {} is not permitted; must be in {}.'
                         .format(method, _valid_methods))

    cutoffs = np.array(cutoffs)
    if method in ['lowpass', 'highpass'] and cutoffs.size != 1:
        raise ValueError('Cutoffs must be len 1 when using {} method'
                         .format(method))
    elif method in ['bandpass', 'bandstop'] and cutoffs.size != 2:
        raise ValueError('Cutoffs must be len 2 when using {} method'
                         .format(method))

    nyq_cutoff = cutoffs / (physio.fs * 0.5)
    if nyq_cutoff > 1:
        raise ValueError('Provided cutoffs {} are outside of the Nyquist '
                         'frequency for input data with sampling rate {}.'
                         .format(cutoffs, physio.fs))

    b, a = signal.butter(3, nyq_cutoff, btype=method)
    filtered = signal.filtfilt(b, a, physio)

    return new_physio_like(physio, filtered)


def interpolate_data(physio, fs):
    """
    Interpolates ``physio`` to sampling rate ``fs``

    Parameters
    ----------
    physio : Physio_like
    fs : float, optional
        Desired sampling rate to interpolate ``physio`` to

    Returns
    -------
    physio : peakdet.Physio
        Interpolated input data
    """

    physio = check_physio(physio)
    orig = np.arange(0, physio.size / physio.fs, 1. / physio.fs)[:physio.size]
    new = np.arange(0, orig[-1], 1. / fs)

    interpolated = InterpolatedUnivariateSpline(orig, physio)(new)

    return new_physio_like(physio, interpolated, fs=fs)


def save(fname, pf):
    """
    Saves ``pf`` to ``fname`

    Parameters
    ----------
    fname : str
        Path to output file
    pf : peakdet.PeakFinder instance
        Or subclass instance
    """

    with open(fname, 'wb') as out:
        pickle.dump(pf, out)


def load(fname):
    """
    Loads `fname` created by save()

    Parameters
    ----------
    fname : str
        Path to input file

    Returns
    -------
    pdbf : peakdet.PeakFinder instance
    """

    with open(fname, 'rb') as src:
        return pickle.load(src)


def gen_flims(signal, fs):
    """
    Generates a rough guess of ideal frequency cutoffs for a bandpass filter

    Parameters
    ----------
    signal : array_like
    fs : float

    Returns
    -------
    flims : (2,) np.ndarray
        optimal frequency cutoffs
    """

    signal = np.squeeze(signal)
    inds = peakfinder(normalize(signal),
                      dist=int(fs / 4))
    inds = peakfinder(normalize(signal),
                      dist=np.ceil(np.diff(inds).mean()) / 2)
    freq = np.diff(inds).mean() / fs

    return np.asarray([freq / 2, freq * 2])


def normalize(data):
    """
    Normalizes `data` (subtracts mean and divides by std)

    Parameters
    ----------
    data : array-like

    Returns
    -------
    array: normalized data
    """

    data = np.array(data).squeeze()
    if data.ndim > 1:
        raise ValueError("Input must be one-dimensional.")
    if data.std() == 0:
        return data - data.mean()
    return (data - data.mean()) / data.std()


def get_extrema(data, peaks=True, thresh=0.4):
    """
    Find extrema in `data` by changes in sign of first derivative

    Parameters
    ----------
    data : array-like
    peaks : bool
        Whether to look for peaks (True) or troughs (False)
    thresh : float (0,1)

    Returns
    -------
    array : indices of extrema from `data`ex
    """

    if thresh < 0 or thresh > 1:
        raise ValueError("Thresh must be in (0, 1).")

    if peaks:
        uthresh = (thresh * np.diff(np.percentile(data, [5, 95])))
        Indx = np.where(data > uthresh)[0]
    else:
        uthresh = (thresh * np.diff(np.percentile(data, [95, 5])))
        Indx = np.where(data < uthresh)[0]

    trend = np.sign(np.diff(data))
    idx = np.where(trend == 0)[0]

    for i in range(idx.size - 1, -1, -1):
        if trend[min(idx[i] + 1, trend.size - 1)] >= 0:
            trend[idx[i]] = 1
        else:
            trend[idx[i]] = -1

    if peaks:
        comp = -2
    else:
        comp = 2

    idx = np.where(np.diff(trend) == comp)[0] + 1

    return np.intersect1d(Indx, idx)


def min_peak_dist(locs, data, peaks=True, dist=250):
    """
    Ensures extrema `locs` in `data` are separated by at least `dist`

    Parameters
    ----------
    locs : array-like
        Extrema, typically from get_extrema()
    data : array-like
    peaks : bool
        Whether to look for peaks (True) or troughs (False)
    dist : int
        Minimum required distance (in datapoints) b/w `locs`

    Returns
    -------
    array : extrema separated by at least `dist`
    """

    if not any(np.diff(sorted(locs)) <= dist):
        return locs

    if peaks:
        idx = data[locs].argsort()[::-1]
    else:
        idx = data[locs].argsort()

    locs = locs[idx]
    idelete = np.ones(locs.size) < 0

    for i in range(locs.size):
        if not idelete[i]:
            dist_diff = np.logical_and(locs >= locs[i] - dist,
                                       locs <= locs[i] + dist)
            idelete = np.logical_or(idelete, dist_diff)
            idelete[i] = 0

    return locs[~idelete]


def peakfinder(data, thresh=0.4, dist=250):
    """
    Finds peaks in `data`

    Parameters
    ----------
    data : array_like
    thresh : float (0,1)
    dist : int
        Minimum required distance (in datapoints) b/w peaks

    Returns
    -------
    array : peak locations (indices)
    """

    locs = get_extrema(data, thresh=thresh)
    locs = min_peak_dist(locs, data, dist=dist)

    return np.array(sorted(locs))


def troughfinder(data, thresh=0.4, dist=250):
    """
    Finds troughs in `data`

    Parameters
    ----------
    data : array-like
    thresh : float (0,1)
    dist : int
        Minimum required distance (in datapoints) b/w troughs

    Returns
    -------
    array : trough locations (indices)
    """

    locs = get_extrema(data, peaks=False, thresh=thresh)
    locs = min_peak_dist(locs, data, peaks=False, dist=dist)

    return np.array(sorted(locs))


def check_troughs(data, troughs, peaks):
    """
    Confirms that a trough exists between every set of `peaks` in `data`

    Parameters
    ----------
    data : array-like
    troughs : array-like
        Indices of current troughs
    peaks : array-like
        Indices of suspected peak locations

    Returns
    -------
    array : troughs
    """

    all_troughs = np.zeros(peaks.size - 1,
                           dtype='int')

    for f in range(peaks.size - 1):
        curr = np.logical_and(troughs > peaks[f],
                              troughs < peaks[f + 1])
        if not np.any(curr):
            dp = data[peaks[f]:peaks[f + 1]]
            idx = peaks[f] + np.argwhere(dp == dp.min())[0]
        else:
            idx = troughs[curr]
            if idx.size > 1:
                idx = idx[0]

        all_troughs[f] = idx

    return all_troughs


def gen_temp(data, locs, factor=0.5):
    """
    Generate waveform template array from `data`

    Waveforms are taken from around peak locations in `locs`

    Parameters
    ----------
    data : array-like
    locs : arrray
        Indices of suspected peak locations
    factor: float (0,1)

    Returns
    -------
    array : peak waveforms
    """

    avgrate = round(np.diff(locs).mean())
    THW = int(np.ceil(factor * (avgrate / 2)))
    nsamptemp = (THW * 2) + 1
    npulse = locs.size
    template = np.zeros([npulse - 2, nsamptemp])

    for n in range(1, npulse - 1):
        template[n - 1] = data[locs[n] - THW:locs[n] + THW + 1]
        template[n - 1] = template[n - 1] - template[n - 1].mean()
        template[n - 1] = template[n - 1] / max(abs(template[n - 1]))

    return template


def z_transform(z):
    """
    Z-transform `z`

    Parameters
    ----------
    z : array-like

    Returns
    -------
    array : z-transformed input
    """

    z = z - (z.sum() / z.size)
    z = z / np.sqrt(np.dot(z.T, z) * (1. / (z.size - 1)))

    return z


def corr(x, y, z_tran=[False, False]):
    """
    Returns correlation of `x` and `y`

    Will z-transform data before correlation.

    Parameters
    ----------
    x : array, n x 1
    y : array, n x 1
    z_tran : [bool, bool]
        Whether x and y, respectively, have been z-transformed

    Returns
    -------
    float : [0,1] correlation between `x` and `y`
    """

    if x.ndim > 1:
        x = x.flatten()
    if y.ndim > 1:
        y = y.flatten()

    if not z_tran[0]:
        x = z_transform(x)
    if not z_tran[1]:
        y = z_transform(y)

    if x.size == y.size:
        return np.dot(x.T, y) * (1. / (x.size - 1))
    else:
        return None


def corr_template(temp, sim=0.95):
    """
    Generates single waveform template from output of `gen_temp`.

    Correlates each row of `temp` to averaged template and selects rows with
    correlation >=`sim` for use in final, averaged template.

    Parameters
    ----------
    temp : array of waveforms
    sim : float (0,1)
        Cutoff for correlation of waveforms to average template

    Returns
    -------
    array : template waveform
    """

    npulse = temp.shape[0]

    mean_temp = z_transform(temp.mean(axis=0))
    sim_to_temp = np.zeros((temp.shape[0], 1))

    for n in range(temp.shape[0]):
        sim_to_temp[n] = corr(temp[n], mean_temp, [False, True])

    good_temp_ind = np.where(sim_to_temp > sim)[0]
    if good_temp_ind.shape[0] >= np.ceil(npulse * 0.1):
        clean_temp = temp[good_temp_ind]
    else:
        new_temp_ind = np.where(sim_to_temp >
                                (1 - np.ceil(npulse * 0.1) / npulse))[0]
        clean_temp = np.atleast_2d(temp[new_temp_ind]).T

    return clean_temp.mean(axis=0)


def match_temp(data, locs, temp):
    """
    Searches through `data` and tries to find peaks that match `temp`.

    Uses template matching to attempt to find missing peaks in data. Searches
    through `data` at regular intervals (corresponding to the average rate in
    `locs`), detecting peaks via correlation of waveforms to `temp`.

    Parameters
    ----------
    data : array-like
    locs : array-like
        Indices of suspected peak locations
    temp : array-like
        Cleaned waveform of target peak shape

    Returns
    -------
    array : indices of peak locations
    """

    avgrate = round(np.diff(locs).mean())
    THW = int(np.floor(temp.size / 2))
    z_temp = z_transform(temp)
    is_z_trans = [False, True]

    c_samp_start = int(round((2.0 * THW) + 1)) - 1
    try:
        c_samp_end = int(locs[19])
    except IndexError:
        c_samp_end = int(locs[-1] - 1)

    sim_to_temp = np.zeros(c_samp_end + 1)
    for n in np.arange(c_samp_start, c_samp_end + 1):
        i_sig_start = n - THW
        i_sig_end = n + THW
        sig_part = data[int(i_sig_start):int(i_sig_end) + 1]
        sim_to_temp[n] = corr(sig_part, z_temp, is_z_trans)

    c_best_match = max(sim_to_temp)
    i_best_match = np.where(sim_to_temp == c_best_match)[0][0]

    peak_num = 0
    search_steps_tot = int(np.ceil(0.5 * avgrate))

    n_samp_pad = THW + search_steps_tot + 1
    data_padded = np.hstack((np.zeros(int(n_samp_pad)),
                             data,
                             np.zeros(int(n_samp_pad))))
    n = int(i_best_match + n_samp_pad)
    sim_to_temp = np.zeros(data_padded.size)

    while n > 1 + search_steps_tot + THW:
        search_pos_array = np.arange(-search_steps_tot - 1, search_steps_tot,
                                     dtype='int')
        for search_pos in search_pos_array:
            index_search_start = int(n - THW + search_pos + 1)
            index_search_end = int(n + THW + search_pos + 1)
            sig_part = data_padded[index_search_start:index_search_end + 1]
            correlation = corr(sig_part, z_temp, is_z_trans)
            curr_weight = abs(data_padded[n + search_pos + 2])
            correlation_weighted = curr_weight * correlation
            sim_to_temp[n + search_pos + 1] = correlation_weighted

        index_search_start = int(n - search_steps_tot)
        index_search_end = int(n + search_steps_tot)
        index_search_range = np.arange(index_search_start,
                                       index_search_end + 1,
                                       dtype='int')

        search_range_values = sim_to_temp[index_search_range]
        c_best_match = np.nanmax(search_range_values)
        i_best_match = np.where(search_range_values == c_best_match)[0][0]
        best_pos = index_search_range[i_best_match]
        n = int(best_pos - avgrate)

    n = best_pos
    peak_num = 0
    cpulse = np.zeros(data.size)
    nlimit = data_padded.size - THW - search_pos - 1
    location_weight = signal.gaussian(2 * search_steps_tot + 1,
                                      std=(2 * search_steps_tot) / 5)

    while n < nlimit:
        search_pos_array = np.arange(-search_steps_tot - 1, search_steps_tot,
                                     dtype='int')
        for search_pos in search_pos_array:
            index_search_start = int(max(0, n - THW + search_pos) + 1)
            index_search_end = int(n + THW + search_pos + 1)
            sig_part = data_padded[index_search_start:index_search_end + 1]
            correlation = corr(sig_part, z_temp, is_z_trans)
            loc_weight = location_weight[search_pos + search_steps_tot + 1]
            amp_weight = abs(data_padded[n + search_pos + 2])
            correlation_weighted = amp_weight * correlation * loc_weight
            sim_to_temp[n + search_pos + 1] = correlation_weighted

        index_search_start = n - search_steps_tot
        index_search_end = n + search_steps_tot
        index_search_range = np.arange(index_search_start,
                                       index_search_end + 1,
                                       dtype='int')

        search_range_values = sim_to_temp[index_search_range]
        c_best_match = np.nanmax(search_range_values)
        i_best_match = np.where(search_range_values == c_best_match)[0][0]
        best_pos = index_search_range[i_best_match]

        cpulse[peak_num] = best_pos - n_samp_pad
        peak_num += 1

        found_c_pulses = np.nanmax(np.where(cpulse)[0])

        if found_c_pulses < 3:
            curr_hr_in_samp = avgrate
        if found_c_pulses < 21 and found_c_pulses >= 3:
            curr_hr_in_samp = round(np.mean(np.diff(cpulse)))
        if found_c_pulses >= 21:
            curr_cpulses = cpulse[int(found_c_pulses - 20):int(found_c_pulses)]
            curr_hr_in_samp = round(np.mean(np.diff(curr_cpulses)))

        check_smaller = curr_hr_in_samp > 0.5 * avgrate
        check_larger = curr_hr_in_samp < 1.5 * avgrate

        if check_smaller and check_larger:
            n = int(best_pos + curr_hr_in_samp)
        else:
            n = int(best_pos + avgrate)

    return cpulse[np.where(cpulse)[0]]
