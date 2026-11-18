"""Static package-provider composition; no discovery or runtime plugin loading."""

import re

from .ports import ProviderDescriptor
from .providers.apt import DebianAptProvider
from .providers.rpm import DnfProvider, ZypperProvider


class PackageProviders:
    def __init__(self, providers: tuple[ProviderDescriptor, ...] | None = None) -> None:
        registered = (
            providers
            if providers is not None
            else (DebianAptProvider(), DnfProvider(), ZypperProvider())
        )
        self._providers: dict[str, ProviderDescriptor] = {}
        ids: set[str] = set()
        for provider in registered:
            if (
                not re.fullmatch(r"[a-z][a-z0-9_]+", provider.legacy_key)
                or not re.fullmatch(
                    r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", provider.provider_id
                )
                or provider.legacy_key in self._providers
                or provider.provider_id in ids
            ):
                raise ValueError("Invalid or duplicate package provider registration")
            self._providers[provider.legacy_key] = provider
            ids.add(provider.provider_id)

    def resolve(self, name: str) -> ProviderDescriptor:
        provider = self._providers.get(name)
        if provider is None:
            raise ValueError("The configured package provider is unsupported")
        return provider


def package_provider(name: str) -> ProviderDescriptor:
    return PackageProviders().resolve(name)
