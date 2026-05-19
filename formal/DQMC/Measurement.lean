namespace DQMC.Measurement

/-- A single contribution added to a measurement accumulator in `meas.c`.

Many measurement lines in `meas.c` have the code-level form
`m->field[...] += pre * expr`, where `pre` has already absorbed factors
such as the Monte Carlo sign/phase and the degeneracy normalization.

This first formal layer intentionally stores `pre` directly as
`prefactor`, rather than formalizing division such as `phase / degen`.
-/
structure AccumulatedContribution (α : Type) where
  prefactor : α
  expr : α

/-- The value contributed to the accumulator by one measured expression. -/
def contribution {α : Type} [Mul α]
    (c : AccumulatedContribution α) : α :=
  c.prefactor * c.expr

theorem contribution_eq_prefactor_mul_expr {α : Type} [Mul α]
    (c : AccumulatedContribution α) :
    contribution c = c.prefactor * c.expr := by
  rfl

/-- A normalized prefactor split into a sign/phase factor and a degeneracy factor.

This is a slightly more explicit version of the common `meas.c` convention
`pre = phase / degen`. The division itself is represented through a supplied
`normalize` function so this file does not need to commit to `Real`, division,
or Mathlib yet. -/
structure NormalizedPrefactor (α : Type) where
  phase : α
  degeneracy : α
  normalize : α → α → α

/-- Construct the code-level prefactor from phase/sign and degeneracy data. -/
def NormalizedPrefactor.value {α : Type}
    (p : NormalizedPrefactor α) : α :=
  p.normalize p.phase p.degeneracy

theorem normalized_prefactor_value_eq_normalize_phase_degeneracy {α : Type}
    (p : NormalizedPrefactor α) :
    p.value = p.normalize p.phase p.degeneracy := by
  rfl

/-- A measured contribution whose prefactor is represented by phase/sign and
degeneracy data. -/
structure NormalizedContribution (α : Type) where
  prefactor : NormalizedPrefactor α
  expr : α

/-- Contribution using the normalized prefactor. -/
def normalizedContribution {α : Type} [Mul α]
    (c : NormalizedContribution α) : α :=
  c.prefactor.value * c.expr

theorem normalized_contribution_eq_prefactor_value_mul_expr {α : Type} [Mul α]
    (c : NormalizedContribution α) :
    normalizedContribution c = c.prefactor.value * c.expr := by
  rfl

end DQMC.Measurement
