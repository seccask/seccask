#!/usr/bin/env bash

MODE=sgx
RA_MODE=tls
PREFIX=/home/mlcask/seccask-temp/scal-test
SCRIPT_PREFIX=/home/mlcask/sgx/encfspython/exp/scalability
NUM_LOOP=16

kill_enclaves() {
  # bash -c 'ps aux | awk '\''/sgx\/loader/ || /libpal.so/'\''| awk '\''{print $2}'\'' | xargs kill -9 2>/dev/null'
  kill -9 $(pgrep -f '.*libpal\.so.*' | grep -v ^$$\$)
}

MANIFEST=empty

SETUPS=(
  "empty;noop.py;venv/dummy;output/dummy"
)

component_id=0

echo "Exp: ${MANIFEST}"
echo "PREFIX: $PREFIX"
for S in "${SETUPS[@]}"; do
  i=0

  for (( ; i <= NUM_LOOP; i++)); do
    IFS=";" read -r -a SX <<<"${S}"
    COMPONENT_NAME="${SX[0]}"
    INPUT_PATH="$SCRIPT_PREFIX/$COMPONENT_NAME"
    INPUT_FILE="$INPUT_PATH/${SX[1]}"

    COMMAND=("gramine-$MODE" "/home/mlcask/sgx/encfspython/gramine_manifest/noop")
    # COMMAND+=("--key" "SECCASK_TEST_KEY")
    # COMMAND+=("--input" $INPUT_FILE)

    echo "========================================"
    echo "COMPONENT_NAME: $COMPONENT_NAME"
    # echo "INPUT_FILE: $INPUT_FILE"
    echo "COMMAND: ${COMMAND[@]}"
    echo "========================================"

    LOG_PATH="$PREFIX/dummy-test-2/${MANIFEST}-${MODE}-${RA_MODE}-encfs-$(printf "%02d\n" ${i}).log"

    sleep 1

    echo "Run: $i"

    # rm -rf $OUTPUT_FOLDER 2>/dev/null
    # mkdir -p $OUTPUT_FOLDER
    # echo "Reset: $OUTPUT_FOLDER"

    # cd $INPUT_PATH

    echo "Exec: cset shield --exec /usr/bin/time -- -v ${COMMAND[@]} 2>&1 | tee $LOG_PATH"
    cset shield --exec /usr/bin/time -- -v "${COMMAND[@]}" 2>&1 | tee $LOG_PATH
    echo "End: $i"

    # cd $PREFIX

    component_id=$((component_id + 1))
  done

  echo "Done: $COMPONENT_NAME"
  # kill_enclaves
  # echo "Killed: Enclaves"
done
