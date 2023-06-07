#!/usr/bin/env bash

START=1
END=1

### FUNCTION: copy_worker_log
### DESCRIPTION: Copy the worker log to the log directory
### INPUT: $1 - worker log dir
### OUTPUT: None
### RETURN: None
copy_worker_log () {
  mkdir -p $1
  cp ${HOME}/seccask-temp/*.log $1
}

clean_workspace () {
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


  ### Loop experiments (Raw, PAC)
  # MANIFEST=autolearn
  # LOG_DIR=autolearn_cacheeffect
  # RA_MODE=tls
  # EXP_NAME="sgx-raw-`printf "%02d\n" ${i}`"
  # WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"

  # echo "${EXP_NAME} start"

  # # clean_workspace
  # # echo "${EXP_NAME} workspace cleaned"

  # echo "SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
  #   PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
  #   gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_${i} -k SECCASK_TEST_KEY \
  #   > \"${WORKER_LOG_DIR}.log\" 2>&1"
  # SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
  #   PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
  #   gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_${i} -k SECCASK_TEST_KEY \
  #   > "${WORKER_LOG_DIR}.log" 2>&1

  # copy_worker_log $WORKER_LOG_DIR
  # echo "${EXP_NAME} worker log copied"
  
  # echo "${EXP_NAME} done"


# for ((i=1;i<=5;i++)); do
#   ### Loop experiments (Raw, PAC)
#   MANIFEST=sa
#   LOG_DIR=sa_cacheeffect
#   RA_MODE=tls
#   EXP_NAME="sgx-raw-`printf "%02d\n" ${i}`"
#   WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"

#   echo "${EXP_NAME} start"

#   # clean_workspace
#   # echo "${EXP_NAME} workspace cleaned"

#   echo "SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_${i} \
#     > \"${WORKER_LOG_DIR}.log\" 2>&1"
#   SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_${i} \
#     > "${WORKER_LOG_DIR}.log" 2>&1

#   copy_worker_log $WORKER_LOG_DIR
#   echo "${EXP_NAME} worker log copied"
  
#   echo "${EXP_NAME} done"
# done

### Loop experiments (Raw, PAC)
MANIFEST=autolearn
LOG_DIR=autolearn_cacheeffect
RA_MODE=tls
EXP_NAME="sgx-raw-`printf "%02d\n" ${i}`"
WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"

echo "${EXP_NAME} start"

# clean_workspace
# echo "${EXP_NAME} workspace cleaned"

echo "SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
  PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
  gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_ce \
  > \"${WORKER_LOG_DIR}.log\" 2>&1"
SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
  PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
  gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST}_ce \
  > "${WORKER_LOG_DIR}.log" 2>&1

copy_worker_log $WORKER_LOG_DIR
echo "${EXP_NAME} worker log copied"

echo "${EXP_NAME} done"
