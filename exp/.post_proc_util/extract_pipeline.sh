#!/bin/bash

# Extract pipeline duration by grep "Pipeline duration" from all .log files in the current directory

for file in *.log
do
    echo Pipeline duration
    echo -n "${file::-4} "
    grep "Pipeline duration" $file | cut -d"|" -f3 | cut -c 27- | tr '\n' ' '
    echo 
done

for file in *.log
do
    echo Component breakdown duration
    echo -n "${file::-4} "
    grep "NODE TIME" 
    echo 
done