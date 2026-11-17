"""Pure immutable grouping rules; membership never authorizes execution."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ..contracts.resources import RelationshipKind, ResourceKind

MAX_RESOURCES = 5000
MAX_MEMBERS = 500
MAX_RULES = 16


class GroupConflict(ValueError):
    """Static safe conflict, never containing user input."""


class RuleField(StrEnum):
    TYPE = "type"
    DISTRO = "distro"
    TAG = "tag"
    CAPABILITY = "capability"
    STATUS = "status"
    RELATIONSHIP = "relationship"


def validate_tag(value: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", value):
        raise GroupConflict("Invalid tag")


@dataclass(frozen=True, slots=True)
class Predicate:
    field: RuleField
    value: str
    relationship: RelationshipKind | None = None

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > 128:
            raise GroupConflict("Invalid rule value")
        if self.field is RuleField.RELATIONSHIP:
            if self.relationship is None:
                raise GroupConflict("Relationship kind is required")
            try:
                UUID(self.value)
            except ValueError:
                raise GroupConflict("Invalid related resource reference") from None
        elif self.relationship is not None:
            raise GroupConflict("Unexpected relationship kind")
        if self.field is RuleField.TYPE and self.value not in ResourceKind:
            raise GroupConflict("Invalid resource type")
        if self.field is RuleField.TAG:
            validate_tag(self.value)
        if self.field is RuleField.CAPABILITY and not re.fullmatch(
            r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+@[1-9][0-9]{0,3}", self.value
        ):
            raise GroupConflict("Invalid versioned capability")


@dataclass(frozen=True, slots=True)
class SmartRule:
    combine: str
    predicates: tuple[Predicate, ...]

    def __post_init__(self) -> None:
        if (
            self.combine not in {"all", "any"}
            or not 1 <= len(self.predicates) <= MAX_RULES
        ):
            raise GroupConflict("Invalid or unbounded smart rule")


@dataclass(frozen=True, slots=True)
class ResourceFacts:
    id: UUID
    kind: ResourceKind
    name: str
    distro: str | None = None
    statuses: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    capabilities: frozenset[str] = frozenset()
    relationships: frozenset[tuple[RelationshipKind, UUID]] = frozenset()


def matches(rule: SmartRule, resource: ResourceFacts) -> bool:
    """Positive exact predicates only; unknown facts cannot satisfy a predicate."""

    def match(predicate: Predicate) -> bool:
        match predicate.field:
            case RuleField.TYPE:
                return resource.kind == predicate.value
            case RuleField.DISTRO:
                return (
                    resource.distro is not None
                    and resource.distro.casefold() == predicate.value.casefold()
                )
            case RuleField.TAG:
                return predicate.value in resource.tags
            case RuleField.CAPABILITY:
                return predicate.value in resource.capabilities
            case RuleField.STATUS:
                return predicate.value in resource.statuses
            case RuleField.RELATIONSHIP:
                return (
                    predicate.relationship,
                    UUID(predicate.value),
                ) in resource.relationships

    results = tuple(match(predicate) for predicate in rule.predicates)
    return all(results) if rule.combine == "all" else any(results)


@dataclass(frozen=True, slots=True)
class Group:
    id: UUID
    name: str
    description: str
    rule: SmartRule | None = None
    members: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 100 or len(self.description) > 500:
            raise GroupConflict("Invalid group metadata")
        if len(self.members) > MAX_MEMBERS or len(set(self.members)) != len(
            self.members
        ):
            raise GroupConflict("Invalid manual membership")
        if self.rule and self.members:
            raise GroupConflict("Smart groups cannot have manual members")
