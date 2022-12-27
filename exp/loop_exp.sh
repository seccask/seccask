#!/bin/bash

START=1
END=2

PROGRAM_NAME=gramine-sgx
SYSTEM=scsgx-nopac

EXP=sklmnist_v1
EPC_SIZE=768mb


clean_workspace () {
  cd ..
  ./clean_cache.sh ; ./clean_storage.sh ; ./kill_processes.sh
}

clean_workspace

# Loop experiments
for ((i=START;i<=END;i++)); do
  cd ./gramine_manifest
  
  echo "Round $i start"
  { time $PROGRAM_NAME python ../start_exp.py ${EXP}; } > "/nfs/host/sgx/logs/${EXP}-${SYSTEM}-${EPC_SIZE}-${i}" 2>&1
  clean_workspace
  echo "Round $i done"
done
