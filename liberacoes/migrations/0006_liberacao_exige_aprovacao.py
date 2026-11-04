"""Garante no PostgreSQL que uma liberação só exista para solicitação aprovada."""

from django.db import migrations


SQL = """
CREATE OR REPLACE FUNCTION tcc_validar_liberacao_aprovada() RETURNS trigger AS $$
BEGIN
    IF (SELECT estado FROM liberacoes_solicitacaoliberacao WHERE id = NEW.solicitacao_id) <> 'aprovada' THEN
        RAISE EXCEPTION 'A liberação exige uma solicitação aprovada';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tcc_liberacao_aprovada
BEFORE INSERT OR UPDATE ON liberacoes_liberacao
FOR EACH ROW EXECUTE FUNCTION tcc_validar_liberacao_aprovada();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS tcc_liberacao_aprovada ON liberacoes_liberacao;
DROP FUNCTION IF EXISTS tcc_validar_liberacao_aprovada();
"""


class Migration(migrations.Migration):
    dependencies = [("liberacoes", "0005_liberacao_liberacao_estado_valido_and_more")]
    operations = [migrations.RunSQL(SQL, REVERSE_SQL)]
