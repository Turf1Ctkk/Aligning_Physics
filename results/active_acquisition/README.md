# Active command design

This G1 adaptation adds bounded excitation to recorded ankle commands. Design uses an information matrix estimated from gain sensitivities. It compares unchanged, random and optimized inputs with equal collection and refitting budgets.

All revised acquisitions pass command-alignment checks. Held-out body errors are 9.34, 8.68 and 9.17 mm for unchanged, random and optimized inputs. A better information proxy does not give the best position result here. The preselected optimized arm's Squat policy completes 95.8% of evaluations.

The first acquisition attempt failed feasibility checks. Its records are preserved. The revision uses the first eligible window from every original parent, with no dropped parent or relaxed limit. It also changes motion phase, so improvement over the older passive fit cannot be assigned to excitation alone.

This prerecorded-command interface differs from SPI-Active's Go2 controller. [Revision](revision.json), [acquisition audit](acquisition_audit.json) and [replay results](replay_comparison.json) give the evidence.
