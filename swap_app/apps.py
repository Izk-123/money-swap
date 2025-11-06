from django.apps import AppConfig

class SwapAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'swap_app'
    
    def ready(self):
        import swap_app.signals