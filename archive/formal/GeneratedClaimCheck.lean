import DQMC

-- This file is generated from an agent claims JSON file.
-- Do not edit by hand.

-- claim_id: Uneqlt.jj_maps_to_raw_current_current
-- claim repo variable: Uneqlt.jj
#check DQMC.MeasVar.Uneqlt_jj
#check DQMC.Obs.raw_current_current
example :
    DQMC.MeasToObs DQMC.MeasVar.Uneqlt_jj =
      DQMC.Obs.raw_current_current := rfl

-- claim_id: Uneqlt.JNJN_from_projected_jj
-- claim derived observable: Uneqlt.JNJN
#check DQMC.Obs.elec_current_current
#check DQMC.Current.JNJN_eq_neg_projected_jj
#check DQMC.Obs.projected_current_current

-- claim_id: EqLt.density_sum_rule
-- claim observable relation: EqLt.density_sum_rule
#check DQMC.Density.density_total_eq_density_up_add_density_down
#check DQMC.Obs.eq_density_total
#check DQMC.Obs.eq_density_up
#check DQMC.Obs.eq_density_down

-- claim_id: meas_accumulator_pattern
-- claim measurement pattern: meas_accumulated_contribution
#check DQMC.Measurement.contribution_eq_prefactor_mul_expr

