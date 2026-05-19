import DQMC.Basic

namespace DQMC

inductive Obs where
  | eq_density_total
  | eq_density_up
  | eq_density_down
  | eq_double_occupancy

  | eq_green_spin_average
  | eq_green_up
  | eq_green_down

  | uneq_green_spin_average
  | uneq_green_up
  | uneq_green_down

  | raw_current_current
  | projected_current_current
  | elec_current_current
  | thermal_current_current
deriving DecidableEq, Repr

end DQMC
