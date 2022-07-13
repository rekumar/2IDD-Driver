import h5py
import numpy as np
from s2driver.logging import get_experiment_dir
from s2driver.driving import PVS
import os


def load_h5(scan_number, clip_flyscan=True, xbic_on_dsic=False, quant_scaler="us_ic"):
    """
    Loads a MAPS-generated .h5 file (raw + fitted data from 2IDD, fitted from 26IDC)

    fpath: path to file
    clip_flyscan: boolean, removes last two columns of map (which are corrupted when running flyscans)
    xbic_on_dsic: boolean. if True, considers the downstream ion chamber to be connected in an XBIC setup, adds to output['maps']['XBIC']
    quant_scaler: one of ['sr_current', 'us_ic', 'ds_ic']. quantification is normalized to some metric of beam power deposited in sample. typically we use upstream ion chamber

    returns a dictionary with scan info and maps.
    """
    fpath = os.path.join(
        get_experiment_dir(),
        "img.dat",
        f"2idd_{scan_number:04d}.h5",
    )
    quant_scaler_key = {
        "sr_current": 0,  # storage ring current
        "us_ic": 1,  # upstream ion chamber (incident flux)
        "ds_ic": 2,  # downstream ion chamber (transmitted flux - make sure this sensor was not used for XBIC!)
    }
    if quant_scaler not in quant_scaler_key:
        raise ValueError(
            f"Quantification normalization must be by either sr_current, us_ic, or ds_ic! user provided {quant_scaler}."
        )

    output = {"filepath": fpath}
    if clip_flyscan:
        xmask = slice(0, -2)  # last two columns are garbage from flyscan, omit here
    else:
        xmask = slice(0, None)  # no clipping

    with h5py.File(fpath, "r") as dat:
        output["x"] = dat["MAPS"]["x_axis"][()]
        output["y"] = dat["MAPS"]["y_axis"][()]
        output["spectra"] = np.moveaxis(dat["MAPS"]["mca_arr"][()], 0, 2)[
            :, xmask
        ]  # y by x by energy, full XRF spectra
        output["energy"] = dat["MAPS"]["energy"][
            : output["spectra"].shape[-1]
        ]  # specmap only has 2000 bins sometimes, match energy to that
        output["intspectra"] = dat["MAPS"]["int_spec"][
            : output["spectra"].shape[-1]
        ]  # integrated spectra
        output["extent"] = [
            output["x"][0],
            output["x"][-1],
            output["y"][0],
            output["y"][-1],
        ]

        scaler_names = dat["MAPS"]["scaler_names"][()].astype("U13").tolist()
        quant_scaler_values = np.array(
            dat["MAPS"]["scalers"][scaler_names.index(quant_scaler)]
        )[:, xmask]
        fillval = np.nanmean(quant_scaler_values[quant_scaler_values > 0])
        quant_scaler_values = np.where(
            quant_scaler_values == 0.0,
            fillval,
            quant_scaler_values,
        )  # change all values that are 0.0 to mean, avoid divide by 0
        if "/MAPS/XRF_fits" in dat:
            xrf = []
            raw = dat["MAPS"]["XRF_fits"][
                :, :, xmask
            ]  # xrf elemental maps, elements by y by x
            quant = np.moveaxis(
                dat["MAPS"]["XRF_fits_quant"][()], 2, 0
            )  # quantification factors from MAPS fitting, elements by factors
            for x, q in zip(raw, quant):
                x = np.divide(
                    x, quant_scaler_values
                )  # normalize to quantification scaler
                quantfactor = q[quant_scaler_key[quant_scaler]]
                xrf.append(
                    x / quantfactor / 4
                )  # factor of 4 came from discussion w/ Arthur Glowacki @ APS, and brings this value in agreement with MAPS displayed value. not sure why it is necessary though...
                # update 20221228: this factor changes from run to run, but is always a round number (have seen 1, 4, and 10). I expect it could be related to usic amplifier settings or similar, but cant find a related value in the h5 file REK
            output["fitted"] = True
        else:
            xrf = dat["MAPS"]["XRF_roi"][:, :, xmask]
            output["fitted"] = False

        allchan = dat["MAPS"]["channel_names"][()].astype("U13").tolist()
        
        output["maps"] = {}
        for channel, xrf_ in zip(allchan, xrf):
            output["maps"][channel] = np.array(xrf_)
        if xbic_on_dsic:
            output["maps"]["xbic"] = dat["MAPS"]["scalers"][scaler_names.index("ds_ic")][:, xmask]
    return output


def load_xeol(scan_number, wlmin=None, wlmax=None):
    fpath = os.path.join(
        get_experiment_dir(),
        "XEOL",
        f"2idd_{scan_number:04d}_XEOL.h5",
    )
    output = {}
    with h5py.File(fpath, "r") as dat:
        wl = dat["wavelength"][()]
        bg = dat["background"][()]
        counts_raw = dat["spectra"][()]
        dwelltime = dat["dwelltime"][()]
        

        if wlmin is None:
            wlmin = wl[0]
        if wlmax is None:
            wlmax = wl[-1]

        roi = slice(
            np.argmin(np.abs(wl-wlmin)),
            np.argmin(np.abs(wl-wlmax))
        )

        if len(counts_raw.shape) == 2: #1d scan
            cps = (counts_raw - bg) / dwelltime[:,np.newaxis]  # counts per second
            peak_cps_per_pixel = cps[:,roi].max(axis=1)
            peak_wl_per_pixel = wl[roi][cps[:,roi].argmax(axis=1)]
            avg = cps.mean(axis=0)
            pos = {'p1': dat["x"][()]}
        else:
            cps = (counts_raw - bg) / dwelltime[:,:,np.newaxis]  # counts per second
            peak_cps_per_pixel = cps[:,:,roi].max(axis=2)
            peak_wl_per_pixel = wl[roi][cps[:,:,roi].argmax(axis=2)]
            avg = cps.mean(axis=(0,1))
            pos = {'p1': dat["x"][()], 'p2': dat["y"][()]}
    
    output = {
        "wavelength": wl,
        "background_counts": bg,
        "raw_counts": counts_raw,
        "dwelltime": dwelltime,
        "cps": cps,
        "map_avg_cps": avg,
        "peak_cps_per_pixel": peak_cps_per_pixel,
        "peak_wl_per_pixel": peak_wl_per_pixel,
        "fitting_params": {
            "wlmin": wlmin,
            "wlmax": wlmax
        },
        "positions": pos
    }

    return output
