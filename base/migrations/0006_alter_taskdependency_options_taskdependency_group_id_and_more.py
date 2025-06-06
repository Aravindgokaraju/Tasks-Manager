# Generated by Django 5.2.1 on 2025-05-21 21:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0005_alter_taskdependency_condition"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="taskdependency",
            options={"verbose_name_plural": "Task dependencies"},
        ),
        migrations.AddField(
            model_name="taskdependency",
            name="group_id",
            field=models.CharField(
                blank=True,
                help_text="UUID to identify groups of dependencies that share the same logic",
                max_length=36,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="taskdependency",
            name="logic_group",
            field=models.CharField(
                choices=[
                    ("AND", "All dependencies must be satisfied"),
                    ("OR", "Any dependency must be satisfied"),
                ],
                default="AND",
                help_text="Logical operator for this dependency group",
                max_length=3,
            ),
        ),
        migrations.AlterField(
            model_name="taskdependency",
            name="condition",
            field=models.CharField(
                choices=[
                    ("completed", "Depends on completion"),
                    ("not_completed", "Depends on not being completed"),
                    ("in_progress", "Depends on being in progress"),
                ],
                default="completed",
                max_length=20,
            ),
        ),
    ]
