"""Sonde lancée deux fois en même temps par `test_test_database.py`, jamais collectée seule
(son nom ne commence pas par `test_`).

Elle écrit une ligne, attend, puis rouvre une connexion, comme le fait le serveur de test à
chaque requête. Si un autre pytest a recréé ou détruit la base entre-temps, la ligne a disparu
(« no such table », « readonly database » : les collisions d'I7 et d'I11).
"""

import os
import time

import pytest
from django.db import connection

from roster.models import StudentGroup


@pytest.mark.django_db(transaction=True)
def test_probe():
    name = f"sonde {os.getpid()}"
    StudentGroup.objects.create(name=name)
    time.sleep(float(os.environ.get("PROBE_PAUSE", "3")))
    connection.close()
    assert StudentGroup.objects.filter(name=name).exists()
