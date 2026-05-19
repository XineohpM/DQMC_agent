import DQMC.Basic
import DQMC.Obs

namespace DQMC.Green

/-- Pair of spin-resolved Green's-function components.

This is the formal layer corresponding to repo observables such as
`EqLt.g00_u` / `EqLt.g00_d` and `Uneqlt.gt0_u` / `Uneqlt.gt0_d`. -/
structure SpinResolvedGreen (α : Type) where
  up : α
  down : α

/-- Spin-averaged Green's-function component.

This is the formal layer corresponding to repo observables such as
`EqLt.g00` and `Uneqlt.gt0`. -/
structure SpinAveragedGreen (α : Type) where
  value : α

/-- Coefficient data for spin averaging.

In the current `meas.c` convention, this coefficient is `1/2`.
We keep it as data instead of hard-coding division so this file does not need
`Real`, `Rat`, or Mathlib at this stage. -/
structure SpinAverageCoeffs (α : Type) where
  half : α

/-- Generic code-level spin-average convention for Green's functions.

This formalizes the pattern
`spin_average = half * (spin_up + spin_down)`.
-/
def SpinAveragedGreen.fromSpin {α : Type} [Add α] [Mul α]
    (coeffs : SpinAverageCoeffs α) (g : SpinResolvedGreen α) :
    SpinAveragedGreen α :=
  { value := coeffs.half * (g.up + g.down) }

theorem green_spin_average_expr {α : Type} [Add α] [Mul α]
    (coeffs : SpinAverageCoeffs α) (g : SpinResolvedGreen α) :
    (SpinAveragedGreen.fromSpin coeffs g).value =
      coeffs.half * (g.up + g.down) := by
  rfl

/-- Equal-time Green's-function spin average.

This corresponds to the `meas.c` convention
`EqLt.g00 = 0.5 * (EqLt.g00_u + EqLt.g00_d)`. -/
theorem g00_spin_average_expr {α : Type} [Add α] [Mul α]
    (coeffs : SpinAverageCoeffs α) (g : SpinResolvedGreen α) :
    (SpinAveragedGreen.fromSpin coeffs g).value =
      coeffs.half * (g.up + g.down) := by
  rfl

/-- Unequal-time Green's-function spin average.

This corresponds to the `meas.c` convention
`Uneqlt.gt0 = 0.5 * (Uneqlt.gt0_u + Uneqlt.gt0_d)`. -/
theorem gt0_spin_average_expr {α : Type} [Add α] [Mul α]
    (coeffs : SpinAverageCoeffs α) (g : SpinResolvedGreen α) :
    (SpinAveragedGreen.fromSpin coeffs g).value =
      coeffs.half * (g.up + g.down) := by
  rfl

end DQMC.Green
