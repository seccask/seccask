ps aux | awk '/worker.py/ || /coordinator.py/ || /bin\/seccask/ || /gramine_manifest\/seccask/ || /libpal.so/'|  awk '{print $2}'  |  xargs kill -9 2>/dev/null
