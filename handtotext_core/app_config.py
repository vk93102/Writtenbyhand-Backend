from django.apps import AppConfig


class QuestionSolverConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'question_solver'
    verbose_name = 'Question Solver'

    def ready(self):
        """Import signal handlers when app is ready"""
        # Import signals if any
        pass
