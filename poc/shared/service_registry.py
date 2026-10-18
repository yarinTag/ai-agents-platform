"""
Fault-Tolerant Pluggable Service Registry.
Ensures that every backend domain service is self-contained and decoupled:
if any individual service is disabled (via DISABLED_SERVICES env var) or disconnected,
the platform continues operating cleanly without startup failure.
"""

import importlib
import logging
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Sequence
from fastapi import FastAPI

logger = logging.getLogger(__name__)


@dataclass
class ServiceSpec:
    """Declarative specification for an independent backend service module."""
    name: str
    module_path: str
    prefix: str
    tags: List[str]
    requires_auth: bool = True
    attr_name: str = "router"


@dataclass
class ServiceStatusRecord:
    """Runtime status of a registered service module."""
    name: str
    prefix: str
    status: str  # MOUNTED, DISABLED, DEGRADED
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ServiceRegistry:
    """Manages isolated registration and health reporting of platform micro-services."""

    def __init__(self) -> None:
        self._records: Dict[str, ServiceStatusRecord] = {}

    @staticmethod
    def get_disabled_services() -> set[str]:
        raw = os.getenv("DISABLED_SERVICES", "")
        return {s.strip().lower() for s in raw.split(",") if s.strip()}

    def register_service(
        self,
        app: FastAPI,
        spec: ServiceSpec,
        auth_dependencies: Optional[Sequence[Any]] = None,
        package: Optional[str] = None
    ) -> ServiceStatusRecord:
        """
        Dynamically import and mount a service router onto the FastAPI app.
        Never crashes the host application if a service is disabled or missing.
        """
        disabled = self.get_disabled_services()
        if spec.name.lower() in disabled:
            record = ServiceStatusRecord(
                name=spec.name,
                prefix=spec.prefix,
                status="DISABLED"
            )
            self._records[spec.name] = record
            logger.info(f"Service '{spec.name}' is disabled via DISABLED_SERVICES")
            return record

        try:
            mod = importlib.import_module(spec.module_path, package=package)
            router = getattr(mod, spec.attr_name)
            deps = list(auth_dependencies) if (spec.requires_auth and auth_dependencies) else []
            app.include_router(
                router,
                prefix=spec.prefix,
                tags=spec.tags,
                dependencies=deps
            )
            record = ServiceStatusRecord(
                name=spec.name,
                prefix=spec.prefix,
                status="MOUNTED"
            )
            self._records[spec.name] = record
            return record
        except Exception as exc:
            logger.warning(f"Service '{spec.name}' ({spec.module_path}) disconnected: {exc}")
            record = ServiceStatusRecord(
                name=spec.name,
                prefix=spec.prefix,
                status="DEGRADED",
                error=str(exc)
            )
            self._records[spec.name] = record
            return record

    def mount_all(
        self,
        app: FastAPI,
        specs: Sequence[ServiceSpec],
        auth_dependencies: Optional[Sequence[Any]] = None,
        package: Optional[str] = None
    ) -> List[ServiceStatusRecord]:
        """Mount a sequence of ServiceSpec definitions onto the FastAPI app fault-tolerantly."""
        return [
            self.register_service(app, spec, auth_dependencies=auth_dependencies, package=package)
            for spec in specs
        ]

    def list_statuses(self) -> List[Dict[str, Any]]:
        """Return status of all registered platform services."""
        return [r.to_dict() for r in self._records.values()]

    def get_status_list(self) -> List[Dict[str, Any]]:
        """Alias for list_statuses."""
        return self.list_statuses()


service_registry = ServiceRegistry()
