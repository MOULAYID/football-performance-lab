-- IDs belong to Transfermarkt. Reference attributes are snapshots, not historical features.
CREATE TABLE matches AS
SELECT CAST(game_id AS BIGINT) AS game_id, competition_id,
       CAST(season AS INTEGER) AS season, CAST(date AS DATE) AS match_date,
       CAST(home_club_id AS BIGINT) AS home_club_id,
       CAST(away_club_id AS BIGINT) AS away_club_id,
       CAST(home_club_goals AS INTEGER) AS home_goals,
       CAST(away_club_goals AS INTEGER) AS away_goals
FROM raw_games
WHERE competition_id IN ('GB1','ES1','IT1','L1','FR1')
  AND CAST(season AS INTEGER) BETWEEN 2021 AND 2025;
ALTER TABLE matches ADD PRIMARY KEY (game_id);

CREATE TABLE player_match_stats AS
SELECT CAST(a.player_id AS BIGINT) AS player_id, m.game_id,
       CAST(a.player_club_id AS BIGINT) AS club_id,
       CAST(a.minutes_played AS INTEGER) AS minutes,
       CAST(a.goals AS INTEGER) AS goals, CAST(a.assists AS INTEGER) AS assists
FROM raw_appearances a JOIN matches m ON CAST(a.game_id AS BIGINT)=m.game_id;
ALTER TABLE player_match_stats ADD PRIMARY KEY (player_id,game_id);

CREATE TABLE players AS
SELECT CAST(p.player_id AS BIGINT) AS player_id, p.name AS player_name,
       CAST(CAST(p.date_of_birth AS TIMESTAMP) AS DATE) AS date_of_birth,
       p.country_of_citizenship AS citizenship_snapshot,
       p.position AS position_snapshot, p.sub_position AS sub_position_snapshot
FROM raw_players p
WHERE CAST(p.player_id AS BIGINT) IN (SELECT player_id FROM player_match_stats);
ALTER TABLE players ADD PRIMARY KEY (player_id);

CREATE TABLE clubs AS
SELECT CAST(club_id AS BIGINT) AS club_id, name AS club_name_snapshot
FROM raw_clubs
WHERE CAST(club_id AS BIGINT) IN
 (SELECT home_club_id FROM matches UNION SELECT away_club_id FROM matches);
ALTER TABLE clubs ADD PRIMARY KEY (club_id);

CREATE TABLE competitions AS
SELECT competition_id, name AS competition_name
FROM raw_competitions WHERE competition_id IN ('GB1','ES1','IT1','L1','FR1');
ALTER TABLE competitions ADD PRIMARY KEY (competition_id);

CREATE VIEW match_coverage AS
SELECT m.*, COUNT(a.player_id) AS appearance_rows,
       COUNT(DISTINCT a.club_id) AS appearance_teams,
       COUNT(a.player_id)=0 AS missing_appearances,
       COUNT(a.player_id)<22 OR COUNT(DISTINCT a.club_id)<>2 AS suspect_appearance_coverage
FROM matches m LEFT JOIN player_match_stats a USING(game_id)
GROUP BY ALL;

CREATE VIEW league_season_coverage AS
WITH scope AS (
 SELECT c.competition_id, y.season FROM
 (VALUES ('GB1'),('ES1'),('IT1'),('L1'),('FR1')) c(competition_id)
 CROSS JOIN range(2021,2026) y(season)
)
SELECT s.competition_id, s.season,
       COUNT(m.game_id) AS match_count,
       COUNT(m.game_id) FILTER (WHERE m.missing_appearances) AS matches_missing_appearances,
       COUNT(m.game_id) FILTER (WHERE m.suspect_appearance_coverage) AS matches_with_suspect_coverage,
       CASE WHEN s.competition_id='L1' OR (s.competition_id='FR1' AND s.season>=2023)
            THEN 306 ELSE 380 END AS expected_match_count,
       match_count=expected_match_count AS expected_count_matches,
       MIN(m.match_date) AS first_match, MAX(m.match_date) AS last_match
FROM scope s LEFT JOIN match_coverage m USING(competition_id,season)
GROUP BY s.competition_id,s.season;

CREATE VIEW club_season_coverage AS
WITH schedule AS (
 SELECT competition_id,season,home_club_id AS club_id,game_id FROM matches
 UNION ALL SELECT competition_id,season,away_club_id AS club_id,game_id FROM matches
), present AS (SELECT DISTINCT game_id,club_id FROM player_match_stats)
SELECT s.competition_id,s.season,s.club_id,COUNT(*) AS scheduled_matches,
       COUNT(*) FILTER (WHERE p.game_id IS NULL) AS matches_missing_club_appearances
FROM schedule s LEFT JOIN present p USING(game_id,club_id) GROUP BY ALL;

CREATE VIEW player_club_season AS
WITH totals AS (
 SELECT a.player_id,a.club_id,m.competition_id,m.season,COUNT(*) AS recorded_appearances,
        CASE WHEN COUNT(a.minutes)=COUNT(*) THEN SUM(a.minutes) END AS minutes,
        CASE WHEN COUNT(a.goals)=COUNT(*) THEN SUM(a.goals) END AS goals,
        CASE WHEN COUNT(a.assists)=COUNT(*) THEN SUM(a.assists) END AS assists,
        COUNT(*)-COUNT(a.minutes) AS missing_minutes_rows,
        COUNT(*)-COUNT(a.goals) AS missing_goals_rows,
        COUNT(*)-COUNT(a.assists) AS missing_assists_rows
 FROM player_match_stats a JOIN matches m USING(game_id) GROUP BY ALL
)
SELECT t.*,p.player_name,p.position_snapshot,c.club_name_snapshot,
       90.0*t.goals/NULLIF(t.minutes,0) AS goals_per90,
       90.0*t.assists/NULLIF(t.minutes,0) AS assists_per90,
       cov.scheduled_matches,cov.matches_missing_club_appearances
FROM totals t JOIN players p USING(player_id) JOIN clubs c USING(club_id)
JOIN club_season_coverage cov USING(competition_id,season,club_id);

-- Aggregate from the match facts, so transfers cannot duplicate player totals.
CREATE VIEW player_season AS
WITH totals AS (
 SELECT a.player_id,m.competition_id,m.season,COUNT(DISTINCT a.club_id) AS clubs_played_for,
        COUNT(*) AS recorded_appearances,
        CASE WHEN COUNT(a.minutes)=COUNT(*) THEN SUM(a.minutes) END AS minutes,
        CASE WHEN COUNT(a.goals)=COUNT(*) THEN SUM(a.goals) END AS goals,
        CASE WHEN COUNT(a.assists)=COUNT(*) THEN SUM(a.assists) END AS assists
 FROM player_match_stats a JOIN matches m USING(game_id) GROUP BY ALL
)
SELECT t.*,p.player_name,p.position_snapshot,
       90.0*t.goals/NULLIF(t.minutes,0) AS goals_per90,
       90.0*t.assists/NULLIF(t.minutes,0) AS assists_per90,
       cov.matches_missing_appearances AS league_matches_missing_appearances,
       cov.matches_with_suspect_coverage AS league_matches_with_suspect_coverage,
       cov.expected_count_matches
FROM totals t JOIN players p USING(player_id)
JOIN league_season_coverage cov USING(competition_id,season);
