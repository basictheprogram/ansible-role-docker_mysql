"""Network/auth tests for the ansible-role-docker_mysql Molecule scenario."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from testinfra.host import Host

from ._data import MYSQL_CONTAINER_NAME, MYSQL_HOST_PORT, MYSQL_ROOT_PASSWORD


def test_port_is_listening(host: Host) -> None:
    assert host.socket(f"tcp://0.0.0.0:{MYSQL_HOST_PORT}").is_listening


def test_mysqladmin_ping(host: Host) -> None:
    cmd = host.run(
        f"docker exec {MYSQL_CONTAINER_NAME} mysqladmin ping -uroot -p{MYSQL_ROOT_PASSWORD}",
    )
    assert cmd.rc == 0
    assert "mysqld is alive" in cmd.stdout


def test_root_login(host: Host) -> None:
    cmd = host.run(
        f'docker exec {MYSQL_CONTAINER_NAME} mysql -uroot -p{MYSQL_ROOT_PASSWORD} -e "SELECT 1;"',
    )
    assert cmd.rc == 0
