import DQMC.RepoMap
import DQMC.Density
import DQMC.Green
import DQMC.Current
import DQMC.Measurement

-- This file is generated from observables.yaml.
-- Do not edit by hand.

-- EqLt.density
#check DQMC.MeasVar.EqLt_density
#check DQMC.Obs.eq_density_total
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_density =
      DQMC.Obs.eq_density_total := rfl

-- EqLt.density_u
#check DQMC.MeasVar.EqLt_density_u
#check DQMC.Obs.eq_density_up
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_density_u =
      DQMC.Obs.eq_density_up := rfl

-- EqLt.density_d
#check DQMC.MeasVar.EqLt_density_d
#check DQMC.Obs.eq_density_down
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_density_d =
      DQMC.Obs.eq_density_down := rfl

-- EqLt.double_occ
#check DQMC.MeasVar.EqLt_double_occ
#check DQMC.Obs.eq_double_occupancy
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_double_occ =
      DQMC.Obs.eq_double_occupancy := rfl

-- EqLt.g00
#check DQMC.MeasVar.EqLt_g00
#check DQMC.Obs.eq_green_spin_average
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_g00 =
      DQMC.Obs.eq_green_spin_average := rfl

-- EqLt.g00_u
#check DQMC.MeasVar.EqLt_g00_u
#check DQMC.Obs.eq_green_up
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_g00_u =
      DQMC.Obs.eq_green_up := rfl

-- EqLt.g00_d
#check DQMC.MeasVar.EqLt_g00_d
#check DQMC.Obs.eq_green_down
example :
    DQMC.MeasToObs DQMC.MeasVar.EqLt_g00_d =
      DQMC.Obs.eq_green_down := rfl

-- Uneqlt.gt0
#check DQMC.MeasVar.Uneqlt_gt0
#check DQMC.Obs.uneq_green_spin_average
example :
    DQMC.MeasToObs DQMC.MeasVar.Uneqlt_gt0 =
      DQMC.Obs.uneq_green_spin_average := rfl

-- Uneqlt.gt0_u
#check DQMC.MeasVar.Uneqlt_gt0_u
#check DQMC.Obs.uneq_green_up
example :
    DQMC.MeasToObs DQMC.MeasVar.Uneqlt_gt0_u =
      DQMC.Obs.uneq_green_up := rfl

-- Uneqlt.gt0_d
#check DQMC.MeasVar.Uneqlt_gt0_d
#check DQMC.Obs.uneq_green_down
example :
    DQMC.MeasToObs DQMC.MeasVar.Uneqlt_gt0_d =
      DQMC.Obs.uneq_green_down := rfl

-- Uneqlt.jj
#check DQMC.MeasVar.Uneqlt_jj
#check DQMC.Obs.raw_current_current
example :
    DQMC.MeasToObs DQMC.MeasVar.Uneqlt_jj =
      DQMC.Obs.raw_current_current := rfl

-- observable relation: EqLt.density_sum_rule
#check DQMC.Density.density_total_eq_density_up_add_density_down
#check DQMC.Obs.eq_density_total
#check DQMC.Obs.eq_density_up
#check DQMC.Obs.eq_density_down

-- observable relation: EqLt.g00_spin_average
#check DQMC.Green.g00_spin_average_expr
#check DQMC.Obs.eq_green_spin_average
#check DQMC.Obs.eq_green_up
#check DQMC.Obs.eq_green_down

-- observable relation: Uneqlt.gt0_spin_average
#check DQMC.Green.gt0_spin_average_expr
#check DQMC.Obs.uneq_green_spin_average
#check DQMC.Obs.uneq_green_up
#check DQMC.Obs.uneq_green_down

-- derived observable: Uneqlt.projected_jj
#check DQMC.Obs.projected_current_current
#check DQMC.Current.projected_jj_from_raw_jj_q0
#check DQMC.MeasVar.Uneqlt_jj

-- derived observable: Uneqlt.JNJN
#check DQMC.Obs.elec_current_current
#check DQMC.Current.JNJN_eq_neg_projected_jj
#check DQMC.Obs.projected_current_current

-- derived observable: Uneqlt.JQJQ
#check DQMC.Obs.thermal_current_current
#check DQMC.Current.JQJQ_eq_thermal_projected_blocks
#check DQMC.Obs.projected_current_current

-- measurement pattern: meas_accumulated_contribution
#check DQMC.Measurement.contribution_eq_prefactor_mul_expr

-- measurement pattern: meas_normalized_prefactor
#check DQMC.Measurement.normalized_prefactor_value_eq_normalize_phase_degeneracy

-- measurement pattern: meas_normalized_contribution
#check DQMC.Measurement.normalized_contribution_eq_prefactor_value_mul_expr

