"""Vues transverses : espace enseignant (l'accueil des étudiants est dans live.views)."""

from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

teacher_home = login_required(TemplateView.as_view(template_name="teacher/home.html"))
