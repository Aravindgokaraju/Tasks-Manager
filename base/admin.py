from django.contrib import admin
from .models import Project, Task

admin.site.register(Task)
admin.site.register(Project)

# Did not use the admin panel much
