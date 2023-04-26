#!/bin/bash

cd /home/mlcask/seccask-temp && { rm -rf storage/*; rm *; rm -rf temp/*; rm -rf venv/*; rm -rf output/*; ln -s /data0/mlcask/scal-test scal-test ; }
