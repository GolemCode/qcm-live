"""Routes de l'application."""

from django.contrib.auth import views as auth_views
from django.urls import include, path

from config import views
from live import views as live_views

urlpatterns = [
    path("", live_views.home, name="home"),
    path("s/<str:code>/", live_views.student_session, name="student-session"),
    path("s/<str:code>/etat/", live_views.student_state, name="student-state"),
    path("s/<str:code>/reponse/", live_views.student_answer, name="student-answer"),
    path("prof/", views.teacher_home, name="teacher-home"),
    path("prof/connexion/", auth_views.LoginView.as_view(), name="login"),
    path("prof/deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
    path("prof/", include("bank.urls")),
    path("prof/", include("roster.urls")),
    path("prof/", include("live.urls")),
]
