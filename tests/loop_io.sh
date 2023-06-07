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

for ((i=START;i<=END;i++)); do
  MANIFEST=cs_autolearn
  LOG_DIR=autolearn_io_size
  RA_MODE=tls

  EXP_NAME="sgx-encfs-`printf "%02d\n" ${i}`"
  WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
  mkdir -p $WORKER_LOG_DIR

  echo "${MANIFEST} - ${EXP_NAME} start"
  
  clean_workspace
  echo "${MANIFEST} - ${EXP_NAME} workspace cleaned"
  
  echo "SECCASK_PROFILE_IO=1 SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
    PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
    gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST} -k SECCASK_TEST_KEY \
    > \"${WORKER_LOG_DIR}.log\" 2>&1"
  SECCASK_PROFILE_IO=1 SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
    PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
    gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST} -k SECCASK_TEST_KEY \
    > "${WORKER_LOG_DIR}.log" 2>&1
  
  copy_worker_log $WORKER_LOG_DIR
  echo "${MANIFEST} - ${EXP_NAME} worker log copied"
  
  echo "${MANIFEST} - ${EXP_NAME} done"

  ##############################################################################

  MANIFEST=cs_sa
  LOG_DIR=sa_io_size
  RA_MODE=tls

  EXP_NAME="sgx-encfs-`printf "%02d\n" ${i}`"
  WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
  mkdir -p $WORKER_LOG_DIR

  echo "${MANIFEST} - ${EXP_NAME} start"
  
  clean_workspace
  echo "${MANIFEST} - ${EXP_NAME} workspace cleaned"
  
  echo "SECCASK_PROFILE_IO=1 SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
    PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
    gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST} -k SECCASK_TEST_KEY \
    > \"${WORKER_LOG_DIR}.log\" 2>&1"
  SECCASK_PROFILE_IO=1 SGX=1 APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
    PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
    gramine-sgx ../gramine_manifest/seccask --coordinator --mode=${RA_MODE} --manifest=${MANIFEST} -k SECCASK_TEST_KEY \
    > "${WORKER_LOG_DIR}.log" 2>&1
  
  copy_worker_log $WORKER_LOG_DIR
  echo "${MANIFEST} - ${EXP_NAME} worker log copied"
  
  echo "${MANIFEST} - ${EXP_NAME} done"
done

### Loop experiments (Raw, PAC)
# MANIFEST=cs_autolearn
# LOG_DIR=sa_pac_torch141_02
# sed -i 's/enable_compatibility_check_on_caching = false/enable_compatibility_check_on_caching = true/g' ${HOME}/sgx/seccask2/.conf/config.ini

# for ((i=START;i<=END;i++)); do
#   EXP_NAME="raw-`printf "%02d\n" ${i}`"
#   WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"

#   echo "${EXP_NAME} start"

#   clean_workspace
#   echo "${EXP_NAME} workspace cleaned"

#   echo "APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > \"${WORKER_LOG_DIR}.log\" 2>&1"
#   APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > "${WORKER_LOG_DIR}.log" 2>&1
  
#   copy_worker_log $WORKER_LOG_DIR
#   echo "${EXP_NAME} worker log copied"
  
#   echo "${EXP_NAME} done"
# done

# ## Loop experiments (Raw, FS, PAC)
# MANIFEST=cs_autolearn
# LOG_DIR=autolearn_pac_fscopy
# # MANIFEST=cs_sa
# # LOG_DIR=sa_pac_torch141_fscopy

# sed -i 's/enable_compatibility_check_on_caching = false/enable_compatibility_check_on_caching = true/g' ${HOME}/sgx/seccask2/.conf/config.ini
# sed -i 's/enable = true/enable = false/g' ${HOME}/sgx/seccask2/.conf/config.ini

# for ((i=START;i<=END;i++)); do
#   EXP_NAME="raw-`printf "%02d\n" ${i}`"
#   WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
#   mkdir -p $WORKER_LOG_DIR

#   echo "${EXP_NAME} start"

#   clean_workspace
#   echo "${EXP_NAME} workspace cleaned"

#   echo "APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > \"${WORKER_LOG_DIR}.log\" 2>&1"
#   APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > "${WORKER_LOG_DIR}.log" 2>&1
  
#   copy_worker_log $WORKER_LOG_DIR
#   echo "${EXP_NAME} worker log copied"
  
#   echo "${EXP_NAME} done"
# done

# ## Loop experiments (Raw, FS, PAC)
# # MANIFEST=cs_autolearn
# # LOG_DIR=autolearn_pac_fscopy
# MANIFEST=cs_sa
# LOG_DIR=sa_pac_torch141_fscopy

# sed -i 's/enable_compatibility_check_on_caching = false/enable_compatibility_check_on_caching = true/g' ${HOME}/sgx/seccask2/.conf/config.ini
# sed -i 's/enable = true/enable = false/g' ${HOME}/sgx/seccask2/.conf/config.ini

# for ((i=START;i<=END;i++)); do
#   EXP_NAME="raw-`printf "%02d\n" ${i}`"
#   WORKER_LOG_DIR="${HOME}/sgx/logs/${LOG_DIR}/${EXP_NAME}"
#   mkdir -p $WORKER_LOG_DIR

#   echo "${EXP_NAME} start"

#   clean_workspace
#   echo "${EXP_NAME} workspace cleaned"

#   echo "APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > \"${WORKER_LOG_DIR}.log\" 2>&1"
#   APP_HOME=${HOME}/sgx/seccask2 PYTHONHOME=${HOME}/sgx/lib/cpython-3.9.13-install \
#     PYTHONPATH=${HOME}/sgx/seccask2/pysrc \
#     ../build/bin/seccask --coordinator --mode=tls --manifest=${MANIFEST} > "${WORKER_LOG_DIR}.log" 2>&1
  
#   copy_worker_log $WORKER_LOG_DIR
#   echo "${EXP_NAME} worker log copied"
  
#   echo "${EXP_NAME} done"
# done