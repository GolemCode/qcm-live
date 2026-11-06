"""Routes enseignant des sessions (sous /prof/)."""

from django.urls import path

from live import views

urlpatterns = [
    path("sessions/", views.session_list, name="session-list"),
    path("sessions/lancer/", views.session_launch, name="session-launch"),
    path("sessions/<str:code>/", views.board, name="board"),
    path("sessions/<str:code>/etat/", views.board_state, name="board-state"),
    path("sessions/<str:code>/demarrer/", views.session_start, name="session-start"),
]
