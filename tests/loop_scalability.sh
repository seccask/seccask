#!/usr/bin/env bash

PROGRAM=sgx
PREFIX=/home/mlcask/seccask-temp/scal-test
SCRIPT_PREFIX=/home/mlcask/sgx/encfspython/exp/scalability
NUM_CONCURRENT=65

kill_enclaves() {
  # bash -c 'ps aux | awk '\''/sgx\/loader/ || /libpal.so/'\''| awk '\''{print $2}'\'' | xargs kill -9 2>/dev/null'
  kill -9 $(pgrep -f '.*libpal\.so.*' | grep -v ^$$\$)
}

MANIFEST=autolearn

# declare -a SETUPS
# SETUPS[0]="al_IG;main_sonar_IG.py;venv/al_dataset;output/al_IG"
# SETUPS[1]="al_dependent_regression;main_sonar_dependent_regression.py;output/al_IG;output/al_dependent_regression"
# SETUPS[2]="al_stable;main_sonar_stable.py;output/al_dependent_regression;output/al_stable"
# SETUPS[3]="al_model;main_sonar_model.py;output/al_stable;output/model"

SETUPS=(
  # "al_IG;main_sonar_IG.py;venv/al_dataset;output/al_IG"
  # "al_dependent_regression;main_sonar_dependent_regression.py;output/al_IG;output/al_dependent_regression"
  "al_stable;main_sonar_stable.py;output/al_dependent_regression;output/al_stable"
  # "al_model;main_sonar_model.py;output/al_stable;output/al_model"
)

# MANIFEST=sa

# # declare -a SETUPS
# # SETUPS[0]="sa_preprocess;preprocess.py;venv/sa_dataset;output/sa_preprocess"
# # SETUPS[1]="sa_generate_embedding;Word2Vec_model.py;output/sa_preprocess;output/sa_generate_embedding"
# # SETUPS[2]="sa_generate_vector;generate_vector.py;output/sa_generate_embedding;output/sa_generate_vector"
# # SETUPS[3]="sa_MLP;mlp_residual_tune_cal_corr_mean_var_wd01_lambda1_beta1.py;output/sa_generate_vector;output/sa_MLP"

# SETUPS=(
#   "sa_preprocess;preprocess.py;venv/sa_dataset;output/sa_preprocess"
#   "sa_generate_embedding;Word2Vec_model.py;output/sa_preprocess;output/sa_generate_embedding"
#   "sa_generate_vector;generate_vector.py;output/sa_generate_embedding;output/sa_generate_vector"
#   "sa_MLP;mlp_residual_tune_cal_corr_mean_var_wd01_lambda1_beta1.py;output/sa_generate_vector;output/sa_MLP"
# )

component_id=0

echo "Exp: ${MANIFEST}"
echo "PREFIX: $PREFIX"
for S in "${SETUPS[@]}"; do
  # if (( $component_id == 1 )); then
  #   i=10
  # else
  #   i=0
  # fi
  i=0

  for (( ; i <= NUM_CONCURRENT; i++)); do
    IFS=";" read -r -a SX <<<"${S}"
    COMPONENT_NAME="${SX[0]}"
    INPUT_PATH="$SCRIPT_PREFIX/$COMPONENT_NAME"
    INPUT_FILE="$INPUT_PATH/${SX[1]}"
    INPUT_FOLDER="$PREFIX/${SX[2]}/0/"
    OUTPUT_FOLDER="$PREFIX/${SX[3]}/$i/"

    COMMAND=("gramine-$PROGRAM" "/home/mlcask/sgx/encfspython/gramine_manifest/encfspython")
    COMMAND+=("--key" "ENCFSPYTHON")
    COMMAND+=("--input" $INPUT_FILE)
    COMMAND+=("--args" "$INPUT_FOLDER,$OUTPUT_FOLDER")

    echo "========================================"
    echo "COMPONENT_NAME: $COMPONENT_NAME"
    echo "INPUT_FILE: $INPUT_FILE"
    echo "INPUT_FOLDER: $INPUT_FOLDER"
    echo "OUTPUT_FOLDER: $OUTPUT_FOLDER"
    echo "COMMAND: ${COMMAND[@]}"
    echo "========================================"

    LOG_PATH="$PREFIX/$MANIFEST.$COMPONENT_NAME.$i.log"

    sleep 1

    echo "Run: $i"

    # rm -rf $OUTPUT_FOLDER 2>/dev/null
    mkdir -p $OUTPUT_FOLDER
    # echo "Reset: $OUTPUT_FOLDER"

    cd $INPUT_PATH

    echo "Exec: cset shield --exec /usr/bin/time -- -v ${COMMAND[@]} 2>&1 | tee $LOG_PATH"
    coproc mypipe { cset shield --exec /usr/bin/time -- -v "${COMMAND[@]}" 2>&1 | tee $LOG_PATH; }
    # exec  | tee -a $LOG_PATH |
    while read l <&${mypipe[0]}; do
      # echo $l
      if [[ $l =~ "time interval" ]]; then
        # echo "FIND TIME INTERVAL"
        break
      fi
    done
    echo "End: $i"

    cd $PREFIX
    sleep 1

    component_id=$((component_id + 1))

    if [[ "$i" == 0 ]]; then
      kill_enclaves
      echo "Killed: Enclaves"
    fi
  done

  echo "Done: $COMPONENT_NAME"
  kill_enclaves
  echo "Killed: Enclaves"
done
