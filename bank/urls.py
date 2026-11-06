from django.urls import path

from bank import views

urlpatterns = [
    path("questions/", views.question_list, name="question-list"),
    path("questions/nouvelle/", views.question_edit, name="question-create"),
    path("questions/<int:pk>/modifier/", views.question_edit, name="question-update"),
    path("questions/<int:pk>/supprimer/", views.question_delete, name="question-delete"),
    path("qcm/", views.quiz_list, name="quiz-list"),
    path("qcm/nouveau/", views.quiz_edit, name="quiz-create"),
    path("qcm/<int:pk>/", views.quiz_detail, name="quiz-detail"),
    path("qcm/<int:pk>/modifier/", views.quiz_edit, name="quiz-update"),
    path("qcm/<int:pk>/supprimer/", views.quiz_delete, name="quiz-delete"),
]
