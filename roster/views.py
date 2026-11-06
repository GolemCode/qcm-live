"""Pages enseignant : groupes d'étudiants (import, consultation, suppression)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import pluralize

from roster.forms import GroupImportForm
from roster.models import StudentGroup


@login_required
def group_list(request: HttpRequest) -> HttpResponse:
    groups = StudentGroup.objects.annotate(n_students=Count("students"))
    return render(request, "roster/group_list.html", {"groups": groups})


@login_required
def group_import(request: HttpRequest) -> HttpResponse:
    form = GroupImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            group = form.save()
        except IntegrityError:  # même nom enregistré entre la validation et l'écriture
            form.add_error("name", "Un groupe porte déjà ce nom.")
        else:
            roster = form.cleaned_data["file"]
            n = len(roster.entries)
            message = f"Groupe importé : {n} étudiant{pluralize(n)}."
            if roster.header:
                line, text = roster.header
                message += f" Ligne {line} ignorée comme en-tête : « {text} »."
            messages.success(request, message)
            return redirect("group-detail", pk=group.pk)
    return render(request, "roster/group_import.html", {"form": form})


@login_required
def group_detail(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(StudentGroup, pk=pk)
    return render(request, "roster/group_detail.html", {"group": group})


@login_required
def group_delete(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(StudentGroup, pk=pk)
    if request.method == "POST":
        group.delete()
        messages.success(request, "Groupe supprimé.")
        return redirect("group-list")
    return render(request, "roster/group_confirm_delete.html", {"group": group})
