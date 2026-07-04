"""Container/image/health tests for the ansible-role-docker_mysql Molecule scenario."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testinfra.host import Host

from ._data import MYSQL_CONTAINER_NAME, MYSQL_IMAGE, MYSQL_VERSION


def test_container_is_running(host: Host) -> None:
    container = host.docker(MYSQL_CONTAINER_NAME)
    assert container.is_running


def test_container_uses_pinned_image(host: Host) -> None:
    inspect_data = host.docker(MYSQL_CONTAINER_NAME).inspect()
    assert inspect_data["Config"]["Image"] == f"{MYSQL_IMAGE}:{MYSQL_VERSION}"


def test_container_is_healthy(host: Host) -> None:
    inspect_data = host.docker(MYSQL_CONTAINER_NAME).inspect()
    assert inspect_data["State"]["Health"]["Status"] == "healthy"


def test_container_restart_policy(host: Host) -> None:
    inspect_data = host.docker(MYSQL_CONTAINER_NAME).inspect()
    assert inspect_data["HostConfig"]["RestartPolicy"]["Name"] == "unless-stopped"
