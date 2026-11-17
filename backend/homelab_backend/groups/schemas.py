"""Strict bounded HTTP boundary for group metadata and rules."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..contracts.resources import RelationshipKind
from .entities import Group, Predicate, RuleField, SmartRule


class PredicateData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: RuleField
    value: str = Field(min_length=1, max_length=128)
    relationship: RelationshipKind | None = None

    def domain(self) -> Predicate:
        return Predicate(self.field, self.value, self.relationship)


class RuleData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    combine: Literal["all", "any"] = "all"
    predicates: tuple[PredicateData, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid_rule(self) -> RuleData:
        self.domain()
        return self

    def domain(self) -> SmartRule:
        return SmartRule(self.combine, tuple(item.domain() for item in self.predicates))

    @classmethod
    def from_domain(cls, rule: SmartRule) -> RuleData:
        return cls.model_validate({
            "combine": rule.combine,
            "predicates": [
                {"field": p.field, "value": p.value, "relationship": p.relationship}
                for p in rule.predicates
            ],
        })


Tag = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")]


class TagData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tags: frozenset[Tag] = Field(max_length=32)


class GroupInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    kind: Literal["manual", "smart"]
    rule: RuleData | None = None
    members: tuple[UUID, ...] = Field(default=(), max_length=500)

    @model_validator(mode="after")
    def valid_kind(self) -> GroupInput:
        if (self.kind == "smart") != (self.rule is not None):
            raise ValueError("Group kind and rule must agree")
        self.domain(UUID(int=1))
        return self

    def domain(self, group_id: UUID) -> Group:
        return Group(
            group_id,
            self.name,
            self.description,
            self.rule.domain() if self.rule else None,
            self.members,
        )


class GroupData(GroupInput):
    id: UUID

    @classmethod
    def from_domain(cls, group: Group) -> GroupData:
        return cls(
            id=group.id,
            name=group.name,
            description=group.description,
            kind="smart" if group.rule else "manual",
            rule=RuleData.from_domain(group.rule) if group.rule else None,
            members=group.members,
        )
