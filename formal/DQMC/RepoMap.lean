import DQMC.Meas
import DQMC.Obs

namespace DQMC

def MeasToObs : MeasVar → Obs
  | .EqLt_density     => .eq_density_total
  | .EqLt_density_u   => .eq_density_up
  | .EqLt_density_d   => .eq_density_down
  | .EqLt_double_occ  => .eq_double_occupancy

  | .EqLt_g00         => .eq_green_spin_average
  | .EqLt_g00_u       => .eq_green_up
  | .EqLt_g00_d       => .eq_green_down

  | .Uneqlt_gt0       => .uneq_green_spin_average
  | .Uneqlt_gt0_u     => .uneq_green_up
  | .Uneqlt_gt0_d     => .uneq_green_down

  | .Uneqlt_jj        => .raw_current_current

theorem MeasToObs_injective :
    Function.Injective MeasToObs := by
  intro a b h
  cases a <;> cases b <;> simp [MeasToObs] at h
  all_goals rfl

end DQMC