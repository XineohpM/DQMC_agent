#!/usr/bin/env bash
set -euo pipefail

cd /home/users/phoenixm/DQMC_agent

export PATH="/home/users/phoenixm/.npm-global/bin:/share/software/user/open/nodejs/25.3.0/bin:/home/users/phoenixm/DQMC_agent/.venv/bin:/share/software/user/open/python/3.12.1/bin:/share/software/user/open/openssl/3.0.7/bin:/share/software/user/open/sqlite/3.44.2/bin:/share/software/user/open/ncurses/6.4/bin:/share/software/user/open/gcc/12.4.0/bin:${PATH:-}"

export LD_LIBRARY_PATH="/share/software/user/open/python/3.12.1/lib:/share/software/user/open/openssl/3.0.7/lib64:/share/software/user/open/openssl/3.0.7/lib:/share/software/user/open/gcc/12.4.0/lib64:/share/software/user/open/gcc/12.4.0/lib:/share/software/user/open/gcc/12.4.0/lib/gcc/x86_64-pc-linux-gnu:/share/software/user/open/libffi/3.2.1/lib64:/share/software/user/open/sqlite/3.44.2/lib:/share/software/user/open/readline/8.2/lib:/share/software/user/open/ncurses/6.4/lib:/share/software/user/open/tcltk/8.6.6/lib:/share/software/user/open/zlib/1.2.11/lib:${LD_LIBRARY_PATH:-}"

export DQMC_ALLOWED_ROOTS="${DQMC_ALLOWED_ROOTS:-/scratch/users/phoenixm/dqmc_runs:/home/users/phoenixm/DQMC_agent}"
export DQMC_OUTPUT_ROOT="${DQMC_OUTPUT_ROOT:-/home/users/phoenixm/dqmc_agent_outputs}"

if [ -f "/home/users/phoenixm/DQMC_agent/formal/observables.yaml" ]; then
  export DQMC_OBSERVABLE_REGISTRY="/home/users/phoenixm/DQMC_agent/formal/observables.yaml"
fi

{
  echo "===== dqmc MCP wrapper start: $(date) ====="
  echo "PWD=$PWD"
  echo "PATH=$PATH"
  echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
  echo "DQMC_ALLOWED_ROOTS=${DQMC_ALLOWED_ROOTS:-}"
  echo "DQMC_OUTPUT_ROOT=${DQMC_OUTPUT_ROOT:-}"
  echo "DQMC_OBSERVABLE_REGISTRY=${DQMC_OBSERVABLE_REGISTRY:-}"
  /home/users/phoenixm/DQMC_agent/.venv/bin/python -c 'import sys; print(sys.executable); import ssl; print("ssl ok"); import h5py; print("h5py ok"); import numpy; print("numpy ok"); import dqmc_tools; print("dqmc_tools ok", dqmc_tools.__file__)'
  echo "===== starting dqmc_mcp_server.py ====="
} >> /home/users/phoenixm/DQMC_agent/dqmc_mcp_debug.log 2>&1

exec /home/users/phoenixm/DQMC_agent/.venv/bin/python \
  /home/users/phoenixm/DQMC_agent/dqmc_mcp_server.py \
  2>> /home/users/phoenixm/DQMC_agent/dqmc_mcp_debug.log
