"""Routes de l'application."""

from django.contrib.auth import views as auth_views
from django.urls import path

from config import views

urlpatterns = [
    path("", views.home, name="home"),
    path("prof/", views.teacher_home, name="teacher-home"),
    path("prof/connexion/", auth_views.LoginView.as_view(), name="login"),
    path("prof/deconnexion/", auth_views.LogoutView.as_view(), name="logout"),
]
