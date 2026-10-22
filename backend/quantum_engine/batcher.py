"""
Circuit Batching utility for quantum circuit execution.
Partitions large quantum circuit jobs into chunks to comply with hardware limits (e.g., IBM Quantum max circuits per job).
"""

def calculate_batches(total_circuits: int, max_per_job: int = 300) -> list[int]:
    """
    Calculates batch chunk sizes for a given number of total circuits.
    
    Args:
        total_circuits: Total count of quantum circuits to execute.
        max_per_job: Maximum circuits allowable in a single job submission (default 300).
        
    Returns:
        List of integer batch sizes. E.g., passing 750 with max_per_job=300 returns [300, 300, 150].
    """
    if total_circuits <= 0:
        return []
    if max_per_job <= 0:
        raise ValueError("max_per_job must be greater than 0")

    full_batches = total_circuits // max_per_job
    remainder = total_circuits % max_per_job

    batches = [max_per_job] * full_batches
    if remainder > 0:
        batches.append(remainder)
    return batches
