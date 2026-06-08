-- VindIA — schéma MariaDB (PROPOSITION — NON APPLIQUÉ)
-- ⚠️ Aucune base/table n'est créée tant que Davy n'a pas validé.
--    Ne PAS lancer `docker compose up -d mariadb` ni appliquer ce fichier sans accord.
--
-- DÉCISION EN ATTENTE — encodage des ID :
--   Recommandation : CHAR(36) (UUID lisible, portable, cohérent MariaDB <-> SQLite,
--   aligné avec les ID hex générés côté Python). Alternative : BINARY(16)+UUID_TO_BIN
--   (compact mais opaque et divergent du store Python). Ce fichier utilise CHAR(36)
--   à titre de proposition ; à confirmer.
--
-- Compliant by design : isolation tenant, consentement explicite, audit append-only.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS tenants (
  id          CHAR(36)     NOT NULL PRIMARY KEY,
  name        VARCHAR(255) NOT NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS members (
  id          CHAR(36)     NOT NULL PRIMARY KEY,
  tenant_id   CHAR(36)     NOT NULL,
  display_name VARCHAR(255),
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_members_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  INDEX idx_members_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Consentement : pré-requis au traitement (cf. SessionDescriptor.can_process()).
CREATE TABLE IF NOT EXISTS consents (
  id          CHAR(36)     NOT NULL PRIMARY KEY,
  tenant_id   CHAR(36)     NOT NULL,
  member_id   CHAR(36)     NOT NULL,
  scope       VARCHAR(64)  NOT NULL,
  granted     TINYINT(1)   NOT NULL DEFAULT 0,
  granted_at  DATETIME,
  CONSTRAINT fk_consents_member FOREIGN KEY (member_id) REFERENCES members(id),
  INDEX idx_consents_member (tenant_id, member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sessions (
  id          CHAR(36)     NOT NULL PRIMARY KEY,
  tenant_id   CHAR(36)     NOT NULL,
  member_id   CHAR(36),
  room        VARCHAR(255) NOT NULL,
  locale      VARCHAR(16)  NOT NULL DEFAULT 'fr-FR',
  started_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ended_at    DATETIME,
  CONSTRAINT fk_sessions_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id),
  INDEX idx_sessions_room (room)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Audit append-only : pas d'UPDATE/DELETE applicatif (à durcir via privilèges + triggers).
CREATE TABLE IF NOT EXISTS audit_log (
  id          CHAR(36)     NOT NULL PRIMARY KEY,
  tenant_id   CHAR(36)     NOT NULL,
  session_id  CHAR(36),
  event_type  VARCHAR(64)  NOT NULL,
  payload     JSON,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_audit_tenant_time (tenant_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
