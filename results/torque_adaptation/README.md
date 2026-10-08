# Torque correction on common data

A shared MLP learns corrective ankle torques through PPO. It uses 20 history samples and runs at 200 Hz. Target recordings are measured at 50 Hz; source histories are actually measured at 200 Hz. Interpolation does not create high-rate target measurements.

Validation selects update 1,000. Held-out body error falls from 36.69 to 24.48 mm, while joint-velocity RMSE rises from 0.86174 to 0.95127 rad/s. The Squat policy completes 100.0% of evaluations, matching ordinary fine-tuning. Its full-motion body error is higher: 105.12 versus 94.45 mm.

This is a UAN-inspired actuator adaptation. It is not a state-transition residual model. Different architectures and PPO transition counts prevent a controlled action-versus-torque ranking. [Raw replay and policy evidence](.).
