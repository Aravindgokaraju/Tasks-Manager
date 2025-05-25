from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
from base.models import Project, Task

User = get_user_model()

class Command(BaseCommand):
    help = 'Wipes test data AND resets ID counters'

    def handle(self, *args, **options):
        # Delete data
        User.objects.filter(is_staff=False, is_superuser=False).delete()
        Project.objects.all().delete()
        Task.objects.all().delete()

        # Reset ID sequences
        vendor = connection.vendor
        with connection.cursor() as cursor:
            if vendor == 'sqlite':
                cursor.execute("DELETE FROM sqlite_sequence")
                self.stdout.write("Reset SQLite auto-increment counters")
            elif vendor in ['postgresql', 'mysql']:
                tables = ['auth_user', 'base_project', 'base_task']
                for table in tables:
                    cursor.execute(
                        f"ALTER SEQUENCE {table}_id_seq RESTART WITH 1"
                        if vendor == 'postgresql' else
                        f"ALTER TABLE {table} AUTO_INCREMENT = 1"
                    )
                self.stdout.write(f"Reset {vendor} sequences")

        self.stdout.write(self.style.SUCCESS('Data wiped + ID counters reset'))