"""Record the actually executed nominal inputs for newly acquired SysID data."""
from research.asap_diagnostics.dataset_runtime import RolloutRecorderPPO
from research.asap_diagnostics.sysid_runtime import CandidateGainReplay


class NominalGainReplay(CandidateGainReplay):
    def _compute_torques(self, actions):
        self.executed_nominal = self.get_open_loop_action_at_current_timestep().clone()
        return super()._compute_torques(actions)


class NominalRecorderPPO(RolloutRecorderPPO):
    def _record_dataset_frame(self):
        # The checkpoint actor is only an evaluation interface; its output is
        # ignored by CandidateGainReplay. Saving that output would corrupt D.
        cached = self.env.actions
        self.env.actions = self.env.executed_nominal
        try:
            return super()._record_dataset_frame()
        finally:
            self.env.actions = cached
