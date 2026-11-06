from django.urls import path

from roster import views

urlpatterns = [
    path("groupes/", views.group_list, name="group-list"),
    path("groupes/importer/", views.group_import, name="group-import"),
    path("groupes/<int:pk>/", views.group_detail, name="group-detail"),
    path("groupes/<int:pk>/supprimer/", views.group_delete, name="group-delete"),
]
