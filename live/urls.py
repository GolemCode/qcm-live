"""Routes enseignant des sessions (sous /prof/)."""

from django.urls import path

from live import views

urlpatterns = [
    path("sessions/", views.session_list, name="session-list"),
    path("sessions/lancer/", views.session_launch, name="session-launch"),
    path("sessions/<str:code>/", views.board, name="board"),
    path("sessions/<str:code>/etat/", views.board_state, name="board-state"),
    path("sessions/<str:code>/demarrer/", views.session_start, name="session-start"),
    path("sessions/<str:code>/plus-10/", views.session_add_time, name="session-add-time"),
    path("sessions/<str:code>/resultats/", views.results, name="results"),
    path("sessions/<str:code>/resultats.csv", views.results_csv, name="results-csv"),
    path("sessions/<str:code>/connectes/", views.participants, name="participants"),
    path(
        "sessions/<str:code>/connectes/<int:pk>/liberer/",
        views.participant_release,
        name="participant-release",
    ),
]
