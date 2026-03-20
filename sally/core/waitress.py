import time

def high_precision_wait(duration: float, sleep_tolerance: float = 0.002) -> None:
    """
    Waits for a specific duration with high precision, releasing the GIL
    for most of the time but spinning at the end for accuracy.

    :param duration: Total time to wait in seconds.
    :param sleep_tolerance: Time (s) before the deadline to switch from sleep to busy-wait.
                            Default 2ms handles most OS scheduling jitter.
    """
    target_time = time.perf_counter() + duration

    # Non-blocking sleep segment
    while True:
        remaining = target_time - time.perf_counter()
        if remaining < sleep_tolerance:
            break
        # Sleep for a chunk of the remaining time to yield CPU
        # Subtracting tolerance ensures we wake up slightly early
        time.sleep(remaining - sleep_tolerance)

    # Busy-wait segment (high precision)
    while time.perf_counter() < target_time:
        pass
