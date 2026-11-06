"""Vues transverses : accueil et espace enseignant."""

from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

home = TemplateView.as_view(template_name="home.html")
teacher_home = login_required(TemplateView.as_view(template_name="teacher/home.html"))
