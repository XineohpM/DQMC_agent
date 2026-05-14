namespace DQMC

inductive TimeKind where
  | equalTime
  | unequalTime
deriving DecidableEq, Repr

inductive SpinKind where
  | up
  | down
  | summed
  | averageUD
  | mixed
  | spinless
deriving DecidableEq, Repr

inductive MeasuredStage where
  | signWeightedAccumulator
  | signReweightedEstimator
  | physicalObservable
deriving DecidableEq, Repr

end DQMC