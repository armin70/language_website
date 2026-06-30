class StudentsConfig(AppConfig):
    name = 'students'

    def ready(self):
        import students.signals
