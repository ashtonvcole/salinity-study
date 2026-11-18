module purge
conda activate tracer-post-env

# Claude suggestions
export CC="$CONDA_PREFIX/bin/$(basename "$(ls $CONDA_PREFIX/bin/*-gcc | head -1)")" # Ensure C++ compiler is correct
export MPIR_CVAR_PMI_VERSION=1 # Some underlying issue
export XALT_EXECUTABLE_TRACKING=no # Efficiency
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 # Efficiency
export XDG_CACHE_HOME=$WORK/.cache # Cache to work, not home