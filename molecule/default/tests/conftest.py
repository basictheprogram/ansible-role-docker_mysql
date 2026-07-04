"""Session-scoped pytest fixtures for the ansible-role-docker_mysql Molecule scenario."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from ._data import MYSQL_CONTAINER_NAME, MYSQL_HOST_PORT, MYSQL_IMAGE, MYSQL_ROOT_PASSWORD, MYSQL_VERSION

if TYPE_CHECKING:
    from testinfra.host import Host  # noqa: F401  (TYPE_CHECKING-only import)


@pytest.fixture(scope="session")
def mysql_container_name() -> str:
    return MYSQL_CONTAINER_NAME


@pytest.fixture(scope="session")
def mysql_image() -> str:
    return MYSQL_IMAGE


@pytest.fixture(scope="session")
def mysql_version() -> str:
    return MYSQL_VERSION


@pytest.fixture(scope="session")
def mysql_host_port() -> int:
    return MYSQL_HOST_PORT


@pytest.fixture(scope="session")
def mysql_root_password() -> str:
    return MYSQL_ROOT_PASSWORD
