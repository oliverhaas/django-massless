"""High-performance Django API framework with a Cython request pipeline that
defers Django object materialization until touched.
"""

from massless.app import MasslessAPI

__all__ = ["MasslessAPI"]
