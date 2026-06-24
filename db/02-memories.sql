-- VindIA — migration 02 : mémoire long-terme par membre
-- Chaque session fermée génère des faits extraits par Mistral, stockés ici.
-- La session suivante les recharge dans le system prompt → le LLM "s'en souvient".

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS member_memories (
    id                CHAR(36)     NOT NULL PRIMARY KEY,
    member_id         CHAR(36)     NOT NULL,
    tenant_id         CHAR(36)     NOT NULL,
    source_session_id CHAR(36),
    content           TEXT         NOT NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_memories_member FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    INDEX idx_memories_member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
