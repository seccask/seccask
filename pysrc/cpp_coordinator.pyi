from typing import List

def get_component_key() -> str:
    """Get Component Key. Debugging purpose only.

    Returns:
        str: The component key.
    """
    ...

def on_new_pipeline(pipeline: List[str], ids: List[str]) -> None:
    """On New Pipeline callback.

    When a new pipeline is created, this method is called to notify the coordinator.
    
    Args:
        pipeline (List[str]): Component names with versions.
        ids (List[str]): The candidate component IDs in the pipeline.
        
    Example:
    ```
    cpp_coordinator.on_new_pipeline(
        [x.to_string(with_version=True) for x in proposed_workspace.pipeline],
        candidate_ids,
    )
    ```
    """
    ...

def on_new_component(info: List[str]) -> float:
    """On New Component callback.

    When a new component is created, this method is called to notify the coordinator.
    
    Args:
        info (List[str]): The information of the new component.
    
    Returns:
        float: I/O time for component.
        
    Example:
    ```
    cpp_coordinator.on_new_component(
        [candidate_id, working_dir, encryption_key, *cmds]
    )
    ```
    """
    ...

def on_cache_full(worker_id: str) -> None:
    """On Cache Full callback.
    
    When a worker's cache is full, this method is called to notify the coordinator to reclaim one worker.
    
    Args:
        worker_id (str): The ID of the worker to be reclaimed.
    """
    ...
