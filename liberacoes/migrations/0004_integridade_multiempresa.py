"""Garante no PostgreSQL que relações de negócio mantenham a mesma organização."""

from django.db import migrations


SQL = """
CREATE OR REPLACE FUNCTION tcc_validar_veiculo_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_transportadora WHERE id = NEW.transportadora_id
    ) THEN
        RAISE EXCEPTION 'Veículo e transportadora devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tcc_validar_vinculo_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_motorista WHERE id = NEW.motorista_id
    ) OR NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_transportadora WHERE id = NEW.transportadora_id
    ) THEN
        RAISE EXCEPTION 'Vínculo e entidades relacionadas devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tcc_validar_solicitacao_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM accounts_usuario WHERE id = NEW.solicitante_id
    ) OR NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_motorista WHERE id = NEW.motorista_id
    ) OR NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_veiculo WHERE id = NEW.veiculo_id
    ) OR NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM cadastros_transportadora WHERE id = NEW.transportadora_id
    ) OR (NEW.decidida_por_id IS NOT NULL AND NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM accounts_usuario WHERE id = NEW.decidida_por_id
    )) THEN
        RAISE EXCEPTION 'Solicitação e entidades relacionadas devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tcc_validar_liberacao_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM liberacoes_solicitacaoliberacao WHERE id = NEW.solicitacao_id
    ) OR (NEW.revogada_por_id IS NOT NULL AND NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM accounts_usuario WHERE id = NEW.revogada_por_id
    )) THEN
        RAISE EXCEPTION 'Liberação e entidades relacionadas devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tcc_validar_avaliacao_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM liberacoes_solicitacaoliberacao WHERE id = NEW.solicitacao_id
    ) OR NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM liberacoes_regra WHERE id = NEW.regra_id
    ) THEN
        RAISE EXCEPTION 'Avaliação e entidades relacionadas devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION tcc_validar_historico_organizacao() RETURNS trigger AS $$
BEGIN
    IF NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM liberacoes_solicitacaoliberacao WHERE id = NEW.solicitacao_id
    ) OR (NEW.liberacao_id IS NOT NULL AND (
        NEW.organizacao_id IS DISTINCT FROM (
            SELECT organizacao_id FROM liberacoes_liberacao WHERE id = NEW.liberacao_id
        ) OR NEW.solicitacao_id IS DISTINCT FROM (
            SELECT solicitacao_id FROM liberacoes_liberacao WHERE id = NEW.liberacao_id
        )
    )) OR (NEW.usuario_id IS NOT NULL AND NEW.organizacao_id IS DISTINCT FROM (
        SELECT organizacao_id FROM accounts_usuario WHERE id = NEW.usuario_id
    )) THEN
        RAISE EXCEPTION 'Histórico e entidades relacionadas devem pertencer à mesma organização';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tcc_veiculo_organizacao
BEFORE INSERT OR UPDATE ON cadastros_veiculo
FOR EACH ROW EXECUTE FUNCTION tcc_validar_veiculo_organizacao();

CREATE TRIGGER tcc_vinculo_organizacao
BEFORE INSERT OR UPDATE ON cadastros_vinculomotoristatransportadora
FOR EACH ROW EXECUTE FUNCTION tcc_validar_vinculo_organizacao();

CREATE TRIGGER tcc_solicitacao_organizacao
BEFORE INSERT OR UPDATE ON liberacoes_solicitacaoliberacao
FOR EACH ROW EXECUTE FUNCTION tcc_validar_solicitacao_organizacao();

CREATE TRIGGER tcc_liberacao_organizacao
BEFORE INSERT OR UPDATE ON liberacoes_liberacao
FOR EACH ROW EXECUTE FUNCTION tcc_validar_liberacao_organizacao();

CREATE TRIGGER tcc_avaliacao_organizacao
BEFORE INSERT OR UPDATE ON liberacoes_avaliacaoregra
FOR EACH ROW EXECUTE FUNCTION tcc_validar_avaliacao_organizacao();

CREATE TRIGGER tcc_historico_organizacao
BEFORE INSERT OR UPDATE ON liberacoes_historicoevento
FOR EACH ROW EXECUTE FUNCTION tcc_validar_historico_organizacao();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS tcc_historico_organizacao ON liberacoes_historicoevento;
DROP TRIGGER IF EXISTS tcc_avaliacao_organizacao ON liberacoes_avaliacaoregra;
DROP TRIGGER IF EXISTS tcc_liberacao_organizacao ON liberacoes_liberacao;
DROP TRIGGER IF EXISTS tcc_solicitacao_organizacao ON liberacoes_solicitacaoliberacao;
DROP TRIGGER IF EXISTS tcc_vinculo_organizacao ON cadastros_vinculomotoristatransportadora;
DROP TRIGGER IF EXISTS tcc_veiculo_organizacao ON cadastros_veiculo;
DROP FUNCTION IF EXISTS tcc_validar_historico_organizacao();
DROP FUNCTION IF EXISTS tcc_validar_avaliacao_organizacao();
DROP FUNCTION IF EXISTS tcc_validar_liberacao_organizacao();
DROP FUNCTION IF EXISTS tcc_validar_solicitacao_organizacao();
DROP FUNCTION IF EXISTS tcc_validar_vinculo_organizacao();
DROP FUNCTION IF EXISTS tcc_validar_veiculo_organizacao();
"""


class Migration(migrations.Migration):
    dependencies = [("liberacoes", "0003_avaliacaoregra_avaliacao_regra_unica_por_solicitacao_and_more")]
    operations = [migrations.RunSQL(SQL, REVERSE_SQL)]
