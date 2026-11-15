"""Pure projection for compatibility proof; not connected to production routes."""

from .contracts.resources import HostResource
from .models import Host


def project_host(host: Host) -> HostResource:
    """Keep the canonical legacy host UUID and leave its stored model untouched."""
    return HostResource(id=host.id, name=host.name)
