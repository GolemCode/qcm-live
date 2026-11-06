"""Pages enseignant : groupes d'étudiants (import, consultation, suppression)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
        group = form.save()
        n = len(form.cleaned_data["file"])
        messages.success(request, f"Groupe importé : {n} étudiant{pluralize(n)}.")
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
