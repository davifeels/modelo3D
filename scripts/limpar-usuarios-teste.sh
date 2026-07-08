#!/usr/bin/env bash
# Remove os usuários de TESTE do banco (deixados pela suíte de testes) e tudo
# que depende deles, preservando as contas reais. Os testes criam contas em
# @zefiro.test e @teste.zefiro a cada execução — rode isto para limpar.
#
# Uso:   ./scripts/limpar-usuarios-teste.sh
# Preserva por padrão a conta do dono (ADMIN_EMAIL ou davifeels23@gmail.com).
set -euo pipefail
cd "$(dirname "$0")/.."

KEEP="${ADMIN_EMAIL:-davifeels23@gmail.com}"
echo "Preservando: $KEEP  (e qualquer e-mail fora de @zefiro.test / @teste.zefiro)"

docker compose exec -T db psql -U zefiro -d zefiro <<SQL
BEGIN;
CREATE TEMP TABLE lixo AS
  SELECT id FROM users
  WHERE email <> '${KEEP}'
    AND (email LIKE '%@zefiro.test' OR email LIKE '%@teste.zefiro');
DELETE FROM password_reset_tokens WHERE user_id IN (SELECT id FROM lixo);
DELETE FROM slice_usage           WHERE user_id IN (SELECT id FROM lixo);
DELETE FROM email_logs            WHERE user_id IN (SELECT id FROM lixo);
DELETE FROM purchases             WHERE user_id IN (SELECT id FROM lixo);
DELETE FROM subscriptions         WHERE user_id IN (SELECT id FROM lixo);
DELETE FROM admin_logs            WHERE alvo_user_id IN (SELECT id FROM lixo);
DELETE FROM users                 WHERE id IN (SELECT id FROM lixo);
COMMIT;
SELECT COUNT(*) AS usuarios_restantes FROM users;
SQL
echo "Limpeza concluída."
