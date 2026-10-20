-- =============================================================================
--  FoodBridge – complete MySQL schema
--  Run once against an empty database:
--      mysql -u root -p foodbridge < database.sql
-- =============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- -------------------------------------------------------------------
-- 1. users
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    organisation_name VARCHAR(160) NOT NULL,
    name            VARCHAR(120) NOT NULL,
    email           VARCHAR(254) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,   -- "algo:iterations:hex_salt:hex_key"
    role            ENUM('business','ngo') NOT NULL,
    location        VARCHAR(200) NOT NULL,
    phone           VARCHAR(30)  NOT NULL DEFAULT '',
    is_active       TINYINT(1)   NOT NULL DEFAULT 1,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE  KEY uq_users_email (email),
    KEY     ix_users_role  (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------------
-- 2. ngos   (one row per NGO user, links to users.id)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ngos (
    id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED NOT NULL,
    organisation_name VARCHAR(160) NOT NULL,
    contact_person  VARCHAR(120) NOT NULL,
    location        VARCHAR(200) NOT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE  KEY uq_ngos_user_id (user_id),
    CONSTRAINT fk_ngos_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------------
-- 3. surplus_listings
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS surplus_listings (
    id                  INT UNSIGNED NOT NULL AUTO_INCREMENT,
    seller_id           INT UNSIGNED NOT NULL,
    name                VARCHAR(180) NOT NULL,
    category            ENUM('Vegetables','Fruits','Dairy & Eggs','Grains & Pulses',
                             'Bakery','Spices & Oils','Meat & Seafood','Other')
                                     NOT NULL DEFAULT 'Other',
    description         TEXT         NOT NULL DEFAULT '',
    total_quantity      DECIMAL(12,3) NOT NULL,
    available_quantity  DECIMAL(12,3) NOT NULL,
    unit                ENUM('kg','L','dozen','pack') NOT NULL DEFAULT 'kg',
    discounted_price    DECIMAL(10,2) NOT NULL,
    market_price        DECIMAL(10,2) NOT NULL,
    condition_grade     ENUM('Fresh','Good','Best used soon') NOT NULL DEFAULT 'Fresh',
    location            VARCHAR(200) NOT NULL,
    collection_deadline DATETIME     NOT NULL,
    donation_enabled    TINYINT(1)   NOT NULL DEFAULT 0,
    status              ENUM('available','sold_out','cancelled','expired')
                                     NOT NULL DEFAULT 'available',
    created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_sl_seller    (seller_id),
    KEY ix_sl_status    (status),
    KEY ix_sl_deadline  (collection_deadline),
    KEY ix_sl_category  (category),
    CONSTRAINT fk_sl_seller FOREIGN KEY (seller_id) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------------
-- 4. orders   (business-to-business purchase orders)
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    listing_id  INT UNSIGNED NOT NULL,
    buyer_id    INT UNSIGNED NOT NULL,
    seller_id   INT UNSIGNED NOT NULL,
    quantity    DECIMAL(12,3) NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    total       DECIMAL(12,2) NOT NULL,
    note        TEXT          NOT NULL DEFAULT '',
    status      ENUM('Pending','Confirmed','Ready for collection',
                     'Completed','Cancelled','Rejected')
                              NOT NULL DEFAULT 'Pending',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME     NULL DEFAULT NULL,
    PRIMARY KEY (id),
    KEY ix_orders_buyer  (buyer_id),
    KEY ix_orders_seller (seller_id),
    KEY ix_orders_listing(listing_id),
    KEY ix_orders_status (status),
    CONSTRAINT fk_orders_listing FOREIGN KEY (listing_id) REFERENCES surplus_listings (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_orders_buyer  FOREIGN KEY (buyer_id)  REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_orders_seller FOREIGN KEY (seller_id) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------------
-- 5. donation_requests
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS donation_requests (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    listing_id  INT UNSIGNED NOT NULL,
    ngo_id      INT UNSIGNED NOT NULL,
    seller_id   INT UNSIGNED NOT NULL,
    quantity    DECIMAL(12,3) NOT NULL,
    note        TEXT          NOT NULL DEFAULT '',
    status      ENUM('Requested','Approved','Collected','Cancelled','Declined')
                              NOT NULL DEFAULT 'Requested',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,
    completed_at DATETIME     NULL DEFAULT NULL,
    PRIMARY KEY (id),
    KEY ix_dr_ngo     (ngo_id),
    KEY ix_dr_seller  (seller_id),
    KEY ix_dr_listing (listing_id),
    KEY ix_dr_status  (status),
    CONSTRAINT fk_dr_listing FOREIGN KEY (listing_id) REFERENCES surplus_listings (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_dr_ngo    FOREIGN KEY (ngo_id)    REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_dr_seller FOREIGN KEY (seller_id) REFERENCES users (id)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------------
-- 6. notifications
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id     INT UNSIGNED NOT NULL,
    message     TEXT         NOT NULL,
    is_read     TINYINT(1)   NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY ix_notif_user (user_id),
    KEY ix_notif_read (user_id, is_read),
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users (id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
