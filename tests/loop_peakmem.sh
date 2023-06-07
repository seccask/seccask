#!/usr/bin/env bash

START=1
END=16

MODE=sgx
RA_MODE=ratls

LOG_DIR=peakmem_timev_2
MANIFESTS="dummy"

HOME=/home/mlcask

### FUNCTION: copy_worker_log
### DESCRIPTION: Copy the worker log to the log directory
### INPUT: $1 - worker log dir
### OUTPUT: None
### RETURN: None
copy_worker_log() {
  mkdir -p $1
  cp ${HOME}/seccask-temp/*.log $1
  # cp ${HOME}/seccask-temp/*.time $1
}

clean_workspace() {
  # nohup ssh ustore@localhost \
  #   'source $HOME/.ledgebase_profile; cd $HOME/ledgebase_release; ./bin/ustore_clean.sh; ./bin/ustore_start.sh' \
  #   >/dev/null 2>/dev/null &
  # sleep 10

  cd ..
  ./clean.sh -csp
  cd ./test
}

## Loop experiments (SGX, FS, PAC)
# sed -i 's/enable_compatibility_check_on_caching = false/enable_compatibility_check_on_caching = true/g' ${HOME}/sgx/seccask2/.conf/config.ini
# sed -i 's/enable = false/enable = true/g' ${HOME}/sgx/seccask2/.conf/config.ini
# sed -i 's/enable_compatibility_check_on_caching = true/enable_compatibility_check_on_caching = false/g' ${HOME}/sgx/seccask2/.conf/config.ini
# sed -i 's/enable = true/enable = false/g' ${HOME}/sgx/seccask2/.conf/config.ini

for ((i = START; i <= END; i++)); do
  # MANIFEST=cs_autolearn
  # RA_MODE=tls

  # EXP_NAME="al-${MODE}-${RA_MODE}-encfs-$(printf "%02d\n" ${i})"
  # WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
  # mkdir -p $WORKER_LOG_DIR

  # echo "${MANIFEST} - ${EXP_NAME} start"

  # clean_workspace
  # echo "${MANIFEST} - ${EXP_NAME} workspace cleaned"

  # cd ..
  # python seccask-exp.py ${MANIFEST} --setup=${MODE} --log-path="${WORKER_LOG_DIR}.log" --encfs
  # cd ./test

  # copy_worker_log $WORKER_LOG_DIR
  # echo "${MANIFEST} - ${EXP_NAME} worker log copied"

  # echo "${MANIFEST} - ${EXP_NAME} done"

  ##############################################################################

  # MANIFEST=sklmnist

  for MANIFEST in $MANIFESTS; do
    EXP_NAME="${MANIFEST}-${MODE}-${RA_MODE}-encfs-$(printf "%02d\n" ${i})"
    WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
    mkdir -p $WORKER_LOG_DIR

    echo "${MANIFEST} - ${EXP_NAME} start"

    clean_workspace
    echo "${MANIFEST} - ${EXP_NAME} workspace cleaned"

    cd ..
    python seccask-exp.py ${MANIFEST} --setup=${MODE} --log-path="${WORKER_LOG_DIR}.log" --encfs
    # exit
    sleep 1
    cd ./test

    copy_worker_log $WORKER_LOG_DIR
    echo "${MANIFEST} - ${EXP_NAME} worker log copied"

    echo "${MANIFEST} - ${EXP_NAME} done"
  done
done
