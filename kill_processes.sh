ps aux | awk '/worker.py/ || /coordinator.py/'|  awk '{print $2}'  |  xargs kill -9 2>/dev/null
