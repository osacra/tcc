"""Preserva pelo menos um administrador ativo por organização."""

from django.db import migrations


SQL = """
CREATE OR REPLACE FUNCTION tcc_preservar_ultimo_administrador() RETURNS trigger AS $$
BEGIN
    IF OLD.papel = 'administrador' AND OLD.is_active
       AND (TG_OP = 'DELETE' OR NEW.papel <> 'administrador' OR NOT NEW.is_active)
       AND NOT EXISTS (
           SELECT 1 FROM accounts_usuario
           WHERE organizacao_id = OLD.organizacao_id
             AND id <> OLD.id
             AND papel = 'administrador'
             AND is_active
       ) THEN
        RAISE EXCEPTION 'A organização precisa manter pelo menos um administrador ativo';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tcc_ultimo_administrador
BEFORE UPDATE OR DELETE ON accounts_usuario
FOR EACH ROW EXECUTE FUNCTION tcc_preservar_ultimo_administrador();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS tcc_ultimo_administrador ON accounts_usuario;
DROP FUNCTION IF EXISTS tcc_preservar_ultimo_administrador();
"""


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunSQL(SQL, REVERSE_SQL)]
