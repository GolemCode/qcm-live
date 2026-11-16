"""Sonde lancée deux fois en même temps par `test_test_database.py`, jamais collectée seule
(son nom ne commence pas par `test_`).

Elle écrit une ligne, attend que l'autre sonde ait écrit la sienne, puis rouvre une connexion,
comme le fait le serveur de test à chaque requête. Elle doit retrouver sa ligne, et elle seule :
une base partagée montrerait celle de l'autre, ou plus aucune si elle a été recréée ou détruite
(« no such table », « readonly database » : les collisions d'I7 et d'I11).
"""

import os
import time
from pathlib import Path

import pytest
from django.db import connection

from roster.models import StudentGroup


def _wait_for_the_other_probe() -> None:
    """Rendez-vous : chaque sonde a écrit sa ligne avant que l'une d'elles ne vérifie."""
    meeting = Path(os.environ["PROBE_MEETING"])
    (meeting / str(os.getpid())).touch()
    deadline = time.monotonic() + 60
    while len(list(meeting.iterdir())) < 2:
        assert time.monotonic() < deadline, "l'autre sonde n'est jamais arrivée"
        time.sleep(0.05)


@pytest.mark.django_db(transaction=True)
def test_probe():
    name = f"sonde {os.getpid()}"
    StudentGroup.objects.create(name=name)
    _wait_for_the_other_probe()
    connection.close()
    # Une base partagée montrerait aussi la ligne de l'autre sonde, ou plus aucune.
    assert list(StudentGroup.objects.values_list("name", flat=True)) == [name]
