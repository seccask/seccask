# SecCask

## Overview

Modern data analytics pipelines are highly dynamic, as they are constantly monitored and fine-tuned by both data engineers and scientists. Recent systems for managing pipelines make it easy to create, deploy, and track their evolution. However, they do not consider the privacy of both the data and the computation, which becomes a challenge for adoption as many of these systems are offered as services on the public cloud with less or no trust. Our goal is to design a secure and efficient data analytics pipeline management system, in which multiple parties could collaborate by providing datasets and libraries to form pipelines. 

To this end, we present SecCask, which leverages hardware-backed trusted execution environments (TEEs) to ensure privacy. Our system overcomes the problems of a naive design that isolates complete pipeline execution in one enclave by administering enclaves and runtimes. Moreover, the objective of supporting fast-changing pipelines with components requiring low latency brings the challenge of reducing the cold start overhead - the main performance bottleneck in modern hardware. Our approach consists of reusing trusted runtimes for different pipeline components and caching them to avoid the cost of initialization. 

## Features

* Secure collaborative pipeline evolution with Intel SGX
* Runtime reusing and worker caching based on worker-component compatibility check
* Pipeline-aware Caching (PAC) strategy

## Installation

1. Install [Gramine](https://gramine.readthedocs.io/en/latest/) globally. For reproducibility, 
2. Build and install [PyZMQ](https://github.com/zeromq/pyzmq) 23.1.0 with ZeroMQ disabling `getifaddrs()`, as the API is not supported by Gramine and causes crashes. This can be done by undefining ZMQ_HAVE_IFADDRS. See source code [here](https://github.com/zeromq/libzmq/blob/37224c93de2c7c08602c79a2a1b4d7e582f09281/src/ip_resolver.cpp#L513).
3. Define the following variables:
    ```bash
    $ export APP_HOME=/PATH/TO/SECCASK
    $ export PYZMQ_HOME=/PATH/TO/PYZMQ-23.1.0
    ```
4. Copy project directory to `$APP_HOME`.
5. Create a Python 3.9 virtual environment with necessary packages:
    ```bash
    $ python -m venv venv
    $ source venv/bin/activate
    (venv) $ python -m pip install cffi colorama paramiko pyyaml
    ```

    Or use the requirements file to get a tested environment including necessary packages as well as commonly used data analytics and machine learning packages (Remember to change `/PATH/TO/PYZMQ-23.1.0`):

    ```bash
    (venv) $ python -m pip install -r requirements.txt
    ```
6. Build SecCask Gramine manifest in the virtual environment:
   
    ```bash
    (venv) $ cd $APP_HOME/gramine_manifest
    (venv) $ make && make SGX=1
    ```
    
    ---
    **NOTE**: The build process may fail with `ModuleNotFoundError: No module named 'graminelibos'`. If so, copy the corresponding package from the system-level package directory to that of `venv`:

    ```bash
    (venv) $ cp -r /usr/lib/python3/dist-packages/graminelibos /PATH/TO/VENV/lib/python3.9/site-packages
    ```
    
    ---
7. Comment line `SGX = "1"` in `gramine_manifest/python.manifest`:
   ```toml
   [loader.env]
   # SGX = "1"
   ```

## Start in Untrusted Mode

Run experiment `$EXP_NAME` with command:

```bash
(venv) $ PYTHONPATH=/PATH/TO/PYZMQ-23.1.0:$APP_HOME/src python $APP_HOME/start_exp.py $EXP_NAME
```

## Start in Trusted Mode

Run experiment `$EXP_NAME` with command:

```bash
(venv) $ gramine-sgx $APP_HOME/gramine_manifest/python $APP_HOME/start_exp.py $EXP_NAME
```

## Configuration

See commented configuration file `.conf/config.ini`.

## Experiments

SecCask supports running experiments specified by *experiment manifests*. Sample manifests are available under `exp/` directory. The `$EXP_NAME` in the experiment running commands are that of the manifest file name without `exp_` prefix and file extension. For example, if you want to execute the experiment specified in `exp_mlp2.yaml`, `$EXP_NAME` should be `mlp2`.

### Available Experiments

- mlp2
- mnist
- resnet18_c10
- sklmnist
- sklmnist_v1
- vgg16_c10
- vgg16_c10_v1

## Architecture

![SecCask Architecture](./.img/architecture.png)
