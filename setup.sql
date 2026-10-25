-- GALAXIAN leaderboard: run this ONCE before playing.
--   mysql -u root -p < setup.sql
CREATE DATABASE IF NOT EXISTS galaxian_db;
USE galaxian_db;

CREATE TABLE IF NOT EXISTS leaderboard (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    username         VARCHAR(20) NOT NULL UNIQUE,   -- one row per player
    points           INT NOT NULL DEFAULT 0,        -- total points
    levels_completed INT NOT NULL DEFAULT 0,        -- 0 to 7
    enemies_defeated INT NOT NULL DEFAULT 0,
    date_achieved    DATETIME NOT NULL
);

-- Handy queries for your viva:
-- SELECT username, points FROM leaderboard ORDER BY points DESC LIMIT 10;
-- SELECT COUNT(*) FROM leaderboard;
