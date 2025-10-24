# /backend/core/migrations/0023_update_prazo_padrao_servicos.py
from django.db import migrations

def set_prazo_padrao(apps, schema_editor):
    Servico = apps.get_model('core', 'Servico')
    print("\n  Atualizando prazo padrão (30 dias) para todos os serviços...")
    # Esta linha vai pegar todos os serviços (incluindo os NULL) e definir 30
    count = Servico.objects.all().update(prazo=30) 
    print(f"  {count} serviços atualizados.")

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_alter_servico_prazo'), # Verifique se o nome do arquivo anterior é esse
    ]

    operations = [
        migrations.RunPython(set_prazo_padrao),
    ]