"""
Alternative async services-based architecture - DEPRECATED.

This module redirects to the legacy version for backward compatibility.
Use sally.main_async_services instead.

Migration:
- SmartGridMonitoringSystem -> sally.main_async_services.SmartGridMonitoringSystem
- main() -> sally.main_async_services.main()
"""
import warnings

# Redirect to legacy module
from sally.legacy.alt_main import SmartGridMonitoringSystem, main

__all__ = ['SmartGridMonitoringSystem', 'main']

# Issue deprecation warning on import
warnings.warn(
    "sally.alt_main is deprecated. Use sally.main_async_services instead.",
    DeprecationWarning,
    stacklevel=2
)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
