#!/usr/bin/env bash
# NOTE: Requires GNU getopt
# On MacOS and FreeBSD, this has to be installed separately
PROG_NAME='seccask-clean'
SECCASK_HOME=$PWD
STORAGE_DIR='/home/mlcask/seccask-temp'

#===== Argument Parsing =====
usage()
{
  echo "Usage: $PROG_NAME [ -c | --cache ]
                     [ -s | --storage ] 
                     [ -p | --process ]"
  exit 2
}
ARGS=$(getopt -o csp --long cache,storage,process -n $PROG_NAME -- "$@")
if [ "$?" != "0" ]; then
  usage
fi
eval set -- "$ARGS"
#===== End Argument Parsing =====

#===== Functions =====
clean_cache()
{
  find $SECCASK_HOME -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete
}

clean_storage()
{
  cd $STORAGE_DIR && {
    rm *
    rm -rf storage/*
    rm -rf temp/*
    rm -rf venv/*
    rm -rf output/*
    ln -s /data0/mlcask/scal-test scal-test
  }
}

kill_process()
{
  ps aux \
  | awk '/worker.py/ \
    || /coordinator.py/ \
    || /bin\/seccask/ \
    || /gramine_manifest\/seccask/ \
    || /libpal.so/' \
  | awk '{print $2}' \
  | xargs kill -9 2>/dev/null
}
#===== End Functions =====

while true; do
  case "$1" in
    -c | --cache ) echo '[cleaning cache]' ; clean_cache ; echo '[done]' ; shift ;;
    -s | --storage ) echo '[cleaning storage]' ; clean_storage ; echo '[done]' ; shift ;;
    -p | --process ) echo '[killing process]' ; kill_process ; echo '[done]' ; shift ;;
    # -- means the end of the arguments; drop this, and break out of the while loop
    -- ) shift ; break ;;
    # If invalid options were passed, then getopt should have reported an error,
    # which we checked as $ARGS when getopt was called
    * ) usage ;;
  esac
done
