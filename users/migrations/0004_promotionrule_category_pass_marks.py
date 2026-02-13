from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0003_alter_cascore_ca1_score_alter_cascore_ca2_score_and_more'),
    ]
    operations = [
        migrations.AddField(
            model_name='promotionrule',
            name='category_pass_marks',
            field=models.JSONField(
                default=dict, blank=True,
                help_text='e.g. {"core": 50, "elective": 45, "vocational": 40}'
            ),
        ),
    ]