import DQMC.Obs

namespace DQMC.Density

/-- Spin-resolved equal-time density pair.
Formal layer corresponding to the pair of repo observables
`EqLt.density_u` and `EqLt.density_d`. -/
structure SpinDensity (α : Type) where
  up : α
  down : α

/-- Total equal-time density.
Formal layer corresponding to the repo observable
`EqLt.density`. -/
structure TotalDensity (α : Type) where
  value : α

/-- Code-level convention from `meas.c`: total density is the spin sum.
Corresponds to `EqLt.density = EqLt.density_u + EqLt.density_d`. -/
def TotalDensity.fromSpin {α : Type} [Add α]
    (n : SpinDensity α) : TotalDensity α :=
  { value := n.up + n.down }

theorem density_total_eq_density_up_add_density_down {α : Type} [Add α]
    (n : SpinDensity α) :
    (TotalDensity.fromSpin n).value = n.up + n.down := by
  rfl

end DQMC.Density
