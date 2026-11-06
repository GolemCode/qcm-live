"""Briques communes des formulaires de l'espace enseignant."""

from __future__ import annotations

from django import forms


def table_field[F: forms.Field](field: F) -> F:
    """Champ rendu dans un tableau, sans <label> visible : son libellé devient son nom
    accessible (aria-label)."""
    field.widget.attrs["aria-label"] = field.label
    return field


class TeacherForm(forms.ModelForm):
    """Base des formulaires enseignant : libellés sans « : » (le français en ajouterait un)."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
