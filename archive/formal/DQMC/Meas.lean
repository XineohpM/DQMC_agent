import DQMC.Basic

namespace DQMC

inductive MeasVar where
  | EqLt_density
  | EqLt_density_u
  | EqLt_density_d
  | EqLt_double_occ

  | EqLt_g00
  | EqLt_g00_u
  | EqLt_g00_d

  | Uneqlt_gt0
  | Uneqlt_gt0_u
  | Uneqlt_gt0_d

  | Uneqlt_jj
deriving DecidableEq, Repr

end DQMC