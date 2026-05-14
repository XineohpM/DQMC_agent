import DQMC.Obs

namespace DQMC.Current

/-- Imaginary-time index. In the Python arrays this corresponds to the tau axis. -/
abbrev TauIndex := Nat

/-- Bond-type index. In jqjq.py this corresponds to the `itype` / `jtype` axes of `jj_q0`. -/
abbrev BondType := Nat

/-- Tensor component of the electric current-current correlator. -/
inductive CurrentComponent where
  | xx
  | yy
  | xy
  | yx
deriving DecidableEq, Repr

/-- Raw q=0 bond-bond current correlator extracted from `/meas_uneqlt/jj`.

This corresponds to the `jj_q0[:, :, itype, jtype]` object in `jqjq.py`,
after the repo variable `Uneqlt.jj` has been loaded and the q=0 component has
been selected. The bin/sample axis is intentionally omitted here; this file
formalizes the deterministic observable transformation for a fixed averaged
input. -/
structure RawJJQ0 (α : Type) where
  value : TauIndex → BondType → BondType → α

/-- Bond geometry and hopping data used to project raw bond-bond correlations
onto Cartesian electric-current components. -/
structure BondGeometry (α : Type) where
  t  : BondType → α
  dx : BondType → α
  dy : BondType → α

/-- The bond-projected current-current tensor before the final extra minus sign.

This corresponds to `np.stack((jj_xx, jj_yy, jj_xy, jj_yx), axis=0)` in
`jqjq.py`, before applying `(-1) * ...`. -/
structure ProjectedJJ (α : Type) where
  value : CurrentComponent → TauIndex → α

/-- Physical/electric JNJN correlator after applying the jqjq.py sign convention. -/
structure JNJN (α : Type) where
  value : CurrentComponent → TauIndex → α

/-- Component-wise bond-projection kernel.

For components `(a,b)`, this returns the geometric factor
`t_i * t_j * d_i^a * d_j^b` used in `jqjq.py`. -/
def projectionWeight {α : Type} [Mul α]
    (geom : BondGeometry α) (comp : CurrentComponent)
    (itype jtype : BondType) : α :=
  match comp with
  | .xx => geom.t itype * geom.t jtype * geom.dx itype * geom.dx jtype
  | .yy => geom.t itype * geom.t jtype * geom.dy itype * geom.dy jtype
  | .xy => geom.t itype * geom.t jtype * geom.dx itype * geom.dy jtype
  | .yx => geom.t itype * geom.t jtype * geom.dy itype * geom.dx jtype

/-- Abstract finite bond-type summation supplied by the caller.

The current formal layer does not yet commit to a concrete finite bond-type set.
This functional represents the double sum over `itype, jtype` in `jqjq.py`. -/
abbrev BondTypeDoubleSum (α : Type) := (BondType → BondType → α) → α

/-- Project raw q=0 `jj` onto `(xx, yy, xy, yx)` current-current components.

This formalizes the jqjq.py step
`jj_ab += t_i * t_j * d_i^a * d_j^b * jj_q0[:, :, i, j]`.
-/
def ProjectedJJ.fromRawJJQ0 {α : Type} [Mul α]
    (sumBondTypes : BondTypeDoubleSum α)
    (geom : BondGeometry α) (jj : RawJJQ0 α) : ProjectedJJ α :=
  { value := fun comp τ =>
      sumBondTypes (fun itype jtype =>
        projectionWeight geom comp itype jtype * jj.value τ itype jtype) }

theorem projected_jj_from_raw_jj_q0 {α : Type} [Mul α]
    (sumBondTypes : BondTypeDoubleSum α)
    (geom : BondGeometry α) (jj : RawJJQ0 α) :
    (ProjectedJJ.fromRawJJQ0 sumBondTypes geom jj).value =
      fun comp τ =>
        sumBondTypes (fun itype jtype =>
          projectionWeight geom comp itype jtype * jj.value τ itype jtype) := by
  rfl

/-- Apply the jqjq.py sign convention:
`result_dict["JNJN"] = (-1) * np.stack((jj_xx, jj_yy, jj_xy, jj_yx), axis=0)`.
-/
def JNJN.fromProjectedJJ {α : Type} [Neg α]
    (jj : ProjectedJJ α) : JNJN α :=
  { value := fun comp τ => - jj.value comp τ }

theorem JNJN_eq_neg_projected_jj {α : Type} [Neg α]
    (jj : ProjectedJJ α) :
    (JNJN.fromProjectedJJ jj).value =
      fun comp τ => - jj.value comp τ := by
  rfl

end DQMC.Current