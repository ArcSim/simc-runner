# simc batch runner

Runs batches of [SimulationCraft](https://github.com/simulationcraft/simc) sims on GitHub Actions for an APL
tuning project.

- `build-simc` builds stock SimulationCraft at the commit pinned in `worker/setup.sh` and keeps the binary in the
  Actions cache.
- `sims` runs one batch. A push to a `jobs/...` branch carries the batch; 20 jobs each run their share and upload
  their results; the branch is deleted afterwards.

Batches and results are encrypted with a repository secret, so this repository holds only the runner scripts.
SimulationCraft (GPL-3.0) is built from its own source at the pinned commit and is not included here.
