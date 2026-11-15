"""Small adapter ports; no provider implementation or execution entrance."""

from typing import Protocol

from .capabilities import CapabilityAssessment, CapabilityDefinition
from .resources import ResourceRef


class PayloadValidator[PayloadT](Protocol):
    """Adapters validate untrusted values into immutable feature DTOs exactly once."""

    def validate(self, value: object) -> PayloadT:
        """Reject invalid input without leaking response data in exceptions."""


class CapabilityProvider[InputT, OutputT](Protocol):
    """One typed capability binding; observation must not trigger mutations."""

    @property
    def provider_id(self) -> str:
        """Return a stable namespaced provider identifier."""

    @property
    def definition(self) -> CapabilityDefinition:
        """Declare the versioned operation, including schemas and risk."""

    @property
    def input_validator(self) -> PayloadValidator[InputT]:
        """Return the input validation boundary for the declared input schema."""

    @property
    def output_validator(self) -> PayloadValidator[OutputT]:
        """Return the output validation boundary for the declared output schema."""

    async def async_assess(self, target: ResourceRef) -> CapabilityAssessment:
        """Read technical support/readiness; central policy can further restrict it."""
