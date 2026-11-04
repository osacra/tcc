"""Gatilhos do PostgreSQL que tornam a tabela de histórico imutável (RNF03)."""

from django.db import migrations

CRIAR = """
CREATE FUNCTION liberacoes_historico_imutavel() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'O histórico de eventos é imutável (% bloqueado).', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER historico_imutavel
BEFORE UPDATE OR DELETE ON liberacoes_historicoevento
FOR EACH ROW EXECUTE FUNCTION liberacoes_historico_imutavel();
"""

REMOVER = """
DROP TRIGGER IF EXISTS historico_imutavel ON liberacoes_historicoevento;
DROP FUNCTION IF EXISTS liberacoes_historico_imutavel();
"""


class Migration(migrations.Migration):
    dependencies = [("liberacoes", "0001_initial")]
    operations = [migrations.RunSQL(CRIAR, REMOVER)]
