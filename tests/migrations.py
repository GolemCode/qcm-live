"""Tests de migration : ramener la base à un état d'avant une mise à jour, puis l'appliquer
(I12, BAR-01 ; I14, MIG-01)."""

from django.apps.registry import Apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def migrate(targets: list[tuple[str, str]]) -> Apps:
    """Base amenée aux migrations `targets` ; renvoie les modèles de cet état."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def leaves() -> list[tuple[str, str]]:
    """Dernières migrations de chaque application : l'état à jour."""
    return MigrationExecutor(connection).loader.graph.leaf_nodes()
