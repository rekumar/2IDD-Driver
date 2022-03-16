import itertools as itt
import numpy as np

### Filters

FILTER_TRANSMITTANCES = [
    0.1,
    0.2,
    0.3,
    0.4,
]  # transmittance (0-1) for each filter (1,2,3,4)

TRANSMITTANCE_TO_FILTERS = (
    {}
)  # dictionary of transmittance: [filter indices], where the transmittance is accessed by inserting the filters in the list
for num_filters in range(len(FILTER_TRANSMITTANCES) + 1):
    for filter_indices in itt.combinations(
        list(range(len(FILTER_TRANSMITTANCES))), num_filters
    ):
        this_transmittance = 1
        for fi in filter_indices:
            this_transmittance *= FILTER_TRANSMITTANCES[fi]
        this_transmittance = round(this_transmittance, 12)  # rounding errors
        TRANSMITTANCE_TO_FILTERS[this_transmittance] = [
            fi + 1 for fi in filter_indices
        ]  # start from 1, not 0

AVAILABLE_TRANSMITTANCES = sorted(list(TRANSMITTANCE_TO_FILTERS.keys()))


def find_nearest_transmittance(transmittance):
    """
    Find the nearest available transmittance to the input transmittance
    """
    if transmittance in AVAILABLE_TRANSMITTANCES:
        return transmittance
    else:
        idx = np.argmin(np.abs(transmittance - np.array(AVAILABLE_TRANSMITTANCES)))
        return AVAILABLE_TRANSMITTANCES[idx]
