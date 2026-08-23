#!/usr/bin/env bash
set -euo pipefail

image_ref="${1:?Pass an image reference}"
expected_version="${2:?Pass the expected version}"
expected_arch="${3:?Pass the expected Home Assistant architecture}"
container_name="homelab-updates-validation-${RANDOM}-${RANDOM}"

cleanup() {
  docker rm --force "${container_name}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

image_config="$(docker image inspect "${image_ref}")"
jq -e '.[0].Config.ExposedPorts["8099/tcp"] == {}' <<< "${image_config}"
jq -e '.[0].Config.Volumes["/data"] == {}' <<< "${image_config}"
jq -e '.[0].Config.Healthcheck.Test | length > 0' <<< "${image_config}"
jq -e --arg version "${expected_version}" \
  '.[0].Config.Labels["io.hass.version"] == $version' <<< "${image_config}"
jq -e --arg arch "${expected_arch}" \
  '.[0].Config.Labels["io.hass.arch"] == $arch' <<< "${image_config}"

docker run --rm --entrypoint ansible "${image_ref}" --version
docker run --rm --entrypoint ssh "${image_ref}" -V

docker run --detach \
  --name "${container_name}" \
  --env HUL_API_TOKEN=synthetic-container-validation-token \
  "${image_ref}"

for _attempt in {1..45}; do
  state="$(docker inspect --format '{{.State.Status}}' "${container_name}")"
  health="$(docker inspect --format '{{.State.Health.Status}}' "${container_name}")"
  if [[ "${health}" == "healthy" ]]; then
    break
  fi
  if [[ "${state}" == "exited" || "${state}" == "dead" ]]; then
    docker logs "${container_name}"
    exit 1
  fi
  sleep 1
done

if [[ "$(docker inspect --format '{{.State.Health.Status}}' "${container_name}")" != "healthy" ]]; then
  docker logs "${container_name}"
  exit 1
fi

docker exec "${container_name}" python -c '
from pathlib import Path

uid_line = next(
    line for line in Path("/proc/1/status").read_text().splitlines()
    if line.startswith("Uid:")
)
assert uid_line.split()[1] == "10001"
'
