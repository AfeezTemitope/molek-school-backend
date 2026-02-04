from django.db import migrations

def add_description_column(apps, schema_editor):
    schema_editor.execute(
        "ALTER TABLE users_classlevel ADD COLUMN IF NOT EXISTS description VARCHAR(100) DEFAULT ''"
    )

class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]
    
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE users_classlevel ADD COLUMN IF NOT EXISTS description VARCHAR(100) DEFAULT ''",
            reverse_sql="ALTER TABLE users_classlevel DROP COLUMN description"
        )
    ]