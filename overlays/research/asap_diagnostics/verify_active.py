"""CPU checks for command support and a known finite-difference information map."""
import json
import numpy as np

from research.asap_diagnostics.active_design import (
    ANKLES, decode_design, excite, finite_difference_gains, information_score,
)


def main():
    n = 54
    reference = {"action": np.zeros((n, 23), np.float32), "fps": 50.}
    modified = excite({"fixture": reference}, decode_design([1., .5, .4, .8]))["fixture"]["action"]
    other = [i for i in range(23) if i not in ANKLES]
    assert np.all(modified[:, other] == 0) and np.all(modified[0] == 0)
    assert np.max(np.abs(.25 * modified[:, [4, 10]])) <= .080001
    assert np.max(np.abs(.25 * modified[:, [5, 11]])) <= .040001
    np.testing.assert_allclose(modified[1:, [4, 5]], -modified[1:, [10, 11]], atol=2e-7)
    assert np.all(reference["action"] == 0), "Do not modify the baseline dataset"
    predictions = {}
    basis = np.zeros((50, 23, 2))
    basis[:, 4, 0] = 1.
    basis[:, 5, 1] = 2.
    for index, theta in enumerate(finite_difference_gains([20., 20.])):
        predictions["motion%d" % index] = {
            "fps": 50., "motion_times": np.arange(1, 51) / 50.,
            "terminate": np.zeros(50, dtype=bool), "root_trans_offset": np.tile([0., 0., .8], (50, 1)),
            "root_rot": np.tile([0., 0., 0., 1.], (50, 1)), "dof": basis @ theta,
        }
    score = information_score(predictions, ["fixture"], {"fixture": 1.}, noise_rad=1., ridge=.001)
    np.testing.assert_allclose(score["fisher"], [[50., 0.], [0., 200.]])
    np.testing.assert_allclose(score["objective"], 1/50.001 + 1/200.001)
    predictions["motion0"]["terminate"][20] = True
    assert not information_score(predictions, ["fixture"], {"fixture": 1.})["feasible"]
    print(json.dumps({"command_support": "PASS", "known_information_matrix": "PASS",
                      "infeasible_trajectory_rejection": "PASS", "scope": "CPU only; no acquisition or physics verification"}))


if __name__ == "__main__":
    main()
