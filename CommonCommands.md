# SecCask 2 Common Commands

## Build

### CMake
```bash
cmake -DCMAKE_BUILD_TYPE=Debug -GNinja ..
```

### Build Gramine manifests

```bash
cd ../gramine_manifest; make clean; make; make SGX=1; cd ../build/
```

### Gramine: Change Gramine Python executable path

```bash
# Build Gramine
meson setup build/ --buildtype=debug -Ddirect=enabled -Dsgx=enabled -Ddcap=enabled
# Change Python executable path
sudo find /usr/local/bin -name 'gramine*' -exec sed -i 's/\/usr\/bin\/python3/\/usr\/bin\/env python3/' {} \;
# Remove previous graminelibos installation
rm -rf ~/scvenv-autolearn/lib/python3.9/site-packages/graminelibos
# Install graminelibos utility scripts as Python package
# (For v1.3 and below)
cp -r /usr/local/lib/python3.9/site-packages/graminelibos ~/scvenv-autolearn/lib/python3.9/site-packages
# (For v1.4)
cp -r /usr/local/lib/python3.9/dist-packages/graminelibos ~/scvenv-autolearn/lib/python3.9/site-packages
```


## Run

### Reset

```bash
# In repo root folder
./clean.sh -csp
```

### Forcely kill running enclaves (Use when starting by shell scripts)

```bash
ps aux | awk '/sgx\/loader/ || /libpal.so/'|  awk '{print $2}'  |  xargs kill -9 2>/dev/null

# or

ps aux | awk '/worker.py/ || /coordinator.py/ || /bin\/seccask/ || /gramine_manifest\/seccask/ || /libpal.so/'|  awk '{print $2}'  |  xargs kill -9 2>/dev/null
```

### Run on SKLMNIST

```bash
# No Gramine
## Use seccask-exp.py
python seccask-exp.py --setup untrusted sklmnist
## Manual
APP_HOME=~/sgx/seccask2 PYTHONHOME=~/sgx/lib/cpython-3.9.13-install PYTHONPATH=~/sgx/seccask2/pysrc ~/sgx/seccask2/build/bin/seccask --coordinator --mode=tls --manifest=sklmnist
# Gramine (Direct)
## Use seccask-exp.py
python seccask-exp.py --setup direct sklmnist
## Manual
gramine-direct ../gramine_manifest/seccask --coordinator --mode=tls --manifest=sklmnist
# Gramine (SGX)
## Use seccask-exp.py
python seccask-exp.py --setup sgx sklmnist
## Manual
gramine-sgx ../gramine_manifest/seccask --coordinator --mode=tls --manifest=sklmnist
```

### Run on AutoLearn

```bash
SECCASK_PROFILE_IO=1 APP_HOME=/home/mlcask/sgx/seccask2 PYTHONHOME=/home/mlcask/sgx/lib/cpython-3.9.13-install PYTHONPATH=/home/mlcask/sgx/seccask2/pysrc gramine-direct ../gramine_manifest/seccask --coordinator --mode=ratls --manifest=cs_autolearn -k SECCASK_TEST_KEY
```

#### Gramine (SGX)

## EncFS

### Regenerate sealed components

```bash
# In test-source/ folder
rm -rf ../enc-test-source/* ; env PYTHONHOME=~/sgx/lib/cpython-3.9.13-install     PYTHONPATH=~/scvenv-autolearn/lib/python3.9/site-packages     ~/sgx/encfspython/build/bin/encfspython     --input ~/sgx/test-source/enc.py --key SECCASK_TEST_KEY
```

### Run with Gramine-SGX with EncFS enabled on SKLMNIST

```bash
PYTHONHOME=~/sgx/lib/cpython-3.9.13-install PYTHONPATH=~/sgx/seccask2/pysrc:~/scvenv-autolearn/lib/python3.9/site-packages APP_HOME=~/sgx/seccask2 ~/sgx/seccask2/build/bin/seccask --coordinator --mode=tls --manifest=sklmnist -k SECCASK_TEST_KEY
```

### Run MonkeyTest

```bash
# In encfspython/ folder
PYTHONHOME=~/sgx/lib/cpython-3.9.13-install PYTHONPATH=~/scvenv-autolearn/lib/python3.9/site-packages gramine-sgx ./gramine_manifest/encfspython --input ~/sgx/encfspython/monkeytest.py --key ENCFSPYTHON --args -r,256,-w,256,-s,512,-f,/mnt/ramdisk/encfs/monkeytest
```

### MLPerf: Generate Sealed Dataset

```bash
# In the folder with enc.py
env PYTHONHOME=~/sgx/lib/cpython-3.9.13-install PYTHONPATH=~/scvenv-autolearn/lib/python3.9/site-packages ~/sgx/encfspython/build/bin/encfspython --input ./enc.py --key ENCFSPYTHON
```


## Debug

### Valgrind

```bash
PYTHONHOME=~/sgx/lib/cpython-3.9.13-install PYTHONPATH=~/sgx/seccask2/pysrc:~/scvenv-autolearn/lib/python3.9/site-packages PYTHONMALLOC=malloc valgrind --tool=memcheck --leak-check=full --suppressions=~/sgx/lib/cpython-3.9.13/Misc/valgrind-python.supp ./bin/seccask --coordinator --mode=tls --manifest=cs_autolearn > valgrind.log 2>&1
```


## Miscellaneous

### Git: Refresh Installation

```bash
# In install/ folder
cd .. && rm -rf ./install && git worktree add ./install -f --no-checkout --detach && cd install && git checkout HEAD -- .
```

### ImageNet to GCS

```bash
python imagenet_to_gcs.py --raw_data_dir=/data0/mlcask/ILSVRC/Data/CLS-LOC --local_scratch_dir=. --nogcs_upload

taskset -c 0 gramine-sgx ../gramine_manifest/encfspython --key ENCFSPYTHON --input imagenet_to_gcs.py --args --raw_data_dir=/data0/mlcask/ILSVRC/Data/CLS-LOC,--local_scratch_dir=/mnt/ramdisk/encfs,--nogcs_upload > sgx-encfs_minfa-aes256sha256-avx2.log 2>&1
```

### Clean Python Cache

```bash
find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete

# or

./clean.sh -c
```
